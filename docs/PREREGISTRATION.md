# Preregistration: does information persist on a qubit from one job to the next? ("memory in space")

**Author:** Máté Róbert (ORCID: [0009-0003-3986-6039](https://orcid.org/0009-0003-3986-6039))  
**Repository:** `https://github.com/silentnoisehun/quantum-space-memory`  
**Date of registration:** 2026-11-07 05:03:00 UTC (commit prior to hardware execution)  

---

## Question and hypotheses

After a job ends and the qubits are reset, does the next job on the same physical qubits carry any information about what the previous job did?

- **H0 (standard quantum mechanics with known hardware physics):** no. Residual excitation decays with T1 (about 0.1 to 0.3 ms on Heron), and seconds pass between two jobs. The outcome of job B is independent of the secret bit set in job A, within shot noise.
- **H1 (information persists in space between operations):** the fraction of 1 outcomes in job B depends on the secret bit of job A.

The test is two-sided.

---

## Design

- Scripts: `scripts/space_memory.py` and `scripts/space_memory_analyze.py`, seed 20261110.
- Backend and qubits: three qubits in a linear chain, chosen immediately before the run with the preregistered rule of `scripts/select_chain.py` (lowest sum of readout errors, every qubit at most 3%). The chain and the calibration snapshot are saved and committed with the data.
- 40 pairs of jobs, 1024 shots per circuit.
- Secret bits: for each qubit separately, 20 ones and 20 zeros, shuffled with the seed. The bits are fixed by the seed and are saved in `campaign.json`.
- **Job A_k:** one circuit: X on each qubit whose secret bit is 1, then measure all three.
- **Job B_k**, submitted as soon as A_k has returned its result:
  - circuit 0, the main measurement: measure all three qubits, no gates;
  - circuits 1 to 4, the positive control inside the job: for u in {000, 111} and tau in {0, 20 µs}: X^u, measure, reset, delay tau, measure again.
- Timestamps of submission and return of every job are saved; the gap between A_k returning and B_k being submitted is recorded.

---

## Positive control (validity condition, fixed now)

An imperfect reset leaves slightly more 1 outcomes after a qubit that was in state 1. This is a known, nonzero effect inside a job. For each B job, d_k = mean over qubits of [P1 of the second measurement with u = 1] minus [the same with u = 0], at tau = 0.

The method counts as sensitive only if mean d_k > 0 with a one-sided sign-flip permutation p < 0.01 (200,000 permutations). If the control fails, the result is **inconclusive**, whatever the main metric shows.

---

## Primary analysis and decision rule (fixed now)

For each qubit q: Delta_q = mean P1 in job B over pairs with secret bit 1, minus mean P1 in job B over pairs with secret bit 0. Primary metric: Delta = mean of Delta_q over the three qubits.

Test: random relabelling of the secret bits, independently for each qubit (200,000 permutations), two-sided p.

H1 is **supported** only if all three hold:
1. the positive control passed;
2. two-sided permutation p < 0.01;
3. Delta has the same sign in pairs 0–19 and in pairs 20–39.

In every other case H1 is not supported (or the run is inconclusive if condition 1 fails), and the textbook prediction stands.

---

## Secondary analyses (reported, not decisive)

- Delta for each qubit separately.
- Delta for pairs with a short gap versus a long gap (split at the median gap). A real persisting memory should not depend on queue timing in a way that tracks known hardware decay.
- The positive control at tau = 20 µs (expected smaller than at tau = 0).
- A check that job A set the bits correctly (fraction of qubit outcomes in job A that match the secret bit).

---

## Sensitivity (from dry runs, before any hardware run)

Dry runs with readout error P(1|0) = 0.008 and reset error 0.01:
- with no memory built in, H1 was not supported (Delta = −0.0002, p = 0.77), and the positive control passed (mean d = 0.0095, p < 0.00001);
- with a built-in memory of 0.003 (0.3 percentage points), H1 was supported (p < 0.00001, same sign in both halves);
- detection rate over 10 seeds: 6/10 at 0.0015 and 7/10 at 0.002.

The test therefore detects a cross-job memory of roughly 0.3 percentage points. Job-to-job drift on real hardware can raise this threshold; its size will be reported from the data.

---

## Stopping, exclusions, reporting, replication

- No early stopping on interim results, no extension.
- If the run breaks, all complete pairs are analysed with the same rule (minimum 20 pairs), and the number is reported.
- A pair is excluded only if a job returned no counts; exclusions are listed.
- The run script prints B-job P1 values per pair to the console; the primary analysis is run only after the last pair.
- All raw data, `campaign.json`, the chain selection and `analysis.json` are pushed, whatever the result.
- A supported H1 counts as evidence only after a replication on a second backend with the same rule, preregistered before that run.
- QPU time: about 80 small jobs, estimated 3 to 5 minutes. The run uses only the author's own account and its regular allocation.
