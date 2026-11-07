# Preregistration: looking inside the 0, energy-matched control

Author: Máté Róbert (ORCID 0009-0003-3986-6039)  
Repository: https://github.com/silentnoisehun/quantum-space-memory  
Date of registration: 2026-11-07T07:56:00Z  
Script: `scripts/zero_iq_energy_matched.py`, seed 20261112  
Parent test: `docs/PREREGISTRATION-zero_iq_memory.md`  

## Why this test

In the parent test, job A applies an X pulse when the secret bit is 1 and nothing when it is 0. A trace in job B's ground-state cloud could then come from the different microwave energy delivered in job A (heating, amplifier or electronics state) rather than from the qubit state itself. This test removes that difference.

## The only change from the parent test

Job A, per qubit:
- secret bit 1: SX, SX (a full X, two physical pulses);
- secret bit 0: SX, SX† (no net rotation, two physical pulses of the same amplitude and duration).

The pulses are separated by barriers and transpiled with optimization_level = 0, so the compiler cannot cancel them. SX† is implemented as a virtual RZ, one physical SX pulse, and a virtual RZ. For every A job the script counts the physical single-qubit pulses on each qubit after transpilation, saves the counts, and stops the run if any qubit does not receive exactly two. In a local check before registration, the transpiled A circuit had two physical SX pulses on each qubit, and the ideal final state matched the secret bits.

Job B, the drift correction, the metrics, the positive control, the validity conditions, the permutation test, the decision rule (two-sided p < 0.01, same sign in both halves, positive control passed, at least 20 pairs, A bits at least 95% correct), the secondary analyses, the stopping rule and the reporting are exactly as in the parent preregistration.

## Hypotheses and interpretation (fixed now)

- **H0:** with matched pulse energy, job B's ground-state cloud does not depend on job A's secret bit.
- **H1:** it does.

How the two tests together are read:
- parent supported, this one not supported: the parent signal came from pulse energy or electronics, not from the qubit state;
- both supported, with Delta of the same sign: the trace follows the qubit state even at equal energy. This needs a preregistered replication on a second backend before it counts as evidence, and further carriers (readout calibration changes between jobs, scheduling) must still be excluded;
- parent not supported: this test is still run and reported, as a second, independent null on a different seed.

## Sensitivity

The same as the parent test; the dry run with no built-in effect gave H1 not supported, the positive control passed, and the A bits were 100% correct. QPU time: about 80 small jobs, estimated 3 to 5 minutes, on the author's own account and regular allocation.
