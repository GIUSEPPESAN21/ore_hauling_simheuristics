from __future__ import annotations
import argparse, json, csv, subprocess, sys, time, traceback
from pathlib import Path
from dataclasses import replace

from models import load_instance
from config import TSIParams, SimBudget, DynamicParams, CV_LEVELS
from simtsi_mc import run_simtsi_mc
from simtsi_des import run_simtsi_des
from dynsimtsi_des import run_dynsimtsi_des

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'/'instances'
RESULTS=ROOT/'results'


def to_serializable(x):
    if isinstance(x, (list,dict,str,int,float,bool)) or x is None: return x
    return str(x)


def scenario_tag(method, iid, cv, quick=False) -> str:
    return f'{method}_{iid}_cv{int(round(cv*100)):02d}' + ('_quick' if quick else '')


SUMMARY_KEY_FIELDS = ('instance', 'method', 'cv', 'replications')


def _summary_key(row: dict) -> tuple:
    return tuple(str(row.get(f, '')) for f in SUMMARY_KEY_FIELDS)


def write_summary(new_rows: list[dict], outdir: Path) -> None:
    """Merge new_rows into <outdir>/summary.csv, deduplicated by
    instance+method+cv+replications. Reruns of the same scenario overwrite the
    prior row for that key instead of duplicating it; unrelated existing rows
    (e.g. from a prior --method mc invocation) are preserved. This makes running
    --method mc, then --method des, then --method dynamic separately accumulate
    into one consolidated file instead of each invocation truncating the last."""
    if not new_rows:
        return
    path = outdir/'summary.csv'
    existing: dict[tuple, dict] = {}
    if path.exists():
        with open(path, 'r', newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                existing[_summary_key(row)] = row
    for row in new_rows:
        existing[_summary_key(row)] = row
    all_rows = list(existing.values())
    keys = sorted(set().union(*(r.keys() for r in all_rows)))
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(all_rows)


def run(method, iid, cv, quick=False, loader_release_rule='load_only', short_reps=None):
    inst=load_instance(DATA/f'{iid}.json')
    tsi=TSIParams()
    budget=SimBudget()
    dyn=DynamicParams()
    if quick:
        # Smoke-test only; NOT the paper experiment.
        tsi=replace(tsi,max_iters=15)
        budget=SimBudget(short_reps=2,elite_reps=3,final_reps=3)
        dyn=replace(dyn,rollout_reps=1,max_reopts=2)
    elif short_reps is not None:
        # Search-phase replication budget override (max_iters, tenure, stag_limit,
        # perturb_moves and final_reps are NOT touched). See docs/DECISIONES.md, Fase 4:
        # justified by a stability check showing the final reported solution is
        # unchanged across short_reps in {20,10,5,3} on I02/I03.
        budget=replace(budget,short_reps=short_reps)
    if method=='mc': return run_simtsi_mc(inst,cv,tsi,budget,loader_release_rule=loader_release_rule)
    if method=='des': return run_simtsi_des(inst,cv,tsi,budget)
    if method=='dynamic': return run_dynsimtsi_des(inst,cv,tsi,budget,dyn)
    raise ValueError(method)


def run_one(method, iid, cv, quick, loader_release_rule, outdir: Path, short_reps=None) -> dict:
    """Run exactly one instance+method+cv combination in-process, write its JSON
    result into outdir, and return the scalar summary row. Raises on failure."""
    res = run(method, iid, cv, quick, loader_release_rule, short_reps)
    tag = scenario_tag(method, iid, cv, quick)
    (outdir/f'{tag}.json').write_text(json.dumps(res, indent=2, default=to_serializable), encoding='utf-8')
    return {k: v for k, v in res.items() if not isinstance(v, (list, dict))}


def run_batch(scenarios, methods, quick, loader_release_rule, outdir: Path,
              timeout_s: float | None, resume: bool = True, log_path: Path | None = None,
              short_reps=None):
    """Run every (instance, cv) x method combination with per-combination error
    handling, optional resume (skip combinations whose result JSON already
    exists), and an optional subprocess-level timeout so one hung combination
    (e.g. an oversized instance under production TSI parameters) cannot block the
    rest of the batch. Every attempt is appended as one JSON line to log_path
    with its outcome (ok / failed / timeout / skipped)."""
    outdir.mkdir(parents=True, exist_ok=True)
    log_path = log_path or (outdir/'run_log.jsonl')
    summaries = []
    for iid, cv in scenarios:
        for m in methods:
            tag = scenario_tag(m, iid, cv, quick)
            entry = {'method': m, 'instance': iid, 'cv': cv, 'quick': quick, 'tag': tag}
            result_path = outdir/f'{tag}.json'
            if resume and result_path.exists():
                print(f'Skipping {m} | {iid} | CV={cv:.2f} (already have {result_path.name})')
                entry.update(status='skipped_already_done', elapsed_s=0.0)
                _append_log(log_path, entry)
                try:
                    row = {k: v for k, v in json.loads(result_path.read_text(encoding='utf-8')).items()
                           if not isinstance(v, (list, dict))}
                    summaries.append(row)
                except Exception:
                    pass
                continue
            print(f'Running {m} | {iid} | CV={cv:.2f}')
            t0 = time.perf_counter()
            if timeout_s:
                ok, row, err = _run_one_subprocess(m, iid, cv, quick, loader_release_rule, outdir,
                                                    timeout_s, short_reps)
            else:
                try:
                    row = run_one(m, iid, cv, quick, loader_release_rule, outdir, short_reps)
                    ok, err = True, None
                except Exception:
                    ok, row, err = False, None, traceback.format_exc()
            elapsed = time.perf_counter() - t0
            if ok:
                entry.update(status='ok', elapsed_s=elapsed)
                summaries.append(row)
            else:
                status = 'timeout' if err == 'TIMEOUT' else 'failed'
                entry.update(status=status, elapsed_s=elapsed, error=(err or '')[-4000:])
                print(f'  -> {status}: {m} | {iid} | CV={cv:.2f}')
            _append_log(log_path, entry)
    if summaries:
        write_summary(summaries, outdir)
    return summaries


def _append_log(log_path: Path, entry: dict) -> None:
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, default=to_serializable) + '\n')


