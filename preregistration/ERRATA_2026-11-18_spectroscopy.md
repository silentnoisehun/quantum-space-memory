# Erratum: Spatial Bath Spectroscopy Statistical Recount and Preregistered Threshold Restoration

**Date:** 2026-11-18, 16:50 UTC (17:50 Budapest)  
**Author:** Maya & Máté Róbert (Silent Coder Labs)  
**Repository:** `quantum-space-memory`  
**Base Commit:** `7bdc94e`  
**Target Execution:** Spatial Bath Spectroscopy, job `dbnc6ooqtr0c73acp00g` on `ibm_kingston` (Q48/Q49/Q50, 92 circuits × 4096 shots).  
**Raw Results:** `measurement_raw/spatial_bath_spectroscopy/20261107T062103Z/raw_results.json`  

---

## 1. Context & Motivation

A comprehensive audit of the spatial bath spectroscopy analysis revealed several statistical inconsistencies and post-hoc criteria modifications in earlier commits:
1. **Misleading `curve_fit` Errors in Commit `b307af6`:** Phase uncertainties were extracted from standard covariance estimates of a 3-parameter cosine model fitted on 4 data points ($\text{df} = 1$). Across identical 4096-shot circuits, these estimated errors fluctuated between $0.11^\circ$ and $1.22^\circ$, representing fit residual instability rather than true binomial shot noise.
2. **Post-Hoc Decision Threshold Alteration in Commit `66ff7a2`:** The decision rules were modified after data inspection (requiring $\max \Delta\Phi > 5^\circ$ and average criteria, widening positive control from $5^\circ$ to $6^\circ$, and lowering $R^2$ from 0.95 to 0.90). Although the declared verdict was $H_0$, it relied on unpreregistered post-hoc criteria.
3. **Protocol 2 (Dielectric TLS Dephasing) Transpilation Cancellation:** In Protocol 2 ($T_2^*$), the $s=1$ branch placed 10 $X$ gates on $Q_{48}$. Because an even number of Pauli $X$ gates reduces to identity, `transpile(..., optimization_level=1)` completely pruned them. As a result, both the $s=0$ (vacuum) and $s=1$ (pumped) branches executed identical quantum circuits (an A/A test). The prior claim that "TLS contrast curves match within shot noise" was an artifact of identity cancellation and is formally retracted.
4. **Protocol 3 (CPMG-4) Static Coupling Confound:** In Protocol 3, $Q_{48}$ was initialized in $|1\rangle$ without reset during spectator decoupling. Any observable difference would reflect static $Q_{48}$–$Q_{49}$ $ZZ$ cross-talk, not residual post-reset bath memory.
5. **Preregistration Significance Threshold Ambiguity:** The original preregistration [`docs/PREREGISTRATION-spatial_bath_spectroscopy.md`](../docs/PREREGISTRATION-spatial_bath_spectroscopy.md) simultaneously specified "$3\sigma$" and "$\alpha = 0.01$". Note that two-sided $3\sigma$ corresponds to $p \approx 0.0027$ ($z = 3.0$), while $\alpha = 0.01$ corresponds to $z = 2.58$.

---

## 2. Corrected Statistical Analysis & Decision Rule

All statistical errors have been recomputed from the original 4096-shot raw counts using:
- **Parametric Binomial Bootstrap:** 20,000 resamples (seed `20261118`) for fringe phases, positive control, and CPMG visibilities; 2,000 resamples for exponential $T_2^*$ fits.
- **Stratified Hypergeometric Permutation:** 200,000 draws for population bias across projection angles.
- **Strict Restoration of Preregistered Decision Rules:**
  - Positive control must satisfy $|\Delta\Phi_{\text{injected}} - 45^\circ| < 5.0^\circ$ and $R^2 > 0.95$. Otherwise declared **INCONCLUSIVE**.
  - $H_1$ requires at least one preregistered test reaching $|z| \ge 3.0$. Otherwise declared **$H_0$**.
- Output stored separately in `measurement_raw/spatial_bath_spectroscopy/20261107T062103Z/analysis_prereg.json` without overwriting historical files.

---

## 3. Recalculated Experimental Results

* **In-situ Positive Control:**
  - Measured injected phase: $+49.27^\circ \pm 0.95^\circ$ (target $45^\circ$, deviation $+4.27^\circ$).
  - Fit quality: $R^2 = 0.9999$.
  - Status: **PASSED** ($|\text{deviation}| < 5^\circ$, $R^2 > 0.95$).
  - *Note:* P4 calibration circuits lack active reset on $Q_{48}$ whereas P1 reference contains reset; the $+4.27^\circ$ offset may include reset-induced phase.
* **Protocol 1 (Spatial Phase & Population):**
  - Largest phase shift: $\Delta\Phi = -4.07^\circ \pm 1.45^\circ$ at $\tau = 50\ \mu\text{s}$ ($z = -2.81$, uncorrected $p = 0.005$). All other delays yield $|z| \le 2.22$.
  - Population bias: $|\Delta P_1| \le 0.0076$ across all delays, with all stratified permutation $p \ge 0.16$.
  - Exploratory constant offset (non-preregistered): $-1.89^\circ \pm 0.50^\circ$ across all $\tau$ (constant fit $\chi^2 = 3.87$, $\text{df} = 4$). Consistent with microwave active reset cross-talk; does not grow with delay.
* **Protocol 2 (Dielectric TLS Dephasing):**
  - $\Delta T_2^* = -2.2 \pm 3.5\ \mu\text{s}$ ($z = -0.61$). Invalid test due to compiler identity cancellation.
* **Protocol 3 (CPMG-4 AC Noise Decoupling):**
  - Largest contrast deviation: $\Delta V = +0.040 \pm 0.014$ at $T_{\text{total}} = 80\ \mu\text{s}$ ($z = +2.89$, uncorrected $p = 0.004$). For all other $T_{\text{total}}$, $|z| \le 1.27$.
* **Overall Verdict:**
  - Preregistered $3\sigma$ rule: Max $|z| = 2.89 < 3.0$. **$H_0$ CONFIRMED (Boundary case).**
  - Multiple testing: Holm-Bonferroni correction across all 15 tests yields minimum corrected $p = 0.057 > 0.05$.
  - If interpreted under uncorrected $\alpha = 0.01$, $\tau = 50\ \mu\text{s}$ phase and $T = 80\ \mu\text{s}$ CPMG would marginally exceed threshold. Under both $3\sigma$ and multiple testing corrections, textbook Markovian physics ($H_0$) holds.

---

## 4. Verification & Testing

A new test suite [`tests/test_spectroscopy_prereg.py`](../tests/test_spectroscopy_prereg.py) has been added with 7 dedicated test cases verifying:
1. Synthetic null effect yields $H_0$.
2. Injected $12^\circ$ phase shift yields $H_1$.
3. Corrupted positive control yields $INCONCLUSIVE$.
4. Preregistered decision boundaries ($5^\circ$, $R^2 = 0.95$, $3\sigma$).
5. Exact reproduction of all Kingston recalculated numbers.
6. Identity cancellation in Protocol 2 under `FakeKingston`.
7. $\alpha = 0.01$ vs $3\sigma$ ambiguity and Holm correction.
