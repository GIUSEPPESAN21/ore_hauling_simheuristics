"""Reproduces the exact sequence flagged in Fase 2b: running --method mc, then
--method des, then --method dynamic as three separate invocations (one instance,
--quick) must leave all three rows in summary.csv, not just the last one. Uses
an isolated --outdir so it never touches the real results/ folder.
"""
from __future__ import annotations
import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class SummaryAccumulatesTests(unittest.TestCase):
    def test_mc_then_des_then_dynamic_all_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            for method in ('mc', 'des', 'dynamic'):
                proc = subprocess.run(
                    [sys.executable, str(ROOT/'run_all.py'),
                     '--method', method, '--instance', 'I01', '--cv', '0.10',
                     '--quick', '--outdir', str(outdir)],
                    cwd=str(ROOT), capture_output=True, text=True,
                )
                self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            summary_path = outdir/'summary.csv'
            self.assertTrue(summary_path.exists())
            with open(summary_path, newline='', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))
            methods_found = {r['method'] for r in rows}
            self.assertEqual(methods_found, {'SimTSI-MC', 'SimTSI-DES', 'DynSimTSI-DES'})
            self.assertEqual(len(rows), 3, msg='expected exactly 3 rows, no duplicates, none overwritten')


if __name__ == '__main__':
    unittest.main()
