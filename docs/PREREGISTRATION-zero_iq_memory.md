# Preregistration: Looking inside the 0 (raw IQ readout of the ground-state cloud across jobs)

**Author:** Máté Róbert (ORCID 0009-0003-3986-6039)  
**Repository:** https://github.com/silentnoisehun/quantum-space-memory  
**Date of registration:** 2026-11-07T07:35:00Z  
**Script:** `scripts/zero_iq_memory.py` (run and analysis in one file), seed `20261111`  

---

## Idea

A standard readout reports every shot as 0 or 1. Physically, each shot is a continuous point in the IQ plane, and the 0/1 bit is only which side of a boundary it falls on. Everything inside the "0" (where the point lies within the ground-state cloud, how wide the cloud is, its tails) is discarded. The earlier space-memory test (quantum-space-memory, 33 pairs, valid null with a passing positive control) looked only at the bits. This test asks the same question with the raw IQ data, which can see shifts too small to change any bit.

## Hypotheses

- **H0 (standard physics):** the position of job B's ground-state cloud does not depend on the secret preparation of the previous, separate job A. Beyond a small thermal satellite (about 1–2%), the cloud is set by the readout chain and is the same whatever happened before.
- **H1 ("something remains inside the 0"):** the centre of job B's ground-state cloud along the 0→1 axis shifts with job A's secret bit.

The test is two-sided.

## Design

- **Readout mode:** SamplerV2 with `meas_type = "kerneled"` (one complex IQ value per shot and qubit). If the backend does not offer IQ data, the script stops before any job is submitted.
- **Qubits:** three in a linear chain, chosen immediately before the run with the preregistered rule of `select_chain.py`; the choice is committed with the data. Selected: `[48, 49, 50]` on `ibm_kingston`.
- **40 pairs of jobs**, 1024 shots per circuit. Secret bits: for each qubit separately 20 ones and 20 zeros, shuffled with the seed and saved in `campaign.json`.
- **Job A_k:** X on each qubit whose secret bit is 1, then measure.
- **Job B_k**, submitted as soon as A_k has returned:
  0. `main`: measure only (primary data);
  1. `cal0`: measure only;
  2. `cal1`: X, measure (axis estimation and drift correction);
  3–4. `ctrl_u0` and `ctrl_u1`: positive control: $X^u$, measure, reset, measure again, for $u = 0$ and $u = 1$.
- The run prints no results while it runs. The analysis starts automatically after the last pair.

## Data processing (fixed now)

- **Global axis per qubit:** $c_0$ = median of all `cal0` shots from all B jobs, $c_1$ = the same for `cal1` (medians of the real and imaginary parts). Each IQ point $z$ gets $x = \text{Re}[(z - c_0)/(c_1 - c_0)]$ and $y = \text{Im}[(z - c_0)/(c_1 - c_0)]$. $x = 0$ is the centre of the 0-cloud, $x = 1$ the centre of the 1-cloud.
- **Drift correction per job:** before projecting, every IQ point of a B job is multiplied by $c_1 / (\text{median of that job's cal1 shots})$. This removes gain and phase drift of the readout chain between jobs. It is tied to the fresh excited state, so a shift that affects only the ground-state cloud is not removed by it.
- **The 0-cloud core:** the shots with $x < 0.5$.

## Primary analysis and decision rule (fixed now)

- Per qubit and pair: $x_0$ = mean $x$ of the `main` circuit's 0-cloud core.
- $\Delta_q$ = mean $x_0$ over pairs with secret bit 1, minus the mean over pairs with secret bit 0. $\Delta$ = mean of $\Delta_q$ over the three qubits.
- **Test:** random relabelling of the secret bits, independently per qubit, 200,000 permutations, two-sided $p$.

**Validity:** at least 20 complete pairs, and in job A at least 95% of the qubit-job cells classify as their secret bit. This also checks that the IQ columns are in qubit order.

**Positive control:** after the reset in circuits 3–4, the mean $x$ of all shots must be larger for $u = 1$ than for $u = 0$ (imperfect reset, about 1.5%), with a one-sided sign-flip permutation $p < 0.01$ over the B jobs. If it fails, the result is inconclusive.

**H1 is supported only if** the run is valid, the positive control passed, the two-sided $p < 0.01$, and $\Delta$ has the same sign in pairs 0–19 and 20–39. In every other case H1 is not supported, and the textbook prediction stands.

## Secondary analyses (reported, not decisive)

- $y$-shift (perpendicular) of the 0-cloud core; width of the core (sd of $x$); fraction of shots with $x \ge 0.5$ (the bit-level metric); fraction with $x \ge 1.5$ (possible higher levels).
- $x_0$ with a per-job axis from that job's `cal0`/`cal1`. This is more sensitive to drift, but a lasting trace inside job B would also shift `cal0` and cancel itself, so it cannot be primary.
- $x_0$ on the global axis without drift correction.
- Within-job shift of the 0-cloud core after reset ($u = 1$ minus $u = 0$): is there a trace inside the 0 on the microsecond scale? This is an interesting question in itself, and the known suspects are residual resonator photons and imperfect reset.
- The null spread of $\Delta$ (from relabelling), so the real sensitivity can be read off the data.

With several secondary metrics, one $p < 0.05$ among them is expected by chance and is not evidence for H1.

## Sensitivity (dry runs before any hardware run)

Simulated Gaussian clouds (width 1/8 of the 0–1 separation, 1% thermal satellite, 1.5% reset error, 1% gain and 0.5° phase drift per job):
- with no built-in effect: $\Delta = 0.0001$, $p = 0.94$, H1 not supported; positive control passed ($p < 0.00001$);
- with a built-in shift of 0.003 of the separation: $\Delta = 0.0031$, $p = 0.005$, H1 supported;
- with 0.005: $p < 0.00001$, H1 supported;
- null spread of $\Delta$: about 0.001 of the separation.

Real drift may be larger; its size will be reported from the data.

## Stopping, exclusions, reporting, replication

- No early stopping, no extension. If the run breaks, all complete pairs (minimum 20) are analysed with the same rule.
- A pair is excluded only if a job returned no data; exclusions are listed.
- All raw IQ data (`pairNNN.npz`), metadata, the chain choice and `analysis.json` are pushed, whatever the result.
- `local_gap_s` is local wall-clock time between two API calls, not time elapsed on the chip, and is not interpreted as such.
- A supported H1 counts as evidence only after a preregistered replication on a second backend.
- QPU time: about 80 small jobs, estimated 3 to 5 minutes, on the author's own account and regular allocation.
