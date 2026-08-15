from dataclasses import dataclass

TSI_SEED = 12345
SIM_BASE_SEED = 500_000
ROLLOUT_BASE_SEED = 900_000
CV_LEVELS = (0.05, 0.10, 0.20, 0.30)
CV_CONTROL = 0.0

@dataclass(frozen=True)
class TSIParams:
    tenure: int = 10
    max_iters: int = 1000
    stag_limit: int = 25
    perturb_moves: int = 3

@dataclass(frozen=True)
class SimBudget:
    short_reps: int = 20
    elite_reps: int = 100
    final_reps: int = 500

@dataclass(frozen=True)
class DynamicParams:
    queue_threshold: int = 2
    delay_threshold_min: float = 30.0
    min_reopt_interval_min: float = 15.0
    rollout_reps: int = 5
    max_reopts: int = 25
