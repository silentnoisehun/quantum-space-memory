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

## 🔬 Spatial Bath & Substrate Spectroscopy (`dbnc6ooqtr0c73acp00g`)

Comprehensive 92-circuit spectroscopy on `ibm_kingston` (Heron r2) evaluating spatial phase imprint, dielectric two-level defect (TLS) dephasing ($T_2^*$), and CPMG-4 dynamical decoupling AC noise filtering:
* **Preregistration:** [`docs/PREREGISTRATION-spatial_bath_spectroscopy.md`](docs/PREREGISTRATION-spatial_bath_spectroscopy.md) (uploaded 2026-11-07 06:18 UTC, preceding run at 06:21 UTC).
* **In-situ Positive Control:** Injected calibrated $R_z(\pi/4) = +45.0^\circ$ phase shift resolved to **$+49.27^\circ \pm 0.95^\circ$** (target $45^\circ$, deviation $+4.27^\circ$, $R^2 = 0.9999$). Control passed under preregistered rule ($|\text{deviation}| < 5^\circ$, $R^2 > 0.95$). *Note:* P4 circuits omit active reset on $Q_{48}$ while P1 baseline includes reset, so the residual $+4.27^\circ$ offset may include reset-induced phase.
* **Findings (Recomputed via Parametric Binomial Bootstrap & Permutation):**
  - **Protocol 1 (Spatial Phase Imprint):** Largest phase deviation observed at $\tau = 50\ \mu\text{s}$: $\Delta\Phi = -4.07^\circ \pm 1.45^\circ$ ($z = -2.81$, uncorrected $p = 0.005$). Across all other delays, $|z| \le 2.22$.
  - **Protocol 1 (Population Tomography):** Spectator population bias across all delays is bounded below $0.8\%$ ($|\Delta P_1| \le 0.0076$), with all stratified permutation tests yielding $p \ge 0.16$ (200,000 draws).
  - **Protocol 1 (Exploratory / Non-Preregistered):** Delay-independent phase offset of $-1.89^\circ \pm 0.50^\circ$, present already at $\tau = 0\ \mu\text{s}$ (constant model $\chi^2 = 3.87$, $\text{df} = 4$). Consistent with microwave active reset crosstalk from adjacent $Q_{48}$; does not accumulate over time and is not a spatial memory signal.
  - **Protocol 2 (Dielectric TLS Bath Dephasing):** $\Delta T_2^* = -2.2 \pm 3.5\ \mu\text{s}$ ($z = -0.61$). *Correction:* The earlier claim that "TLS contrast curves match within shot noise" is retracted as evidence of physical invariance. Protocol 2's $s=1$ branch placed 10 $X$ gates on $Q_{48}$; an even number of $X$ gates is identity, which `transpile(..., optimization_level=1)` completely eliminates. Both branches compiled into identical circuits (an A/A test), providing no probe of substrate TLS saturation.
  - **Protocol 3 (CPMG-4 AC Noise Filtering):** Largest visibility deviation observed at $T_{\text{total}} = 80\ \mu\text{s}$: $\Delta V = +0.040 \pm 0.014$ ($z = +2.89$, uncorrected $p = 0.004$). For all other filter times, $|z| \le 1.27$. *Note:* In Protocol 3, $Q_{48}$ was left in $|1\rangle$ without reset during spectator interrogation, so any physical effect would reflect static $Q_{48}$–$Q_{49}$ $ZZ$ cross-talk coupling, not post-reset vacuum memory.
* **Preregistered Ambiguity & Verdict:**
  - The frozen preregistration simultaneously stated a $3\sigma$ threshold and $\alpha = 0.01$ ($3\sigma$ two-sided corresponds to $p \approx 0.0027$; $\alpha = 0.01$ corresponds to $z = 2.58$). Under an uncorrected $\alpha = 0.01$ reading, the $\tau = 50\ \mu\text{s}$ phase shift ($p = 0.005$) and $T = 80\ \mu\text{s}$ CPMG contrast ($p = 0.004$) would independently exceed threshold.
  - Under the strictly preregistered $3\sigma$ decision rule ($|z| \ge 3.0$), no test passes (maximum $|z| = 2.89 < 3.0$).
  - Across all 15 preregistered tests, Holm-Bonferroni family-wise error correction yields a minimum adjusted $p = 0.057 > 0.05$.
  - **Verdict:** **$H_0$ CONFIRMED (Marginal / Boundary Case: max $|z| = 2.89 < 3.0$; Holm min $p = 0.057$). Standard quantum mechanics and Markovian vacuum thermalization hold.** Future preregistrations will specify a single unambiguous significance threshold.
