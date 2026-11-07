# Preregistration: Comprehensive Spatial Field & Substrate Bath Memory Spectroscopy

**Registration Date:** 2026-11-07T06:20:00Z  
**Author:** Máté Róbert (Rongyász)  
**Hardware:** `ibm_kingston` (Heron r2, 156 qubits)  
**Target Transmon Chain:** $Q_{48}$ (Source / Field Pump) — $Q_{49}$ (Primary Spatial Sensor / Spectator) — $Q_{50}$ (Distant Spatial Sensor)  

---

## 1. Scientific Objective

To experimentally test whether the physical spatial environment surrounding superconducting transmons (including the dielectric substrate two-level defect bath, coupling buses, and package electromagnetic modes) retains physical information about quantum states previously prepared on a source qubit ("Memory in Space").

Specifically, we test whether encoding an excitation / quantum state into source qubit $Q_{48}$ imprints persistent, retrievable information onto the quantum state or coherence dynamics of adjacent spectator qubit $Q_{49}$ located in the adjacent physical space.

---

## 2. Hypotheses & Preregistered Decision Rules

### Hypotheses
* **$H_0$ (Standard Markovian Open System & Thermalized Vacuum):**
  The spatial field and substrate retain zero measurable memory of the prior state of $Q_{48}$. The observables of spectator $Q_{49}$ (phase $\Phi$, population $P_1$, dephasing time $T_2^*$, and dynamical decoupling coherence $V_{\text{CPMG}}$) are statistically indistinguishable under source vacuum ($s=0$) versus source preparation ($s=1$):
  $$\Delta P_1 = 0,\quad \Delta\Phi = 0,\quad \Delta T_2^* = 0,\quad \Delta V_{\text{CPMG}} = 0$$

* **$H_1$ (Persistent Spatial Memory / Bath Imprint):**
  Information from the preparation of $Q_{48}$ persists in the spatial medium, producing a statistically significant deviation in the spectator observables:
  - Phase shift: $|\Delta\Phi| \ge 3\sigma_{\Phi}$
  - Population bias: $|\Delta P_1| \ge 3\sigma$ with $p < 0.01$ (two-sided permutation)
  - Dephasing modulation: $|\Delta T_2^*| \ge 3\sigma$
  - CPMG AC noise filter dip: $\Delta V_{\text{CPMG}} \ge 3\sigma$

### Decision Threshold
* **Statistical Significance:** $\alpha = 0.01$ ($3\sigma$ confidence level).
* **Control Requirement:** Positive control ($R_z(\pi/4)$ calibration circuit) must yield $|\Phi_{\text{meas}} - 45^\circ| < 5^\circ$ with $R^2 > 0.95$. If the positive control fails, the run is declared **INCONCLUSIVE**.

---

## 3. Experimental Protocols (Unified Batch Execution)

The experiment is compiled into a single unified batch of circuits executed with 4096 shots per circuit on `ibm_kingston`.

### Protocol 1: Spatial Phase & Population Tomography
* **Source $Q_{48}$:** Prepared in $s \in \{0, 1\}$ (vacuum $|0\rangle$ vs state $|1\rangle$), followed by active reset `reset(48)`.
* **Spectator $Q_{49}$:** Interrogated via Ramsey tomography:
  $$R_x(\pi/2) \to \text{Delay } \tau \in \{0, 10, 25, 50, 100\ \mu\text{s}\} \to R_z(\theta) \to R_x(\pi/2)$$
  with tomographic projection angles $\theta \in \{0, \pi/2, \pi, 3\pi/2\}$.
* **Observables:** Fitted fringe amplitude $V(\tau)$ and spatial phase shift $\Delta\Phi(\tau) = \Phi(s=1) - \Phi(s=0)$.

### Protocol 2: Dielectric Substrate TLS Bath Dephasing ($T_2^*$)
* **Source $Q_{48}$:** Driven with a high-intensity saturation pulse train ($10 \times X$ gates) to maximize energy transfer into resonant substrate two-level defects (TLS) vs. idle vacuum.
* **Spectator $Q_{49}$:** Ramsey free induction decay measured across 8 delays:
  $$\tau \in \{2, 10, 25, 50, 75, 100, 150, 200\ \mu\text{s}\}$$
* **Observables:** Decay envelopes $P_1(\tau \mid \text{vacuum})$ vs $P_1(\tau \mid \text{saturated})$. Extracted dephasing times $T_{2,\text{vac}}^*$ vs $T_{2,\text{sat}}^*$.

### Protocol 3: CPMG-4 Dynamical Decoupling AC Noise Spectroscopy
* **Spectator $Q_{49}$:** Interrogated with a 4-pulse Carr-Purcell-Meiboom-Gill sequence:
  $$R_x(\pi/2) - [\tau/2 - X - \tau - X - \tau - X - \tau - X - \tau/2] - R_x(\pi/2)$$
  filtering AC environmental noise at sampling frequency $f_{\text{filter}} = 1/(4\tau)$.
* **Delays:** Total interrogation time $T_{\text{total}} = 4\tau \in \{10, 20, 40, 80\ \mu\text{s}\}$.
* **Observables:** Coherence retention under $Q_{48}$ modulation.

### Protocol 4: Positive Control
* Exact calibrated $R_z(\pi/4)$ phase rotation applied to $Q_{49}$ during Ramsey evolution to independently guarantee phase sensitivity.

---

## 4. Hardware Parameters & Target Setup

* **Backend:** `ibm_kingston` (Heron r2)
* **Qubits:** $Q_{48}$ (Source), $Q_{49}$ (Center Spectator), $Q_{50}$ (Distant Spectator)
* **Coupling Edges:** $(48, 49)$, $(49, 50)$
* **Target Calibration:** $T_1(Q_{49}) = 197.1\ \mu\text{s}$, $T_2(Q_{49}) = 94.5\ \mu\text{s}$
* **Shots:** 4096 shots per circuit
