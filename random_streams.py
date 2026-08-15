from __future__ import annotations
import math
import numpy as np

_COMPONENT_CODE = {
    'load': 11,
    'haul': 22,
    'dump': 33,
    'return': 44,
}


def _seed_sequence(base_seed: int, replicate: int, job_id: int, component: str, loader_id: int = -1):
    code = _COMPONENT_CODE[component]
    return np.random.SeedSequence([int(base_seed), int(replicate), int(job_id), int(code), int(loader_id + 1)])


def lognormal_mean_cv(mean: float, cv: float, base_seed: int, replicate: int,
                      job_id: int, component: str, loader_id: int = -1) -> float:
    """Mean-preserving lognormal draw with deterministic keyed CRN stream."""
    if mean <= 0:
        return 0.0
    if cv <= 0:
        return float(mean)
    sigma2 = math.log1p(cv * cv)
    sigma = math.sqrt(sigma2)
    mu = math.log(mean) - 0.5 * sigma2
    rng = np.random.default_rng(_seed_sequence(base_seed, replicate, job_id, component, loader_id))
    return float(rng.lognormal(mean=mu, sigma=sigma))
