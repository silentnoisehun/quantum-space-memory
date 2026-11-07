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

### 🏆 Primary Verdict: H0 Confirmed (Valid Null Result with Passed Positive Control)

Across independent QPU jobs separated by macroscopic execution delays, **no residual physical memory persists**:
* **Primary cross-job Delta:** **$\Delta = +0.00023$** ($+0.023$ percentage points), two-sided permutation **$p = 0.36058 \gg 0.01$**.
* **Split-half consistency:** First half $\Delta = +0.00036$, Second half $\Delta = +0.00014$.
* **Full $3 \times 3$ Cross-Qubit Correlation Matrix $\Delta(B_i \mid A_j)$:**
  - $Q_{48}$ response: $-0.00015$ (from $A_{48}$), $+0.00021$ (from $A_{49}$), $+0.00021$ (from $A_{50}$)
  - $Q_{49}$ response: $-0.00075$ (from $A_{48}$), $+0.00104$ (from $A_{49}$), $-0.00109$ (from $A_{50}$)
  - $Q_{50}$ response: $+0.00001$ (from $A_{48}$), $+0.00061$ (from $A_{49}$), $-0.00020$ (from $A_{50}$)
  - All cross-qubit and parity correlations ($\Delta_{\text{parity}} = +0.00022$) are strictly within shot noise.

### 🛡️ Positive Control: Reset Infidelity of ~1.5%, Decaying with T1, as Expected

The positive control was explicitly preregistered to verify measurement sensitivity to small residual excitations on the physical qubits. Active reset microwave pulses leave a well-documented hardware imperfection of $\sim 1.5\%$ excited-state population that decays according to textbook Markovian thermalization:
* **In-situ Reset Inaccuracy ($\tau \le 20\ \mu\text{s}$):**
  - $\tau = 0\ \mu\text{s}$ (immediately post-reset): **$+1.48\%$ excess $|1\rangle$ population** when prior state was $|1\rangle$ vs $|0\rangle$ (mean $d_k = +0.01476$, one-sided sign-flip permutation **$p = 0.000005 < 0.01$**).
  - $\tau = 20\ \mu\text{s}$ (delayed readout): **$+1.25\%$ excess population** (mean $d_k = +0.01255$, **$p = 0.000005$**).
  - **Verdict on Control:** Passed. The apparatus successfully detects sub-percent excited state persistence on microsecond scales.
* **Decay Lifetime Sweep ($\tau \in [0, 500\ \mu\text{s}]$, job `dbnbt9c4148s7390mt0g`):**
  - $\tau = 0\ \mu\text{s} \to +1.06\%$, $2\ \mu\text{s} \to +1.35\%$, $10\ \mu\text{s} \to +1.35\%$, $50\ \mu\text{s} \to +0.98\%$, $100\ \mu\text{s} \to +0.86\%$, $200\ \mu\text{s} \to +0.42\%$, $500\ \mu\text{s} \to +0.057\%$.
  - Single-exponential fit yields relaxation lifetime **$T_{\text{mem}} = 232.33\ \mu\text{s}$**, in exact quantitative agreement with the physical transmon relaxation lifetime $T_1 \approx 200 - 250\ \mu\text{s}$ on `ibm_kingston`.
  - This confirms that intra-circuit residual signal is standard $T_1$ transmon relaxation following reset infidelity, which completely thermalizes to vacuum within milliseconds.

---

## 🛰️ Spatial Cavity-Field Ramsey Phase Probe

To test whether the surrounding electromagnetic field (cavity resonator / coupling bus) retains residual coherent phase information, we deployed an in-situ **Ramsey Quantum Phase Magnetometer** on spectator sensor $Q_{49}$ while pumping/resetting adjacent source $Q_{48}$ across a $10\ \mu\text{s}$ exposure window.

* **Preregistration:** [`docs/PREREGISTRATION-spatial_ramsey_probe.md`](docs/PREREGISTRATION-spatial_ramsey_probe.md)
* **Results (`ibm_kingston`, job `dbnbvrtt7fqc73ajaigg`, 4096 shots):**
  - Sensor Visibility: $V_{\text{vacuum}} = 0.9205$ ($R^2 = 0.9997$), $V_{\text{pumped}} = 0.9195$ ($R^2 = 0.9997$).
  - Measured Spatial Phase Shift: **$\Delta\Phi = +0.00634\text{ rad} = +0.36^\circ \pm 0.62^\circ$** ($\pm 0.01078\text{ rad}$).
* **Verdict:** **H0 CONFIRMED** — the differential phase shift induced on the spatial sensor is strictly within the $1\sigma$ shot noise envelope ($|\Delta\Phi| < 3\sigma$). The inter-qubit spatial field displays zero measurable coherent AC Stark displacement post-reset.

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