* **Erratum Notice (2026-11-18):** Replaced post-hoc decision thresholds from commit `66ff7a2` with the original preregistered rules, replaced single-degree-of-freedom `curve_fit` errors with parametric binomial bootstrap errors, retracted Protocol 2 TLS conclusion due to compiler identity cancellation, and added analysis script `scripts/analyze_spatial_spectroscopy_prereg.py`. Detailed log in [`preregistration/ERRATA_2026-11-18_spectroscopy.md`](preregistration/ERRATA_2026-11-18_spectroscopy.md).

---

## ☁️ Zero IQ Memory: Looking Inside the 0-Cloud (`20261107T073452Z`)

Direct interrogation of continuous raw IQ readout voltages to detect sub-bit ground-state displacement across independent jobs on `ibm_kingston` (Heron r2):
* **Preregistration:** [`docs/PREREGISTRATION-zero_iq_memory.md`](docs/PREREGISTRATION-zero_iq_memory.md) (Script: `scripts/zero_iq_memory.py`)
* **Execution:** Exactly **40 complete pairs** (80 jobs, 1024 shots/circuit, kerneled IQ data) executed with 100% bit classification accuracy in Job A ($A_{\text{correct}} = 1.0$).
* **Positive Control:** In-situ reset imperfection detected with **$\bar{d} = +0.0188$ ($p = 0.000005 < 0.01$)**, confirming sub-percent IQ cloud sensitivity.
* **Primary Result:** Ground-state cloud centroid shift along the $0 \to 1$ axis:
  $$\Delta = -0.00069,\quad p_{\text{two-sided}} = 0.5546 \gg 0.01$$
  - Null standard deviation: $\sigma_{\text{null}} = 0.00115$ (observed $|\Delta| < 0.6\sigma$).
  - Job-to-job drift-corrected and raw axes are identically consistent with zero ($p = 0.85$ and $p = 0.22$).
* **Verdict:** **H0 CONFIRMED / H1 NOT SUPPORTED.** The continuous ground-state IQ distribution retains zero sub-bit displacement from the prior job's preparation. Textbook Markovian reset holds down to the raw analog microwave level.

---

## ⚡ Zero IQ Energy-Matched Control (`20261107T075634Z`)

Energy-matched control removing drive energy asymmetry between $s=1$ ($SX, SX$) and $s=0$ ($SX, SX^\dagger$) with verified physical pulse counts (2 physical pulses/qubit, `optimization_level=0`):
* **Preregistration:** [`docs/PREREGISTRATION-zero_iq_energy_matched.md`](docs/PREREGISTRATION-zero_iq_energy_matched.md) (Script: `scripts/zero_iq_energy_matched.py`, seed `20261112`)
* **Execution:** Exactly **40 complete pairs** (80 jobs, 1024 shots/circuit, kerneled IQ data) with 100% bit classification accuracy in Job A ($A_{\text{correct}} = 1.0$) and verified pulse execution ($[2, 2, 2]$ physical pulses per qubit).
* **Positive Control:** Reset imperfection detected with **$\bar{d} = +0.0175$ ($p = 0.000005 < 0.01$)**, confirming high detector sensitivity.
* **Primary Result:** Ground-state cloud centroid shift along the $0 \to 1$ axis:
  $$\Delta = -0.00135,\quad p_{\text{two-sided}} = 0.2862 \gg 0.01$$
  - Null standard deviation: $\sigma_{\text{null}} = 0.00127$ (observed $|\Delta| \approx 1.06\sigma$, strictly within shot noise).
  - Secondary metrics: $y$-shift $p = 0.49$, width $w_0$ $p = 0.99$, excited fraction $p = 1.00$.
* **Verdict:** **H0 CONFIRMED / H1 NOT SUPPORTED.** Equalized microwave pulse energy produces an independent, confirmed null result on an independent seed, definitively ruling out both qubit-state and drive-energy cross-job ground-cloud memory.

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
