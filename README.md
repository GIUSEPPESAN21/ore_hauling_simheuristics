# Ore hauling simheuristics — IJMST working code

Implements the three agreed methods:

1. **SimTSI-MC**: calibrated TSI + Monte Carlo candidate evaluation.
2. **SimTSI-DES**: calibrated TSI + discrete-event simulation evaluator.
3. **DynSimTSI-DES**: DES + disruption-triggered rolling-horizon TSI, with short DES rollouts.

## Fixed deterministic TSI

The calibrated values are fixed across the new experiments:

- FIFO initial solution
- INSERT neighborhood
- tabu tenure = **10**
- maximum iterations = **1000**
- stagnation limit = **25**
- perturbation = **3 random INSERT moves**
- fixed TSI seed = **12345**

No new TSI calibration runs are performed. Stochastic replications belong to the simulation layer, not to TSI tuning.

## Common random numbers

Primitive durations are generated using keyed random streams by `(replication, job, component, loader)`. Therefore MC, DES and dynamic DES can use the same exogenous stochastic realization for loading, hauling, dumping and return.

## Uncertainty

Main CV levels: `0.05, 0.10, 0.20, 0.30`. `CV=0` can be used as a verification control.
Mean-preserving lognormal durations are used.

## IMPORTANT — instance data

The published conference manuscript specifies the **structure** of the 10 instances (1–10 loading resources, 2–20 CAT 798 AC / Komatsu 960E trucks, 24 h, Plant/Pad, production targets), but it does **not** publish the exact trip-level values of `r_j`, `p_jk`, grades, destinations and production contributions.

Therefore `data/instances/I01.json` ... `I10.json` are **reproducible surrogate trip-level instances for software verification**, preserving the published dimensions. They must be replaced by the exact original 10 instance files before producing final IJMST numerical results. The simulation/optimization code does not need to change when the JSONs are replaced.

## Installation

```bash
pip install -r requirements.txt
python instance_builder.py
```

## Quick smoke tests

```bash
python run_all.py --method mc --instance I01 --cv 0.10 --quick
python run_all.py --method des --instance I01 --cv 0.10 --quick
python run_all.py --method dynamic --instance I01 --cv 0.10 --quick
```

`--quick` intentionally reduces iterations and replications. Do **not** use quick mode for the paper.

## Full single-scenario runs

```bash
python run_all.py --method mc --instance I05 --cv 0.20
python run_all.py --method des --instance I05 --cv 0.20
python run_all.py --method dynamic --instance I05 --cv 0.20
```

## Full 10 x 4 experiment matrix

```bash
python run_all.py --method all --batch
```

This runs 10 base instances × 4 positive CV levels × 3 simheuristics.

## Dynamic trigger

Current implementation triggers residual reoptimization when either:

- destination queue length >= 2, or
- a not-yet-loaded job has waited >= 30 min,

subject to a minimum 15 min interval between reoptimizations.

These dynamic parameters are isolated in `config.py`, so they can be calibrated separately without touching the calibrated TSI.
