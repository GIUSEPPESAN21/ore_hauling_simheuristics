from __future__ import annotations
from statistics import mean, pstdev
from typing import List

from models import Instance, validate_solution
from random_streams import lognormal_mean_cv
from parallel_pool import get_pool, chunk_bounds


def _one_mc_rep(instance: Instance, solution: List[List[int]], cv: float,
                replicate: int, base_seed: int,
                loader_release_rule: str = 'load_only',
                dest_contention_rule: str = 'queued') -> dict:
    """Two-pass evaluation of one replication.

    Pass 1 (per loader, sequential, unchanged from before Fase 8): each loader
    processes its own job sequence one truck at a time, giving every job a
    `load_end` and an `arrive_dest = load_end + haul` -- the moment the truck
    is ready to dump, before knowing whether the destination is free. This
    pass is independent of destination contention because a loader's own
    availability (`free`) only depends on `load_end` under the production
    'load_only' release rule (see Fase 2a) -- never on what other loaders'
    trucks are doing at Plant/Pad.

    Pass 2 (per destination, across ALL loaders' jobs together, Fase 8): jobs
    arriving at the same destination ('Plant' or 'Pad') are processed in
    arrival order and serialized through a single-server queue
    (`dest_free_at`), mirroring des.py's `dest_busy`/`dest_queue` event
    handling exactly, just computed analytically instead of via an event
    loop. This is what was missing before Fase 8: two loaders converging on
    the same destination in a short window used to get independently
    computed (and silently overlapping) dump windows.
    """
    validate_solution(instance, solution)
    jobs = instance.job_map(); loaders = instance.loader_map()
    if dest_contention_rule not in ('queued', 'none'):
        raise ValueError("dest_contention_rule must be 'queued' or 'none'")
    if dest_contention_rule == 'queued' and loader_release_rule == 'full_cycle':
        # Under 'full_cycle' a loader's next start depends on the FINISH of the
        # truck it just released, which under 'queued' depends in turn on the
        # shared destination queue -- coupling every loader's schedule to every
        # other loader's through the queue at each step. Modeling that
        # correctly requires a full event-driven simulation (equivalent to
        # des.py), not the two-pass analytic approach used here. 'full_cycle'
        # is a legacy comparison-only option (production always uses
        # 'load_only'), so this combination is rejected explicitly instead of
        # silently producing an inconsistent result. See docs/DECISIONES.md,
        # Fase 8.
        raise ValueError(
            "dest_contention_rule='queued' is not supported together with "
            "loader_release_rule='full_cycle' -- see docs/DECISIONES.md, Fase 8."
        )

    arrivals = []  # (arrive_dest, jid, dest, dump_duration, return_duration)
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
            arrive_dest = load_end + haul
            # loader_release_rule='load_only' matches des.py: the loader is free for the
            # next truck in its sequence as soon as it finishes loading (load_end), not
            # after the truck completes its full haul+dump+return cycle. 'full_cycle' keeps
            # the pre-Fase-2 behavior available for explicit before/after comparison; it is
            # only reachable here with dest_contention_rule='none' (see check above), so
            # `arrive_dest + dump + ret` below equals the old analytic `finish`.
            free = load_end if loader_release_rule == 'load_only' else (arrive_dest + dump + ret)
            arrivals.append((arrive_dest, jid, j.destination, dump, ret))

    completions = {}
    dump_times = {}
    truck_wait = {j.id: 0.0 for j in instance.jobs}
    dest_busy_time = {'Plant': 0.0, 'Pad': 0.0}
    if dest_contention_rule == 'queued':
        for dest in ('Plant', 'Pad'):
            dest_free_at = 0.0
            for arrive, jid, _d, dump, ret in sorted(a for a in arrivals if a[2] == dest):
                dump_start = max(arrive, dest_free_at)
                dump_end = dump_start + dump
                dest_free_at = dump_end
                dest_busy_time[dest] += dump
                truck_wait[jid] = dump_start - arrive
                dump_times[jid] = dump_end
                completions[jid] = dump_end + ret
    else:  # 'none' -- pre-Fase-8 behavior: no queueing, dumps may silently overlap.
        for arrive, jid, dest, dump, ret in arrivals:
            dump_end = arrive + dump
            dest_busy_time[dest] += dump
            dump_times[jid] = dump_end
            completions[jid] = dump_end + ret

    cmax = max(completions.values(), default=0.0)
    plant = sum(jobs[j].fine_cu_tons for j,t in dump_times.items() if t <= instance.horizon_min and jobs[j].destination == 'Plant')
    pad = sum(jobs[j].fine_cu_tons for j,t in dump_times.items() if t <= instance.horizon_min and jobs[j].destination == 'Pad')
    n = max(1, len(jobs))
    return {
        'cmax': cmax, 'plant': plant, 'pad': pad,
        'truck_wait_mean_min': sum(truck_wait.values())/n,
        'plant_dump_utilization': min(1.0, dest_busy_time['Plant']/max(cmax, 1e-9)),
        'pad_dump_utilization': min(1.0, dest_busy_time['Pad']/max(cmax, 1e-9)),
    }


def _run_mc_rep_range(instance: Instance, solution: List[List[int]], cv: float,
                      rep_start: int, rep_end: int, base_seed: int,
                      loader_release_rule: str, dest_contention_rule: str) -> List[dict]:
    """One process-pool task per chunk of replications; see des._run_des_rep_range
    for the rationale (persistent Pool, chunked to bound round trips)."""
    return [_one_mc_rep(instance, solution, cv, r, base_seed, loader_release_rule, dest_contention_rule)
            for r in range(rep_start, rep_end)]


def evaluate_mc(instance: Instance, solution: List[List[int]], cv: float,
                reps: int, base_seed: int, penalty_per_ton_min: float = 1.0,
                loader_release_rule: str = 'load_only', workers: int = 1,
                dest_contention_rule: str = 'queued') -> dict:
    if loader_release_rule not in ('load_only', 'full_cycle'):
        raise ValueError("loader_release_rule must be 'load_only' or 'full_cycle'")
    pool = get_pool(workers)
    if pool is None:
        rows = [_one_mc_rep(instance, solution, cv, r, base_seed, loader_release_rule, dest_contention_rule)
                for r in range(reps)]
    else:
        # See des.evaluate_des: replications are independent and every metric
        # below is order-invariant over rows, so chunked cross-process
        # execution reproduces the sequential result exactly.
        chunks = pool.starmap(_run_mc_rep_range,
                              [(instance, solution, cv, a, b, base_seed, loader_release_rule,
                                dest_contention_rule)
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
        'mean_truck_wait_min': mean(x['truck_wait_mean_min'] for x in rows),
        'mean_plant_dump_utilization': mean(x['plant_dump_utilization'] for x in rows),
        'mean_pad_dump_utilization': mean(x['pad_dump_utilization'] for x in rows),
        'replications': reps,
        'loader_release_rule': loader_release_rule,
        'dest_contention_rule': dest_contention_rule,
    }
