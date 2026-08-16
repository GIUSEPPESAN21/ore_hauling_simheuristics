"""Process-pool lifecycle for optional replication-level parallelism.

See docs/DECISIONES.md, Fase 6: replications (short_reps/final_reps) are
independent draws (random_streams.py keys every seed on (base_seed, replicate,
job, component, loader), never on execution order), so they are safe to run
across processes. A single Pool is created lazily and reused for the whole
process instead of per-call, since Pool creation is expensive under Windows'
'spawn' start method. workers<=1 means "no pool" (unchanged sequential path).
"""
from __future__ import annotations
import multiprocessing as mp

_pool: mp.pool.Pool | None = None
_pool_workers: int | None = None


def get_pool(workers: int) -> mp.pool.Pool | None:
    global _pool, _pool_workers
    if workers is None or workers <= 1:
        return None
    if _pool is not None and _pool_workers == workers:
        return _pool
    shutdown_pool()
    _pool = mp.Pool(processes=workers)
    _pool_workers = workers
    return _pool


def shutdown_pool() -> None:
    global _pool, _pool_workers
    if _pool is not None:
        _pool.close()
        _pool.join()
    _pool = None
    _pool_workers = None


def chunk_bounds(n: int, workers: int) -> list[tuple[int, int]]:
    """Split range(n) into up to `workers` contiguous, near-equal chunks."""
    if n <= 0:
        return []
    size = -(-n // workers)  # ceil(n / workers)
    return [(start, min(start + size, n)) for start in range(0, n, size)]
