"""Consistency test for the Fase 8 fix: on a deterministic (cv=0) instance where
2 loaders converge on the same destination in the same instant, evaluate_mc with
dest_contention_rule='queued' must match evaluate_des exactly (both serialize the
second truck's dump behind the first's), while dest_contention_rule='none'
reproduces the pre-Fase-8 behavior of two dumps silently overlapping in time.
See docs/DECISIONES.md, Fase 8.
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import Instance, Loader, Job
from mc import evaluate_mc
from des import evaluate_des


def _converging_instance() -> Instance:
    """2 loaders, 1 job each, both destined for 'Plant', both released at t=0 with
    identical (load, haul, dump, return) means -> both trucks arrive at Plant at
    exactly the same instant (t=15), forcing the destination queue to matter."""
    job_kwargs = dict(truck_type='T', release_min=0.0, destination='Plant', grade_pct=1.0,
                      mean_haul_min=10.0, mean_dump_min=5.0, mean_return_min=10.0,
                      fine_cu_tons=1.0)
    return Instance(
        id='TEST', horizon_min=1440.0, meta_plant=0.0, meta_pad=0.0,
        loaders=[Loader(id=0, name='L0', mean_load_min=5.0), Loader(id=1, name='L1', mean_load_min=5.0)],
        jobs=[
            Job(id=0, truck_id=0, **job_kwargs),
            Job(id=1, truck_id=1, **job_kwargs),
        ],
    )


class DestContentionTests(unittest.TestCase):
    def test_queued_matches_des(self):
        inst = _converging_instance()
        solution = [[0], [1]]
        mc_res = evaluate_mc(inst, solution, cv=0.0, reps=1, base_seed=500000,
                            dest_contention_rule='queued')
        des_res = evaluate_des(inst, solution, cv=0.0, reps=1, base_seed=500000)
        self.assertEqual(mc_res['dest_contention_rule'], 'queued')
        # Hand-computed: both trucks arrive at Plant at t=15. Truck 0 dumps [15,20],
        # finishes at 30. Truck 1 must wait for the queue: dumps [20,25], finishes
        # at 35 -- 5 extra minutes, exactly truck 0's dump duration.
        self.assertAlmostEqual(mc_res['mean_cmax_min'], 35.0, places=9)
        self.assertAlmostEqual(mc_res['mean_cmax_min'], des_res['mean_cmax_min'], places=9)
        self.assertAlmostEqual(mc_res['mean_truck_wait_min'], 2.5, places=9)
        self.assertAlmostEqual(mc_res['mean_truck_wait_min'], des_res['mean_truck_wait_min'], places=9)
        self.assertAlmostEqual(mc_res['mean_plant_dump_utilization'],
                               des_res['mean_plant_dump_utilization'], places=9)

    def test_none_reproduces_pre_fase8_overlap(self):
        inst = _converging_instance()
        solution = [[0], [1]]
        mc_res = evaluate_mc(inst, solution, cv=0.0, reps=1, base_seed=500000,
                            dest_contention_rule='none')
        # Pre-Fase-8: both dumps computed independently as [15,20], both trucks
        # finish at 30 -- the destination collision is silently ignored.
        self.assertAlmostEqual(mc_res['mean_cmax_min'], 30.0, places=9)
        self.assertAlmostEqual(mc_res['mean_truck_wait_min'], 0.0, places=9)

    def test_queued_is_default(self):
        inst = _converging_instance()
        solution = [[0], [1]]
        default_res = evaluate_mc(inst, solution, cv=0.0, reps=1, base_seed=500000)
        self.assertEqual(default_res['dest_contention_rule'], 'queued')
        self.assertAlmostEqual(default_res['mean_cmax_min'], 35.0, places=9)


if __name__ == '__main__':
    unittest.main()
