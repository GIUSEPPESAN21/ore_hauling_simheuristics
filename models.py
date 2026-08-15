from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict
import json

@dataclass(frozen=True)
class Loader:
    id: int
    name: str
    mean_load_min: float

@dataclass(frozen=True)
class Job:
    id: int
    truck_id: int
    truck_type: str
    release_min: float
    destination: str
    grade_pct: float
    mean_haul_min: float
    mean_dump_min: float
    mean_return_min: float
    fine_cu_tons: float

@dataclass
class Instance:
    id: str
    horizon_min: float
    meta_plant: float
    meta_pad: float
    loaders: List[Loader]
    jobs: List[Job]

    @property
    def n_loaders(self) -> int:
        return len(self.loaders)

    @property
    def n_jobs(self) -> int:
        return len(self.jobs)

    def job_map(self) -> Dict[int, Job]:
        return {j.id: j for j in self.jobs}

    def loader_map(self) -> Dict[int, Loader]:
        return {m.id: m for m in self.loaders}


def instance_from_dict(d: dict) -> Instance:
    return Instance(
        id=d['id'],
        horizon_min=float(d['horizon_min']),
        meta_plant=float(d['meta_plant']),
        meta_pad=float(d['meta_pad']),
        loaders=[Loader(**x) for x in d['loaders']],
        jobs=[Job(**x) for x in d['jobs']],
    )


def load_instance(path: str | Path) -> Instance:
    with open(path, 'r', encoding='utf-8') as f:
        return instance_from_dict(json.load(f))


def solution_key(solution: List[List[int]]) -> tuple:
    return tuple(tuple(seq) for seq in solution)


def validate_solution(instance: Instance, solution: List[List[int]]) -> None:
    if len(solution) != instance.n_loaders:
        raise ValueError('Solution must contain one sequence per loader.')
    flat = [j for seq in solution for j in seq]
    expected = sorted(j.id for j in instance.jobs)
    if sorted(flat) != expected or len(flat) != len(set(flat)):
        raise ValueError('Solution must contain every job exactly once.')
