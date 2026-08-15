from __future__ import annotations
from collections import deque
from typing import Callable, List, Tuple
import random

from config import TSIParams, TSI_SEED
from models import Instance, solution_key, validate_solution

Solution = List[List[int]]
Evaluator = Callable[[Solution], float]


def _copy_solution(solution: Solution) -> Solution:
    """Shallow copy sufficient for a list-of-lists-of-int: avoids copy.deepcopy(),
    which recursively walks object structure and dominates runtime in the innermost
    loop of insert_neighbors() for medium/large instances (see docs/DECISIONES.md,
    Fase 2c)."""
    return [list(route) for route in solution]


def nominal_processing_min(instance: Instance, job_id: int, loader_id: int) -> float:
    job = instance.job_map()[job_id]
    loader = instance.loader_map()[loader_id]
    return loader.mean_load_min + job.mean_haul_min + job.mean_dump_min + job.mean_return_min


def fifo_solution(instance: Instance, loader_ready: List[float] | None = None,
                  job_ids: List[int] | None = None) -> Solution:
    jobs = instance.jobs if job_ids is None else [instance.job_map()[j] for j in job_ids]
    avg_p = {j.id: sum(nominal_processing_min(instance, j.id, k) for k in range(instance.n_loaders)) / instance.n_loaders
             for j in jobs}
    ordered = sorted(jobs, key=lambda j: (j.release_min, avg_p[j.id], j.id))
    seqs: Solution = [[] for _ in range(instance.n_loaders)]
    free = list(loader_ready) if loader_ready is not None else [0.0] * instance.n_loaders
    for job in ordered:
        best_k = min(range(instance.n_loaders), key=lambda k: max(job.release_min, free[k]) + nominal_processing_min(instance, job.id, k))
        seqs[best_k].append(job.id)
        free[best_k] = max(job.release_min, free[best_k]) + nominal_processing_min(instance, job.id, best_k)
    return seqs


def insert_neighbors(solution: Solution):
    """Full INSERT neighborhood; yields (neighbor, descriptive_move_key)."""
    m = len(solution)
    for src in range(m):
        for src_pos, job in enumerate(solution[src]):
            base = _copy_solution(solution)
            base[src].pop(src_pos)
            for dst in range(m):
                for dst_pos in range(len(base[dst]) + 1):
                    if dst == src and dst_pos == src_pos:
                        continue
                    cand = _copy_solution(base)
                    cand[dst].insert(dst_pos, job)
                    yield cand, (job, src, src_pos, dst, dst_pos)


def perturb(solution: Solution, rng: random.Random, moves: int = 3) -> Solution:
    s = _copy_solution(solution)
    for _ in range(moves):
        nonempty = [k for k, seq in enumerate(s) if seq]
        if not nonempty:
            break
        src = rng.choice(nonempty)
        src_pos = rng.randrange(len(s[src]))
        job = s[src].pop(src_pos)
        dst = rng.randrange(len(s))
        dst_pos = rng.randrange(len(s[dst]) + 1)
        s[dst].insert(dst_pos, job)
    return s


def tabu_search(instance: Instance, evaluator: Evaluator,
                initial_solution: Solution | None = None,
                params: TSIParams = TSIParams(), seed: int = TSI_SEED,
                validate_full: bool = True) -> dict:
    rng = random.Random(seed)
    s0 = _copy_solution(initial_solution) if initial_solution is not None else fifo_solution(instance)
    if validate_full:
        validate_solution(instance, s0)

    cache = {}
    def ev(s: Solution) -> float:
        k = solution_key(s)
        if k not in cache:
            cache[k] = float(evaluator(s))
        return cache[k]

    s_curr = _copy_solution(s0)
    s_best = _copy_solution(s0)
    f_best = ev(s_best)
    tabu = deque(maxlen=params.tenure)
    stag = 0
    history = [(0, f_best)]

    for it in range(1, params.max_iters + 1):
        best_cand = None
        best_val = float('inf')
        best_key = None
        for cand, _move in insert_neighbors(s_curr):
            key = solution_key(cand)
            val = ev(cand)
            acceptable = key not in tabu or val < f_best  # aspiration
            if acceptable and val < best_val:
                best_cand, best_val, best_key = cand, val, key
        if best_cand is None:
            s_curr = perturb(s_best, rng, params.perturb_moves)
            stag = 0
            continue
        s_curr = best_cand
        tabu.append(best_key)
        if best_val < f_best - 1e-12:
            s_best = _copy_solution(s_curr)
            f_best = best_val
            stag = 0
        else:
            stag += 1
            if stag >= params.stag_limit:
                s_curr = perturb(s_best, rng, params.perturb_moves)
                stag = 0
        history.append((it, f_best))

    return {
        'best_solution': s_best,
        'best_fitness': f_best,
        'history': history,
        'evaluations': len(cache),
    }
