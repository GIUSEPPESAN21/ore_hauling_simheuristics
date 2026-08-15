"""Basic smoke tests: each of the three methods must run without raising an
exception in --quick mode on the smallest instance (I01). Run with:

    .venv/Scripts/python.exe -m unittest discover -s tests -t . -v
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_all import run


class SmokeTests(unittest.TestCase):
    def test_mc_quick_runs_on_I01(self):
        res = run('mc', 'I01', 0.10, quick=True)
        self.assertEqual(res['method'], 'SimTSI-MC')
        self.assertIn('mean_cmax_min', res)

    def test_des_quick_runs_on_I01(self):
        res = run('des', 'I01', 0.10, quick=True)
        self.assertEqual(res['method'], 'SimTSI-DES')
        self.assertIn('mean_cmax_min', res)

    def test_dynamic_quick_runs_on_I01(self):
        res = run('dynamic', 'I01', 0.10, quick=True)
        self.assertEqual(res['method'], 'DynSimTSI-DES')
        self.assertIn('mean_cmax_min', res)


if __name__ == '__main__':
    unittest.main()
