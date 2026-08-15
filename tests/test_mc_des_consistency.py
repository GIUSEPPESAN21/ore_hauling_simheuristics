"""Consistency test for the Fase 2a fix: on a deterministic (cv=0), congested
minimal instance (1 loader, 2 jobs close enough together for the loader-release
rule to matter), evaluate_mc(loader_release_rule='load_only') must match
evaluate_des exactly, and evaluate_mc(loader_release_rule='full_cycle') must
reproduce the old, larger makespan. See docs/DECISIONES.md, Fase 2a.
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import Instance, Loader, Job
from mc import evaluate_mc
from des import evaluate_des


def _congested_instance() -> Instance:
    return Instance(
        id='TEST', horizon_min=1440.0, meta_plant=0.0, meta_pad=0.0,
        loaders=[Loader(id=0, name='L0', mean_load_min=5.0)],
        jobs=[
            Job(id=0, truck_id=0, truck_type='T', release_min=0.0, destination='Plant',
                grade_pct=1.0, mean_haul_min=10.0, mean_dump_min=2.0, mean_return_min=10.0,
                fine_cu_tons=1.0),
            Job(id=1, truck_id=1, truck_type='T', release_min=8.0, destination='Plant',
                grade_pct=1.0, mean_haul_min=10.0, mean_dump_min=2.0, mean_return_min=10.0,
                fine_cu_tons=1.0),
        ],
    )


class MCDesConsistencyTests(unittest.TestCase):
    def test_load_only_matches_des(self):
        inst = _congested_instance()
        solution = [[0, 1]]
        mc_res = evaluate_mc(inst, solution, cv=0.0, reps=1, base_seed=500000)
        des_res = evaluate_des(inst, solution, cv=0.0, reps=1, base_seed=500000)
        self.assertEqual(mc_res['loader_release_rule'], 'load_only')
        self.assertAlmostEqual(mc_res['mean_cmax_min'], des_res['mean_cmax_min'], places=9)
        self.assertAlmostEqual(mc_res['mean_cmax_min'], 35.0, places=9)

    def test_full_cycle_preserves_pre_fase2_behavior(self):
        inst = _congested_instance()
        solution = [[0, 1]]
        mc_full = evaluate_mc(inst, solution, cv=0.0, reps=1, base_seed=500000,
                              loader_release_rule='full_cycle')
        self.assertAlmostEqual(mc_full['mean_cmax_min'], 54.0, places=9)


if __name__ == '__main__':
    unittest.main()
