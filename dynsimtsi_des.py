from __future__ import annotations
import time
from statistics import mean, pstdev
from copy import deepcopy

from config import (TSIParams, SimBudget, DynamicParams, TSI_SEED,
                    SIM_BASE_SEED, ROLLOUT_BASE_SEED)
from models import Instance
from tsi import tabu_search
from des import DESimulator
from simtsi_des import run_simtsi_des
from parallel_pool import get_pool, chunk_bounds


def _residual_solution(sim: DESimulator):
    return [list(q) for q in sim.pending]


def _triggered(sim: DESimulator, dyn: DynamicParams, last_reopt: float) -> bool:
    if sim.time - last_reopt < dyn.min_reopt_interval_min:
        return False
    qmax = max(len(sim.dest_queue['Plant']), len(sim.dest_queue['Pad']))
    waitmax = 0.0
    for jid, st in sim.status.items():
        if st == 'waiting_loader':
            waitmax = max(waitmax, sim.time - sim.wait_since[jid])
    return qmax >= dyn.queue_threshold or waitmax >= dyn.delay_threshold_min


def _rollout_fitness(sim: DESimulator, residual, dyn: DynamicParams,
                     rollout_seed: int, penalty_per_ton_min: float) -> float:
    vals = []
    for rr in range(dyn.rollout_reps):
        clone = sim.clone()
        clone.base_seed = rollout_seed
        clone.replicate = rr
        clone.set_future_solution(residual)
        met = clone.run_to_end()
        shortfall = max(0.0, clone.instance.meta_plant-met['plant']) + max(0.0, clone.instance.meta_pad-met['pad'])
        vals.append(met['cmax'] + penalty_per_ton_min*shortfall)
    return mean(vals)


def run_one_dynamic_rep(instance: Instance, static_solution, cv: float, actual_rep: int,
                        tsi_params: TSIParams, dyn: DynamicParams,
                        tsi_seed: int, sim_seed: int, rollout_seed: int,
                        penalty_per_ton_min: float):
    sim = DESimulator(instance, static_solution, cv, actual_rep, sim_seed)
    n_reopt = 0
    decision_times = []
    last_reopt = -1e18

    while sim.events:
        sim.step()
        if n_reopt >= dyn.max_reopts:
            continue
        eligible = [j for j,s in sim.status.items() if s in ('not_released','waiting_loader')]
        if len(eligible) <= 1 or not _triggered(sim, dyn, last_reopt):
            continue
        initial_res = _residual_solution(sim)
        t0 = time.perf_counter()
        # Residual TSI uses the same calibrated search parameters and fixed seed.
        # validate_full=False because only remaining jobs are optimized.
        def evaluator(s):
            return _rollout_fitness(sim, s, dyn,
                                    rollout_seed + n_reopt*10000,
                                    penalty_per_ton_min)
        ts = tabu_search(instance, evaluator, initial_res, tsi_params, tsi_seed,
                         validate_full=False)
        sim.set_future_solution(ts['best_solution'])
        decision_times.append(time.perf_counter()-t0)
        last_reopt = sim.time
        n_reopt += 1

    met = sim.metrics()
    met['n_reoptimizations'] = n_reopt
    met['mean_decision_time_s'] = mean(decision_times) if decision_times else 0.0
    met['max_decision_time_s'] = max(decision_times) if decision_times else 0.0
    return met


def _run_dynamic_rep_range(instance: Instance, static_solution, cv: float,
                           rep_start: int, rep_end: int, tsi_params: TSIParams,
                           dyn: DynamicParams, tsi_seed: int, sim_seed: int,
                           rollout_seed: int, penalty_per_ton_min: float) -> list:
    """One process-pool task per chunk of top-level replications. Each
    replication is a fully independent simulated shift (its own DESimulator
    seeded by `replicate`, its own possible reoptimizations), so this is the
    highest-leverage parallelization target for DynSimTSI-DES specifically —
    see docs/DECISIONES.md, Fase 6."""
    return [run_one_dynamic_rep(instance, static_solution, cv, r, tsi_params,
                                dyn, tsi_seed, sim_seed, rollout_seed,
                                penalty_per_ton_min)
            for r in range(rep_start, rep_end)]


def run_dynsimtsi_des(instance: Instance, cv: float,
                      tsi_params: TSIParams = TSIParams(), budget: SimBudget = SimBudget(),
                      dyn: DynamicParams = DynamicParams(), tsi_seed: int = TSI_SEED,
                      sim_seed: int = SIM_BASE_SEED, rollout_seed: int = ROLLOUT_BASE_SEED,
                      penalty_per_ton_min: float = 1.0, static_solution=None,
                      workers: int = 1):
    t0 = time.perf_counter()
    if static_solution is None:
        # Initial schedule is the static DES simheuristic solution.
        static = run_simtsi_des(instance, cv, tsi_params, budget, tsi_seed,
                                sim_seed, penalty_per_ton_min, workers=workers)
        static_solution = static['best_solution']

    pool = get_pool(workers)
    if pool is None:
        rows = [run_one_dynamic_rep(instance, static_solution, cv, r, tsi_params,
                                    dyn, tsi_seed, sim_seed, rollout_seed,
                                    penalty_per_ton_min)
                for r in range(budget.final_reps)]
    else:
        # Order-invariant aggregation below (mean/pstdev/sums over rows), so
        # chunked cross-process execution reproduces the sequential result
        # exactly (each replication's randomness is keyed on its own index,
        # never on execution order — see random_streams.py).
        chunks = pool.starmap(_run_dynamic_rep_range,
                              [(instance, static_solution, cv, a, b, tsi_params, dyn,
                                tsi_seed, sim_seed, rollout_seed, penalty_per_ton_min)
                               for a, b in chunk_bounds(budget.final_reps, workers)])
        rows = [row for chunk in chunks for row in chunk]
    c = [x['cmax'] for x in rows]
    plant = [x['plant'] for x in rows]; pad = [x['pad'] for x in rows]
    return {
        'method': 'DynSimTSI-DES', 'instance': instance.id, 'cv': cv,
        'best_solution_initial': static_solution,
        'mean_cmax_min': mean(c),
        'sd_cmax_min': pstdev(c) if len(c)>1 else 0.0,
        'prob_finish_within_shift': sum(x <= instance.horizon_min for x in c)/len(c),
        'expected_overtime_min': mean(max(0.0,x-instance.horizon_min) for x in c),
        'prob_plant_target': sum(x >= instance.meta_plant for x in plant)/len(plant),
        'prob_pad_target': sum(x >= instance.meta_pad for x in pad)/len(pad),
        'mean_truck_wait_min': mean(x['truck_wait_mean_min'] for x in rows),
        'mean_loader_utilization': mean(x['loader_utilization_mean'] for x in rows),
        'mean_n_reoptimizations': mean(x['n_reoptimizations'] for x in rows),
        'mean_decision_time_s': mean(x['mean_decision_time_s'] for x in rows),
        'max_decision_time_s': max(x['max_decision_time_s'] for x in rows),
        'replications': budget.final_reps,
        'cpu_s': time.perf_counter()-t0,
        'tsi_seed': tsi_seed, 'simulation_seed': sim_seed,
        'rollout_seed': rollout_seed,
    }
