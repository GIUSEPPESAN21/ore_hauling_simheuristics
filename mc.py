from __future__ import annotations
from statistics import mean, pstdev
from typing import List

from models import Instance, validate_solution
from random_streams import lognormal_mean_cv
from parallel_pool import get_pool, chunk_bounds


def _one_mc_rep(instance: Instance, solution: List[List[int]], cv: float,
                replicate: int, base_seed: int,
                loader_release_rule: str = 'load_only') -> dict:
    validate_solution(instance, solution)
    jobs = instance.job_map(); loaders = instance.loader_map()
    completions = {}
    dump_times = {}
    for k, seq in enumerate(solution):
        free = 0.0
        for jid in seq:
            j = jobs[jid]
            load = lognormal_mean_cv(loaders[k].mean_load_min, cv, base_seed, replicate, jid, 'load', k)
            haul = lognormal_mean_cv(j.mean_haul_min, cv, base_seed, replicate, jid, 'haul')
            dump = lognormal_mean_cv(j.mean_dump_min, cv, base_seed, replicate, jid, 'dump')
            ret = lognormal_mean_cv(j.mean_return_min, cv, base_seed, replicate, jid, 'return')
            start = max(j.release_min, free)
            load_end = start + load
            dump_end = load_end + haul + dump
            finish = dump_end + ret
            # loader_release_rule='load_only' matches des.py: the loader is free for the
            # next truck in its sequence as soon as it finishes loading (load_end), not
            # after the truck completes its full haul+dump+return cycle. 'full_cycle' keeps
            # the pre-Fase-2 behavior available for explicit before/after comparison.
            free = load_end if loader_release_rule == 'load_only' else finish
            completions[jid] = finish
            dump_times[jid] = dump_end
    cmax = max(completions.values(), default=0.0)
    plant = sum(jobs[j].fine_cu_tons for j,t in dump_times.items() if t <= instance.horizon_min and jobs[j].destination == 'Plant')
    pad = sum(jobs[j].fine_cu_tons for j,t in dump_times.items() if t <= instance.horizon_min and jobs[j].destination == 'Pad')
    return {'cmax': cmax, 'plant': plant, 'pad': pad}


def _run_mc_rep_range(instance: Instance, solution: List[List[int]], cv: float,
                      rep_start: int, rep_end: int, base_seed: int,
                      loader_release_rule: str) -> List[dict]:
    """One process-pool task per chunk of replications; see des._run_des_rep_range
    for the rationale (persistent Pool, chunked to bound round trips)."""
    return [_one_mc_rep(instance, solution, cv, r, base_seed, loader_release_rule)
            for r in range(rep_start, rep_end)]


def evaluate_mc(instance: Instance, solution: List[List[int]], cv: float,
                reps: int, base_seed: int, penalty_per_ton_min: float = 1.0,
                loader_release_rule: str = 'load_only', workers: int = 1) -> dict:
    if loader_release_rule not in ('load_only', 'full_cycle'):
        raise ValueError("loader_release_rule must be 'load_only' or 'full_cycle'")
    pool = get_pool(workers)
    if pool is None:
        rows = [_one_mc_rep(instance, solution, cv, r, base_seed, loader_release_rule) for r in range(reps)]
    else:
        # See des.evaluate_des: replications are independent and every metric
        # below is order-invariant over rows, so chunked cross-process
        # execution reproduces the sequential result exactly.
        chunks = pool.starmap(_run_mc_rep_range,
                              [(instance, solution, cv, a, b, base_seed, loader_release_rule)
                               for a, b in chunk_bounds(reps, workers)])
        rows = [row for chunk in chunks for row in chunk]
    c = [x['cmax'] for x in rows]
    plant = [x['plant'] for x in rows]
    pad = [x['pad'] for x in rows]
    shortfall = [max(0.0, instance.meta_plant-p) + max(0.0, instance.meta_pad-q) for p,q in zip(plant,pad)]
    fit = [x + penalty_per_ton_min*s for x,s in zip(c, shortfall)]
    return {
        'fitness': mean(fit),
        'mean_cmax_min': mean(c),
        'sd_cmax_min': pstdev(c) if len(c)>1 else 0.0,
        'prob_finish_within_shift': sum(x <= instance.horizon_min for x in c)/len(c),
        'expected_overtime_min': mean(max(0.0, x-instance.horizon_min) for x in c),
        'prob_plant_target': sum(x >= instance.meta_plant for x in plant)/len(plant),
        'prob_pad_target': sum(x >= instance.meta_pad for x in pad)/len(pad),
        'mean_plant_fine_tons': mean(plant),
        'mean_pad_fine_tons': mean(pad),
        'replications': reps,
        'loader_release_rule': loader_release_rule,
    }
