from __future__ import annotations
import time
from config import TSIParams, SimBudget, TSI_SEED, SIM_BASE_SEED
from models import Instance
from tsi import tabu_search, fifo_solution
from mc import evaluate_mc


def run_simtsi_mc(instance: Instance, cv: float, tsi_params: TSIParams = TSIParams(),
                  budget: SimBudget = SimBudget(), tsi_seed: int = TSI_SEED,
                  sim_seed: int = SIM_BASE_SEED, penalty_per_ton_min: float = 1.0,
                  loader_release_rule: str = 'load_only', workers: int = 1):
    t0 = time.perf_counter()
    initial = fifo_solution(instance)
    def evaluator(s):
        return evaluate_mc(instance, s, cv, budget.short_reps, sim_seed,
                           penalty_per_ton_min, loader_release_rule, workers=workers)['fitness']
    ts = tabu_search(instance, evaluator, initial, tsi_params, tsi_seed)
    final = evaluate_mc(instance, ts['best_solution'], cv, budget.final_reps,
                        sim_seed, penalty_per_ton_min, loader_release_rule, workers=workers)
    final.update({
        'method': 'SimTSI-MC', 'instance': instance.id, 'cv': cv,
        'best_solution': ts['best_solution'], 'search_fitness': ts['best_fitness'],
        'tsi_evaluations': ts['evaluations'], 'cpu_s': time.perf_counter()-t0,
        'tsi_seed': tsi_seed, 'simulation_seed': sim_seed,
    })
    return final
