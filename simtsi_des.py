from __future__ import annotations
import time
from config import TSIParams, SimBudget, TSI_SEED, SIM_BASE_SEED
from models import Instance
from tsi import tabu_search, fifo_solution
from des import evaluate_des


def run_simtsi_des(instance: Instance, cv: float, tsi_params: TSIParams = TSIParams(),
                   budget: SimBudget = SimBudget(), tsi_seed: int = TSI_SEED,
                   sim_seed: int = SIM_BASE_SEED, penalty_per_ton_min: float = 1.0):
    t0 = time.perf_counter()
    initial = fifo_solution(instance)
    def evaluator(s):
        return evaluate_des(instance, s, cv, budget.short_reps, sim_seed,
                            penalty_per_ton_min)['fitness']
    ts = tabu_search(instance, evaluator, initial, tsi_params, tsi_seed)
    final = evaluate_des(instance, ts['best_solution'], cv, budget.final_reps,
                         sim_seed, penalty_per_ton_min)
    final.update({
        'method': 'SimTSI-DES', 'instance': instance.id, 'cv': cv,
        'best_solution': ts['best_solution'], 'search_fitness': ts['best_fitness'],
        'tsi_evaluations': ts['evaluations'], 'cpu_s': time.perf_counter()-t0,
        'tsi_seed': tsi_seed, 'simulation_seed': sim_seed,
    })
    return final
