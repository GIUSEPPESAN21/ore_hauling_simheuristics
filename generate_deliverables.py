"""Regenerate resultados_paper/run_manifest.json and resultados_paper/RESUMEN_PARA_PAPER.md
from the current state of resultados_paper/raw/ (per-scenario JSON + run_log.jsonl).

Reads the real files on disk every time it runs -- does not trust any previous snapshot.
Validates every "ok" result (500 replications, mean_cmax_min > 0 and finite, probabilities in
[0, 1], instance/method/cv fields consistent with the filename) before including it. Any
combination missing its JSON is looked up in run_log.jsonl for its last known status
(timeout / failed) instead of being silently omitted.
"""
from __future__ import annotations
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'resultados_paper' / 'raw'
OUT_MANIFEST = ROOT / 'resultados_paper' / 'run_manifest.json'
OUT_SUMMARY_MD = ROOT / 'resultados_paper' / 'RESUMEN_PARA_PAPER.md'

METHODS = ['mc', 'des', 'dynamic']
METHOD_DISPLAY = {'mc': 'SimTSI-MC', 'des': 'SimTSI-DES', 'dynamic': 'DynSimTSI-DES'}
METHOD_DISPLAY_SHORT = {'mc': 'MC', 'des': 'DES', 'dynamic': 'Dinámico'}
CV_LEVELS = (0.05, 0.10, 0.20, 0.30)
INSTANCES = [f'I{i:02d}' for i in range(1, 11)]

