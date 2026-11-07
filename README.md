# Quantum Space Memory: Preregistered Cross-Job Information Persistence Test on Superconducting Transmons

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![IBM Quantum](https://img.shields.io/badge/IBM%20Quantum-Heron%20r2%20(156q)-blue.svg)](https://quantum.ibm.com/)
[![ORCID](https://img.shields.io/badge/ORCID-0009--0003--3986--6039-green.svg)](https://orcid.org/0009-0003-3986-6039)

**Preregistered experimental test probing whether physical superconducting transmon qubits retain information about secret state preparations across distinct, macroscopic execution sessions separated by seconds ("Memory in Space").**

**Author:** Máté Róbert (Rongyász)  
**Affiliation:** Silent Coder Labs  
**ORCID:** [0009-0003-3986-6039](https://orcid.org/0009-0003-3986-6039)  
**Contact:** materobi86@gmail.com  

---

## 🔬 Scientific Question & Predictions

After a quantum job completes, the transmon qubits are reset, and seconds pass before the next independent job is queued, **does any residual physical information persist in the local cavity or qubit space?**

* **$H_0$ (Textbook Quantum Mechanics & Markovian Open System Physics):** No. The transmon relaxation time is $T_1 \approx 150 - 250\ \mu\text{s}$. Thermal relaxation to the ground state $|0\rangle$ occurs within $\sim 1\ \text{ms}$. Across inter-job delays of seconds ($> 10^4 \cdot T_1$), the probability distribution of Job B is strictly independent of Job A's secret bit:
  $$\mathbb{E}[\Delta] = 0$$
* **$H_1$ (Persistent Space Memory / Non-Markovian Residual Field):** Physical information persists in the local environment, inducing a statistically significant correlation between the secret preparation of Job A and the unaddressed ground-state readout of Job B:
  $$\Delta = P_1(\text{secret}=1) - P_1(\text{secret}=0) \neq 0$$

---

## 🛡️ Ironclad Methodology & Validation Safeguards

1. **Pre-commit Preregistration:** Frozen in [`docs/PREREGISTRATION.md`](docs/PREREGISTRATION.md) prior to quantum execution.
2. **In-situ Positive Control:** Every Job B executes mid-circuit reset circuits with delay $\tau \in \{0, 20\ \mu\text{s}\}$. Reset imperfection produces a known non-zero signal $d_k > 0$. **The experiment is declared INCONCLUSIVE if this control fails ($p \ge 0.01$).**
3. **Blinding / Independent Secret Bits:** 20 ones and 20 zeros per qubit, generated deterministically from seed `20261110`.
4. **Exact Permutation Testing:** 200,000 independent relabelling permutations across qubits.
5. **Split-Half Replication:** Requires identical sign in pairs 0–19 and 20–39.

## 📊 Experimental Results (ibm_kingston, Heron r2)

The experiment executed on physical transmons `[48, 49, 50]` on `ibm_kingston` (calibration: `2026-11-07 05:51:53+01:00`). Exactly **33 complete pairs** (66 QPU jobs, 1024 shots/circuit) were executed before open-instance quota was consumed (preregistered minimum rule = 20 pairs).

* **In-situ Positive Control (Reset Imperfection):**
  - $\tau = 0\ \mu\text{s}$: Mean $d_k = +0.01476$ ($+1.48\%$), one-sided sign-flip permutation **$p = 0.000005 < 0.01$**.
  - $\tau = 20\ \mu\text{s}$: Mean $d_k = +0.01255$ ($+1.25\%$), $p < 0.00001$.
  - **Status:** **PASSED** (detector proven sensitive to sub-percent residual state memory).
* **Job A Bit Setting Fidelity:** 100.0% of secret bits were correctly verified.
* **Inter-job Submission Gap:** Median gap = **91.8 ms** (sub-100 ms between Job A completion and Job B submission).
* **Primary Metric (Cross-Job Memory):**
  - Mean $\Delta = +0.00023$ ($+0.023$ percentage points).
  - Per-qubit: Q48 = $-0.00015$, Q49 = $+0.00104$, Q50 = $-0.00020$.
  - Exact two-sided permutation test (200,000 permutations): **$p = 0.360583$** (far above threshold $p < 0.01$).
* **Preregistered Decision:**
  **H1 NOT SUPPORTED** — consistent with $H_0$ and textbook Markovian quantum mechanics. No residual physical information persists in the transmon space across independent execution sessions.

---

## 📁 Repository Layout

```
├── docs/
│   └── PREREGISTRATION.md        # Frozen preregistration protocol
├── scripts/
│   ├── select_chain.py           # Algorithmic transmon selection
│   ├── space_memory.py           # Main QPU orchestrator
│   └── space_memory_analyze.py   # Exact permutation analyzer
└── measurement_raw/              # Complete raw Qiskit job counts & timestamps
```