def _run_one_subprocess(method, iid, cv, quick, loader_release_rule, outdir: Path, timeout_s: float,
                         short_reps=None):
    """Run one combination in a child process so a hang (infinite/very long TSI
    search on an oversized instance) can be killed after timeout_s instead of
    stalling the whole batch."""
    cmd = [sys.executable, str(Path(__file__).resolve()),
           '--method', method, '--instance', iid, '--cv', str(cv),
           '--outdir', str(outdir), '--loader-release-rule', loader_release_rule,
           '--single-run']
    if quick:
        cmd.append('--quick')
    if short_reps is not None:
        cmd += ['--short-reps', str(short_reps)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return False, None, 'TIMEOUT'
    if proc.returncode != 0:
        return False, None, proc.stderr
    tag = scenario_tag(method, iid, cv, quick)
    result_path = outdir/f'{tag}.json'
    if not result_path.exists():
        return False, None, 'Child process exited 0 but wrote no result file.\n' + proc.stderr
    row = {k: v for k, v in json.loads(result_path.read_text(encoding='utf-8')).items()
           if not isinstance(v, (list, dict))}
    return True, row, None


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--method',choices=['mc','des','dynamic','all'],default='all')
    ap.add_argument('--instance',default='I01')
    ap.add_argument('--cv',type=float,default=0.10)
    ap.add_argument('--quick',action='store_true')
    ap.add_argument('--batch',action='store_true',help='Run all 10 instances x CV={.05,.10,.20,.30}.')
    ap.add_argument('--loader-release-rule',choices=['load_only','full_cycle'],default='load_only',
                    help="mc method only: 'load_only' (default, matches des.py) frees the loader "
                         "at load_end; 'full_cycle' keeps the pre-Fase-2 behavior (loader busy "
                         "until the truck completes load+haul+dump+return) for explicit comparison.")
    ap.add_argument('--outdir',default=None,
                    help='Where to write per-scenario JSON + summary.csv. Defaults to results/.')
    ap.add_argument('--timeout-s',type=float,default=0.0,
                    help='If >0, run each instance+method+cv combination in a subprocess and kill it '
                         'after this many seconds, logging it as a timeout instead of hanging the batch.')
    ap.add_argument('--no-resume',action='store_true',
                    help='Do not skip combinations whose result JSON already exists in --outdir.')
    ap.add_argument('--short-reps',type=int,default=None,
                    help='Override SimBudget.short_reps (search-phase replications, default 20) for '
                         'non-quick runs. Does NOT change max_iters/tenure/stag_limit/perturb_moves '
                         '(TSI calibration) or final_reps (reported precision). See docs/DECISIONES.md, Fase 4.')
    ap.add_argument('--single-run',action='store_true',help=argparse.SUPPRESS)
    args=ap.parse_args()
    outdir = Path(args.outdir).resolve() if args.outdir else RESULTS
    outdir.mkdir(parents=True, exist_ok=True)
    methods=['mc','des','dynamic'] if args.method=='all' else [args.method]

    if args.single_run:
        # Internal entry point used by _run_one_subprocess(): exactly one combination,
        # no resume/logging wrapper (the parent process handles that).
        row = run_one(args.method, args.instance, args.cv, args.quick, args.loader_release_rule,
                      outdir, args.short_reps)
        write_summary([row], outdir)
        return

    scenarios=[]
    if args.batch:
        scenarios=[(f'I{i:02d}',cv) for i in range(1,11) for cv in CV_LEVELS]
    else:
        scenarios=[(args.instance,args.cv)]
    run_batch(scenarios, methods, args.quick, args.loader_release_rule, outdir,
              timeout_s=(args.timeout_s or None), resume=not args.no_resume, short_reps=args.short_reps)

if __name__=='__main__': main()
