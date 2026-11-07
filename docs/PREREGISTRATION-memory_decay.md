# Preregistration: High-Precision Measurement of Quantum Memory Lifetime Post-Active Reset

**Author:** Máté Róbert (ORCID: [0009-0003-3986-6039](https://orcid.org/0009-0003-3986-6039))  
**Repository:** `https://github.com/silentnoisehun/quantum-space-memory`  
**Date of registration:** 2026-11-07 06:01:00 UTC (commit prior to hardware execution)  

---

## 1. Scientific Objective & Rationale

In the preregistered Space Memory experiment (`measurement_raw/space_memory/20261107T050740Z`), the in-situ positive control conclusively revealed that active reset on superconducting transmons leaves a statistically significant residual memory footprint:
- Immediately post-reset ($\tau = 0\ \mu\text{s}$): $+1.48\%$ excess $|1\rangle$ population ($p = 0.000005$).
- After $\tau = 20\ \mu\text{s}$ delay: $+1.25\%$ excess population still persists ($p = 0.000005$).

To characterize the physical nature of this residual memory, we measure the continuous decay function:
$$d(\tau) = P_1(\tau \mid \text{initial}=1) - P_1(\tau \mid \text{initial}=0)$$
across a microsecond delay sweep $\tau \in [0, 500\ \mu\text{s}]$ on IBM Heron r2 transmons.

---

## 2. Experimental Design

- **Backend:** `ibm_kingston` (156-qubit Heron r2).
- **Physical Transmons:** Linear chain `[48, 49, 50]` (calibrated readout error $\le 0.6\%$).
- **Delay Times ($\tau$):**
  $$\tau \in \{0.0, \; 2.0, \; 5.0, \; 10.0, \; 20.0, \; 50.0, \; 100.0, \; 200.0, \; 500.0\}\ \mu\text{s}$$
- **Circuits:** 9 delays $\times$ 2 initial states ($u \in \{0, 1\}$) = 18 circuits executed in a single batch job.
- **Shots:** 4096 shots per circuit (shot noise floor $\sigma \approx 0.002$ near $P_1 \approx 0.01$).
- **Script:** `scripts/memory_decay_sweep.py`.

---

## 3. Physical Models & Hypothesis Testing

1. **Model 0 (Instantaneous Memoryless Reset):**
   Active reset instantaneously evacuates all energy. $d(\tau) = 0$ for all $\tau \ge 0$.
2. **Model 1 (Single-Exponential Transmon Thermalization):**
   The residual excitation decays with the transmon relaxation time $T_1$:
   $$d(\tau) = d_0 \cdot e^{-\tau / T_{\text{mem}}} + c$$
   where $T_{\text{mem}} \approx T_1 \approx 150 - 250\ \mu\text{s}$.
3. **Model 2 (Resonator Ringdown / Fast Cavity Depopulation):**
   The memory is driven by residual photons in the readout resonator, decaying rapidly with $T_{\text{mem}} \approx \kappa^{-1} \approx 1 - 10\ \mu\text{s}$.
4. **Model 3 (Non-Markovian Two-Level System / TLS Memory):**
   The decay exhibits a multi-exponential or stretched-exponential plateau surviving beyond $T_1$.

---

## 4. Decision & Classification Rule

- The memory gap $d(\tau)$ is computed for each delay.
- Non-linear least squares fit extracts $d_0$, $T_{\text{mem}}$, and asymptotic floor $c$.
- If $T_{\text{mem}} \in [100, 300]\ \mu\text{s}$, the memory is classified as transmon $T_1$ relaxation leakage.
- If $T_{\text{mem}} < 20\ \mu\text{s}$, the memory is classified as cavity ringdown.
- If $T_{\text{mem}} > 500\ \mu\text{s}$ or $c > 0.005$, anomalous TLS persistent memory is supported.
