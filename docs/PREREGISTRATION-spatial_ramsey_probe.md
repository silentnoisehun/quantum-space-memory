# Preregistration: Spatial Cavity-Field Ramsey Phase Probe on Superconducting Transmons

**Author:** Máté Róbert (ORCID: [0009-0003-3986-6039](https://orcid.org/0009-0003-3986-6039))  
**Repository:** `https://github.com/silentnoisehun/quantum-space-memory`  
**Date of registration:** 2026-11-07 06:06:00 UTC (commit prior to hardware execution)  

---

## 1. Scientific Objective & Rationale

Previous longitudinal ($Z$-axis) population tests showed that on macroscopic timescales ($t \ge 84\ \text{ms}$), discrete transmon states thermalize to ground. However, standard projective $Z$-measurements are fundamentally blind to:
1. Coherent electromagnetic field displacements in the surrounding microwave resonator / coupling bus cavity;
2. Spatial dispersive AC Stark shifts induced by non-equilibrium photon populations in the inter-qubit space;
3. Transverse phase accumulation $\Delta\Phi$ across the equatorial plane of the Bloch sphere.

To test whether the **surrounding space** (cavity / bus field) retains physical information after an active reset, we employ an unaddressed spectator transmon as an in-situ **Ramsey Quantum Phase Magnetometer**.

---

## 2. Experimental Design

- **Backend:** `ibm_kingston` (156-qubit Heron r2).
- **Physical Layout:**
  - **Source Transmon (Pump):** $Q_{48}$.
  - **Spatial Probe Transmon (Field Sensor):** $Q_{49}$ (directly coupled to $Q_{48}$ via physical coupling bus).
  - **Distance Control:** $Q_{50}$ (next-neighbor sensor).
- **Circuit Sequence:**
  1. Spatial Sensor ($Q_{49}$) is placed on the Bloch sphere equator via $R_x(\pi/2)$.
  2. Source ($Q_{48}$) executes one of two conditions:
     - **Arm P (Pumped):** $X(Q_{48}) \to \text{Measure} \to \text{Reset}(Q_{48})$.
     - **Arm V (Vacuum Baseline):** $I(Q_{48}) \to \text{Measure} \to \text{Reset}(Q_{48})$.
  3. Space Exposure Delay: $\tau = 10\ \mu\text{s}$ (where earlier decay sweeps showed $+1.35\%$ persistent memory).
  4. Phase Tomography on Sensor ($Q_{49}$):
     $$R_z(-\phi) \to R_x(\pi/2) \to \text{Measure}(Q_{49})$$
     probed across 8 tomographic angles:
     $$\phi_k \in \left\{ 0, \; \frac{\pi}{4}, \; \frac{\pi}{2}, \; \frac{3\pi}{4}, \; \pi, \; \frac{5\pi}{4}, \; \frac{3\pi}{2}, \; \frac{7\pi}{4} \right\}$$
- **Total Circuits:** 8 angles $\times$ 2 arms = 16 circuits in a single batch job.
- **Shots:** 4096 shots per circuit (shot noise floor $\sigma \approx 0.0078$).
- **Script:** `scripts/spatial_ramsey_probe.py`.

---

## 3. Mathematical Models & Primary Metric

For each arm (Pumped vs Vacuum), the sensor probability oscillates as a Ramsey fringe:
$$P_1(\phi) = \frac{1 - V \cos(\phi - \Phi)}{2}$$
where $V$ is fringe visibility and $\Phi$ is the accumulated phase offset.

### Primary Metric: Spatial Phase Shift
$$\Delta\Phi = \Phi_{\text{Pumped}} - \Phi_{\text{Vacuum}}$$

- **$H_0$ (Standard Memoryless Cavity Reset):** The active reset instantaneously depopulates all microwave modes. The spectator transmon accumulates zero differential phase shift:
  $$\Delta\Phi = 0$$
- **$H_1$ (Persistent Field Memory in Space):** Residual cavity photons or bus excitations induce a non-zero dispersive AC Stark shift on the sensor:
  $$\Delta\Phi = 2 \bar{n} \chi \tau \neq 0$$

### Decision Rule
$H_1$ (Spatial Field Memory) is supported if:
1. Both Ramsey fringes have fit visibility $V > 0.50$ ($R^2 > 0.90$);
2. $|\Delta\Phi| > 3 \sigma_\Phi$ and $|\Delta\Phi| > 0.05\text{ rad}$ ($> 2.8^\circ$);
3. Permutation shuffle $p$-value $< 0.01$.
Otherwise, $H_0$ stands.