INSTANCES_META = {}
with open(ROOT / 'data' / 'instances' / 'instances_summary.csv', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        INSTANCES_META[row['instance']] = (row['loaders'], row['trucks_jobs'])


def scenario_tag(method: str, iid: str, cv: float) -> str:
    return f'{method}_{iid}_cv{int(round(cv * 100)):02d}'


def load_run_log() -> dict:
    """tag -> last log entry (by file order, later entries override earlier retries)."""
    path = RAW / 'run_log.jsonl'
    last = {}
    if not path.exists():
        return last
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            last[entry['tag']] = entry
    return last


def validate(data: dict, method: str, iid: str, cv: float, tag: str) -> list[str]:
    problems = []
    if data.get('instance') != iid:
        problems.append(f"instance en JSON ({data.get('instance')!r}) != {iid!r}")
    if data.get('method') != METHOD_DISPLAY[method]:
        problems.append(f"method en JSON ({data.get('method')!r}) != {METHOD_DISPLAY[method]!r}")
    if not math.isclose(float(data.get('cv', -1)), cv, abs_tol=1e-9):
        problems.append(f"cv en JSON ({data.get('cv')!r}) != {cv!r}")
    if data.get('replications') != 500:
        problems.append(f"replications ({data.get('replications')!r}) != 500")
    mc = data.get('mean_cmax_min')
    if mc is None or not isinstance(mc, (int, float)) or not math.isfinite(mc) or mc <= 0:
        problems.append(f"mean_cmax_min inválido ({mc!r})")
    for pfield in ('prob_finish_within_shift', 'prob_plant_target', 'prob_pad_target'):
        v = data.get(pfield)
        if v is not None:
            if not isinstance(v, (int, float)) or not math.isfinite(v) or not (0.0 <= v <= 1.0):
                problems.append(f"{pfield} fuera de [0,1] o inválido ({v!r})")
    return problems


def main():
    run_log = load_run_log()
    combinations = []
    anomalies = []
    counts = {'ok': 0, 'timeout': 0, 'failed': 0, 'no_intentada': 0}

    for iid in INSTANCES:
        for cv in CV_LEVELS:
            for method in METHODS:
                tag = scenario_tag(method, iid, cv)
                result_path = RAW / f'{tag}.json'
                entry = {'tag': tag, 'method': METHOD_DISPLAY[method], 'instance': iid, 'cv': cv}
                if result_path.exists():
                    data = json.loads(result_path.read_text(encoding='utf-8'))
                    problems = validate(data, method, iid, cv, tag)
                    if problems:
                        entry['status'] = 'anomalia'
                        entry['note'] = '; '.join(problems)
                        anomalies.append({'tag': tag, 'problems': problems})
                    else:
                        entry['status'] = 'ok'
                        entry['cpu_s'] = data.get('cpu_s')
                        entry['mean_cmax_min'] = data.get('mean_cmax_min')
                        entry['replications'] = data.get('replications')
                        counts['ok'] += 1
                else:
                    log_entry = run_log.get(tag)
                    if log_entry and log_entry.get('status') == 'timeout':
                        entry['status'] = 'timeout'
                        entry['elapsed_s'] = log_entry.get('elapsed_s')
                        entry['note'] = (
                            f"No completó dentro del timeout configurado para esta corrida "
                            f"({log_entry.get('elapsed_s'):.1f} s medidos). Ver docs/DECISIONES.md."
                        )
                        counts['timeout'] += 1
                    elif log_entry and log_entry.get('status') == 'failed':
                        entry['status'] = 'failed'
                        entry['error'] = (log_entry.get('error') or '')[-2000:]
                        counts['failed'] += 1
                    else:
                        entry['status'] = 'no_intentada'
                        entry['note'] = 'Sin archivo de resultado ni entrada en run_log.jsonl.'
                        counts['no_intentada'] += 1
                combinations.append(entry)

    total_expected = len(INSTANCES) * len(CV_LEVELS) * len(METHODS)
    now_local = datetime.now().astimezone()
    now_utc = now_local.astimezone(timezone.utc)

    complete = counts['no_intentada'] == 0 and counts['failed'] == 0 and (
        counts['ok'] + counts['timeout'] == total_expected
    )
    status_note = (
        f"Estado DEFINITIVO del lote: {counts['ok']}/{total_expected} combinaciones completas "
        f"y validadas; {counts['timeout']} no completadas por costo computacional (timeout, "
        f"evidencia de tiempo medido en cada entrada); {counts['failed']} con error; "
        f"{counts['no_intentada']} nunca intentadas. "
        + ("Lote cerrado para esta ronda de corridas." if complete else
           "El lote AÚN tiene combinaciones sin intentar -- este manifiesto no es definitivo.")
    )

    manifest = {
        'generated_at_local': now_local.isoformat(),
        'generated_at_utc': now_utc.isoformat(),
        'status_note': status_note,
        'configuration': {
            'short_reps': 5,
            'short_reps_default_in_config_py': 20,
            'final_reps': 500,
            'loader_release_rule': 'load_only',
            'timeout_s_default': 4500,
            'timeout_s_extended_for': {
                'dynamic_I09_cv20': 7200,
                'dynamic_I09_cv30': 7200,
            },
            'workers': 2,
            'tsi_params': {'tenure': 10, 'max_iters': 1000, 'stag_limit': 25, 'perturb_moves': 3},
            'seeds': {'tsi_seed': 12345, 'sim_base_seed': 500000, 'rollout_base_seed': 900000},
        },
        'known_limitation_pending_decision': {
            'topic': 'SimTSI-MC no modela contencion en destinos (Plant/Pad)',
            'ref': 'docs/DECISIONES.md, Fase 2a y Fase 7',
            'decided': False,
        },
        'totals': {'expected': total_expected, **counts},
        'anomalies': anomalies,
        'combinations': combinations,
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')

    # ---- RESUMEN_PARA_PAPER.md ----
    lines = []
    lines.append('# Resumen de resultados para el paper')
    lines.append('')
    lines.append(
        f'Generado automáticamente por `generate_deliverables.py` a partir de '
        f'`resultados_paper/raw/` (snapshot generado el '
        f'{now_local.strftime("%Y-%m-%d %H:%M:%S")}).'
    )
    lines.append('')
    lines.append(f'**Estado del lote:** {status_note}')
    lines.append('')
    lines.append(
        '**Nota importante:** las 10 instancias (I01-I10) son **surrogate** — datos sintéticos '
        'generados para verificación de código, marcados explícitamente como `SURROGATE` en '
        '`data/instances/*.json` (`provenance_note`). No representan la operación real de la '
        'mina; deben reemplazarse por las instancias originales exactas antes de reportar estos '
        'números como resultados operativos en el artículo final.'
    )
    lines.append('')
    lines.append(
        '**Decisión de diseño pendiente para el paper (no resuelta en este pase):** '
        '`SimTSI-MC` no modela contención en los puntos de descarga (Plant/Pad), a diferencia de '
        '`SimTSI-DES`. Ver `docs/DECISIONES.md`, Fase 7, para las dos opciones concretas — '
        'esto afecta cómo se debe presentar cualquier comparación cuantitativa MC-vs-DES.'
    )
    lines.append('')
    lines.append('## Tabla de métricas clave por instancia, CV y método')
    lines.append('')
    lines.append(
        '| Instancia | Loaders/Jobs | CV | Método | cmax medio (min) | DE cmax (min) | '
        'P(fin. en turno) | P(meta planta) | P(meta pad) | Reopt. medias |'
    )
    lines.append('|---|---|---|---|---|---|---|---|---|---|')

    ok_by_tag = {}
    for iid in INSTANCES:
        for cv in CV_LEVELS:
            for method in METHODS:
                tag = scenario_tag(method, iid, cv)
                p = RAW / f'{tag}.json'
                if p.exists():
                    ok_by_tag[tag] = json.loads(p.read_text(encoding='utf-8'))

    n_rows = 0
    for iid in INSTANCES:
        loaders, jobs = INSTANCES_META.get(iid, ('?', '?'))
        for cv in CV_LEVELS:
            for method in METHODS:
                tag = scenario_tag(method, iid, cv)
                data = ok_by_tag.get(tag)
                if data is None:
                    continue
                reopt = data.get('mean_n_reoptimizations')
                reopt_s = f'{reopt:.1f}' if isinstance(reopt, (int, float)) else '-'
                lines.append(
                    f"| {iid} | {loaders}/{jobs} | {cv:g} | {METHOD_DISPLAY_SHORT[method]} | "
                    f"{data['mean_cmax_min']:.1f} | {data.get('sd_cmax_min', float('nan')):.1f} | "
                    f"{data.get('prob_finish_within_shift', float('nan')):.2f} | "
                    f"{data.get('prob_plant_target', float('nan')):.2f} | "
                    f"{data.get('prob_pad_target', float('nan')):.2f} | {reopt_s} |"
                )
                n_rows += 1

    lines.append('')
    lines.append(f'{counts["ok"]} de {total_expected} combinaciones completas están en la tabla de arriba.')
    lines.append('')

    pending = [c for c in combinations if c['status'] != 'ok']
    if pending:
        lines.append('## Combinaciones no completadas')
        lines.append('')
        lines.append(
            f'**{len(pending)} de {total_expected} combinaciones no están en la tabla.** No se '
            'omiten en silencio -- se listan aquí con su estado y evidencia exacta (detalle '
            'completo en `resultados_paper/run_manifest.json`):'
        )
        lines.append('')
        lines.append('| Combinación | Instancia | CV | Método | Estado | Evidencia |')
        lines.append('|---|---|---|---|---|---|')
        for c in pending:
            if c['status'] == 'timeout':
                ev = f"timeout a los {c.get('elapsed_s', 0):.1f} s"
            elif c['status'] == 'failed':
                ev = 'error (ver run_manifest.json)'
            elif c['status'] == 'anomalia':
                ev = c.get('note', '')
            else:
                ev = 'nunca intentada'
            lines.append(
                f"| {c['tag']} | {c['instance']} | {c['cv']:g} | {c['method']} | "
                f"{c['status']} | {ev} |"
            )
        lines.append('')
        timeouts = [c for c in pending if c['status'] == 'timeout']
        if timeouts:
            lines.append(
                f"**{len(timeouts)} no completadas por costo computacional** (timeout), no por "
                "un fallo del código -- ver `docs/DECISIONES.md` (Fase 6-7) para la evidencia de "
                "CPU real acumulada en cada intento y la justificación de no seguir subiendo el "
                "límite de tiempo indefinidamente."
            )
            lines.append('')
    else:
        lines.append(f'**Las {total_expected} combinaciones de la matriz están completas y validadas.**')
        lines.append('')

    OUT_SUMMARY_MD.write_text('\n'.join(lines), encoding='utf-8')
    print(f"OK={counts['ok']} TIMEOUT={counts['timeout']} FAILED={counts['failed']} "
          f"NO_INTENTADA={counts['no_intentada']} ANOMALIAS={len(anomalies)} / {total_expected}")


if __name__ == '__main__':
    main()
