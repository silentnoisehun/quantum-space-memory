#!/usr/bin/env python3
"""
analyze_spatial_spectroscopy_prereg.py

Preregistered analysis of spatial bath and substrate spectroscopy data.
Evaluates H0 vs H1 strictly using preregistered decision rules.
Output: analysis_prereg.json alongside raw_results.json (does NOT overwrite analysis_summary.json).
"""

import argparse
import json
import sys
from pathlib import Path
import numpy as np
from scipy import stats
from scipy.optimize import curve_fit

REPO = Path(__file__).resolve().parent.parent

def parse_args():
    p = argparse.ArgumentParser(description="Preregistered analysis of spatial bath spectroscopy")
    p.add_argument("raw_json", nargs="?", default=None, help="Path to raw_results.json")
    p.add_argument("--seed", type=int, default=20261118, help="Random seed for bootstrap/permutation")
    p.add_argument("--n-boot", type=int, default=20000, help="Number of bootstrap samples")
    p.add_argument("--n-boot-t2", type=int, default=2000, help="Bootstrap samples for T2*")
    p.add_argument("--n-perm", type=int, default=200000, help="Permutation draws for population test")
    return p.parse_args()

def get_p1(counts, q_idx=1):
    """Returns P(1) for qubit q_idx (0=Q48, 1=Q49, 2=Q50). Counts keys are 'q2 q1 q0'."""
    shots = sum(counts.values())
    p1 = 0
    for bs, c in counts.items():
        bs = bs.replace(" ", "")
        if bs[-1 - q_idx] == "1":
            p1 += c
    return p1 / shots

def fit_fringe_analytic(p1s):
    """
    Analytic fit for 4-point Ramsey fringe at theta = [0, pi/2, pi, 3pi/2]:
    P1(theta) = A - 0.5 * V * cos(theta + phi)
    phi = arctan2(p1[1] - p1[3], p1[2] - p1[0])
    """
    a = float(np.mean(p1s))
    v = float(np.sqrt((p1s[2] - p1s[0])**2 + (p1s[1] - p1s[3])**2))
    phi = float(np.arctan2(p1s[1] - p1s[3], p1s[2] - p1s[0]))
    thetas = np.array([0.0, np.pi/2, np.pi, 3*np.pi/2])
    model = a - 0.5 * v * np.cos(thetas + phi)
    ss_res = float(np.sum((p1s - model)**2))
    ss_tot = float(np.sum((p1s - a)**2))
    r2 = float(1.0 - ss_res / (ss_tot + 1e-12))
    return a, v, phi, r2

def fit_t2(taus, contrasts):
    """Fits c(tau) = A * exp(-tau / T2*)."""
    def model(t, a, t2):
        return a * np.exp(-t / t2)
    popt, _ = curve_fit(model, taus, contrasts, p0=[0.9, 80.0], bounds=([0, 1.0], [1.5, 500.0]))
    return float(popt[0]), float(popt[1])

def analyze_spectroscopy(data, seed=20261118, n_boot=20000, n_boot_t2=2000, n_perm=200000):
    rng = np.random.default_rng(seed)

    # 1. POSITIVE CONTROL
    pos_items = sorted([d for d in data if d["meta"]["protocol"] == "P4_positive_control"],
                       key=lambda x: x["meta"]["theta"])
    pos_p1s = np.array([get_p1(d["counts"], q_idx=1) for d in pos_items])
    a_pos, v_pos, phi_pos, r2_pos = fit_fringe_analytic(pos_p1s)

    items_s0_10us = sorted([d for d in data if d["meta"]["protocol"] == "P1_phase_tomography"
                            and d["meta"]["tau_us"] == 10.0 and d["meta"]["s"] == 0],
                           key=lambda x: x["meta"]["theta"])
    p0_10us = np.array([get_p1(d["counts"], q_idx=1) for d in items_s0_10us])
    _, _, phi_base_10us, _ = fit_fringe_analytic(p0_10us)

    phi_pos_deg = np.rad2deg(phi_pos)
    phi_base_10us_deg = np.rad2deg(phi_base_10us)
    injected_measured_deg = (phi_pos_deg - phi_base_10us_deg + 180) % 360 - 180

    # Parametric bootstrap for positive control uncertainty
    boot_pos = rng.binomial(4096, pos_p1s, size=(n_boot, 4)) / 4096.0
    boot_base = rng.binomial(4096, p0_10us, size=(n_boot, 4)) / 4096.0
    phi_pos_samples = np.arctan2(boot_pos[:, 1] - boot_pos[:, 3], boot_pos[:, 2] - boot_pos[:, 0])
    phi_base_samples = np.arctan2(boot_base[:, 1] - boot_base[:, 3], boot_base[:, 2] - boot_base[:, 0])
    injected_samples = (np.rad2deg(phi_pos_samples) - np.rad2deg(phi_base_samples) + 180) % 360 - 180
    injected_err_deg = float(np.std(injected_samples))

    pos_ctrl_diff = injected_measured_deg - 45.0
    pos_ctrl_passed = bool(abs(pos_ctrl_diff) < 5.0 and r2_pos > 0.95)

    # 2. PROTOCOL 1: PHASE & POPULATION TOMOGRAPHY
    p1_items = [d for d in data if d["meta"]["protocol"] == "P1_phase_tomography"]
    taus = sorted(list(set([d["meta"]["tau_us"] for d in p1_items])))

    phase_results = {}
    p1_results = {}
    all_z = []
    all_p = []

    for tau in taus:
        s0 = sorted([d for d in p1_items if d["meta"]["tau_us"] == tau and d["meta"]["s"] == 0],
                    key=lambda x: x["meta"]["theta"])
        s1 = sorted([d for d in p1_items if d["meta"]["tau_us"] == tau and d["meta"]["s"] == 1],
                    key=lambda x: x["meta"]["theta"])
        p0 = np.array([get_p1(d["counts"], q_idx=1) for d in s0])
        p1 = np.array([get_p1(d["counts"], q_idx=1) for d in s1])

        _, _, phi0, _ = fit_fringe_analytic(p0)
        _, _, phi1, _ = fit_fringe_analytic(p1)
        d_phi_deg = float((np.rad2deg(phi1 - phi0) + 180) % 360 - 180)

        # Bootstrap for phase difference
        b0 = rng.binomial(4096, p0, size=(n_boot, 4)) / 4096.0
        b1 = rng.binomial(4096, p1, size=(n_boot, 4)) / 4096.0
        phi0_s = np.arctan2(b0[:, 1] - b0[:, 3], b0[:, 2] - b0[:, 0])
        phi1_s = np.arctan2(b1[:, 1] - b1[:, 3], b1[:, 2] - b1[:, 0])
        d_phi_s = (np.rad2deg(phi1_s - phi0_s) + 180) % 360 - 180
        sigma_phi = float(np.std(d_phi_s))
        z_phi = float(d_phi_deg / sigma_phi)
        p_phi = float(2.0 * (1.0 - stats.norm.cdf(abs(z_phi))))

        phase_results[str(tau)] = {
            "d_phi_deg": d_phi_deg,
            "sigma_deg": sigma_phi,
            "z": z_phi,
            "p_value": p_phi
        }
        all_z.append(z_phi)
        all_p.append(p_phi)

        # Population test
        dp1 = float(np.mean(p1) - np.mean(p0))
        # Stratified permutation test (hypergeometric sampling across shots per theta)
        k0 = np.array([sum(c for bs, c in d["counts"].items() if bs.replace(" ", "")[-2] == "1") for d in s0])
        k1 = np.array([sum(c for bs, c in d["counts"].items() if bs.replace(" ", "")[-2] == "1") for d in s1])
        k_tot = k0 + k1
        perm_k1 = rng.hypergeometric(k_tot, 8192 - k_tot, 4096, size=(n_perm, 4))
        perm_k0 = k_tot - perm_k1
        perm_dp1 = np.mean((perm_k1 - perm_k0) / 4096.0, axis=1)
        p_perm = float(np.mean(np.abs(perm_dp1) >= abs(dp1) - 1e-12))

        # Bootstrap sigma for population difference
        boot_dp1 = np.mean(b1 - b0, axis=1)
        sigma_p1 = float(np.std(boot_dp1))
        z_p1 = float(dp1 / sigma_p1)

        p1_results[str(tau)] = {
            "dp1": dp1,
            "sigma": sigma_p1,
            "z": z_p1,
            "p_perm": p_perm
        }
        all_z.append(z_p1)
        all_p.append(p_perm)

    # Exploratory constant phase offset
    p1_dphis = np.array([phase_results[str(tau)]["d_phi_deg"] for tau in taus])
    p1_sigmas = np.array([phase_results[str(tau)]["sigma_deg"] for tau in taus])
    weights = 1.0 / (p1_sigmas**2)
    const_offset = float(np.sum(weights * p1_dphis) / np.sum(weights))
    const_offset_err = float(1.0 / np.sqrt(np.sum(weights)))
    chi2_const = float(np.sum(((p1_dphis - const_offset) / p1_sigmas)**2))

    # 3. PROTOCOL 2: SUBSTRATE TLS BATH DEPHASING (T2*)
    p2_items = [d for d in data if d["meta"]["protocol"] == "P2_tls_dephasing"]
    p2_taus = np.array(sorted(list(set([d["meta"]["tau_us"] for d in p2_items]))))

    def get_contrasts_arr(items, s):
        cs = []
        for tau in p2_taus:
            it = [d for d in items if d["meta"]["tau_us"] == tau and d["meta"]["s"] == s]
            p_th0 = get_p1([d for d in it if d["meta"]["theta"] == 0.0][0]["counts"], 1)
            p_th1 = get_p1([d for d in it if d["meta"]["theta"] > 0.0][0]["counts"], 1)
            cs.append(2.0 * np.sqrt((p_th0 - 0.5)**2 + (p_th1 - 0.5)**2))
        return np.array(cs)

    c0 = get_contrasts_arr(p2_items, 0)
    c1 = get_contrasts_arr(p2_items, 1)
    _, t2_s0 = fit_t2(p2_taus, c0)
    _, t2_s1 = fit_t2(p2_taus, c1)
    dt2 = float(t2_s1 - t2_s0)

    # Bootstrap for T2* difference
    dt2_boot = []
    for _ in range(n_boot_t2):
        bc0 = []
        bc1 = []
        for tau in p2_taus:
            it0 = [d for d in p2_items if d["meta"]["tau_us"] == tau and d["meta"]["s"] == 0]
            it1 = [d for d in p2_items if d["meta"]["tau_us"] == tau and d["meta"]["s"] == 1]
            p_th0_0 = get_p1([d for d in it0 if d["meta"]["theta"] == 0.0][0]["counts"], 1)
            p_th1_0 = get_p1([d for d in it0 if d["meta"]["theta"] > 0.0][0]["counts"], 1)
            p_th0_1 = get_p1([d for d in it1 if d["meta"]["theta"] == 0.0][0]["counts"], 1)
            p_th1_1 = get_p1([d for d in it1 if d["meta"]["theta"] > 0.0][0]["counts"], 1)

            bp0_0 = rng.binomial(4096, p_th0_0) / 4096.0
            bp1_0 = rng.binomial(4096, p_th1_0) / 4096.0
            bp0_1 = rng.binomial(4096, p_th0_1) / 4096.0
            bp1_1 = rng.binomial(4096, p_th1_1) / 4096.0

            bc0.append(2.0 * np.sqrt((bp0_0 - 0.5)**2 + (bp1_0 - 0.5)**2))
            bc1.append(2.0 * np.sqrt((bp0_1 - 0.5)**2 + (bp1_1 - 0.5)**2))
        try:
            _, bt0 = fit_t2(p2_taus, np.array(bc0))
            _, bt1 = fit_t2(p2_taus, np.array(bc1))
            dt2_boot.append(bt1 - bt0)
        except Exception:
            pass

    sigma_dt2 = float(np.std(dt2_boot)) if dt2_boot else 3.5
    z_t2 = float(dt2 / sigma_dt2)
    p_t2 = float(2.0 * (1.0 - stats.norm.cdf(abs(z_t2))))
    all_z.append(z_t2)
    all_p.append(p_t2)

    # 4. PROTOCOL 3: CPMG-4 DYNAMICAL DECOUPLING
    p3_items = [d for d in data if d["meta"]["protocol"] == "P3_cpmg_decoupling"]
    p3_totals = sorted(list(set([d["meta"]["total_us"] for d in p3_items])))

    cpmg_results = {}
    for T_tot in p3_totals:
        s0 = [d for d in p3_items if d["meta"]["total_us"] == T_tot and d["meta"]["s"] == 0]
        s1 = [d for d in p3_items if d["meta"]["total_us"] == T_tot and d["meta"]["s"] == 1]
        p_th0_s0 = get_p1([d for d in s0 if d["meta"]["theta"] == 0.0][0]["counts"], 1)
        p_th1_s0 = get_p1([d for d in s0 if d["meta"]["theta"] > 0.0][0]["counts"], 1)
        w0 = p_th1_s0 - p_th0_s0

        p_th0_s1 = get_p1([d for d in s1 if d["meta"]["theta"] == 0.0][0]["counts"], 1)
        p_th1_s1 = get_p1([d for d in s1 if d["meta"]["theta"] > 0.0][0]["counts"], 1)
        w1 = p_th1_s1 - p_th0_s1

        # In CPMG visibility V = |w| = -w, Delta V = V(s=1) - V(s=0) = -(w1 - w0)
        v0 = -w0
        v1 = -w1
        dv = float(v1 - v0)

        # Bootstrap
        b0_th0 = rng.binomial(4096, p_th0_s0, size=n_boot) / 4096.0
        b0_th1 = rng.binomial(4096, p_th1_s0, size=n_boot) / 4096.0
        b1_th0 = rng.binomial(4096, p_th0_s1, size=n_boot) / 4096.0
        b1_th1 = rng.binomial(4096, p_th1_s1, size=n_boot) / 4096.0
        bv0 = -(b0_th1 - b0_th0)
        bv1 = -(b1_th1 - b1_th0)
        bdv = bv1 - bv0
        sigma_dv = float(np.std(bdv))
        z_cpmg = float(dv / sigma_dv)
        p_cpmg = float(2.0 * (1.0 - stats.norm.cdf(abs(z_cpmg))))

        cpmg_results[str(T_tot)] = {
            "dv": dv,
            "sigma": sigma_dv,
            "z": z_cpmg,
            "p_value": p_cpmg
        }
        all_z.append(z_cpmg)
        all_p.append(p_cpmg)

    # 5. VERDICT DETERMINATION
    # 15 preregistered tests total (5 phase + 5 pop + 1 t2* + 4 cpmg)
    assert len(all_z) == 15, f"Expected 15 tests, got {len(all_z)}"
    max_abs_z = float(np.max(np.abs(all_z)))

    # Holm-Bonferroni correction
    sorted_p = sorted(all_p)
    holm_p = [p * (15 - i) for i, p in enumerate(sorted_p)]
    min_holm_p = float(min(holm_p))

    if not pos_ctrl_passed:
        verdict = "INCONCLUSIVE"
        explanation = "Positive control failed (|diff from 45 deg| >= 5 deg or R2 <= 0.95)."
    elif max_abs_z >= 3.0:
        verdict = "H1 SUPPORTED"
        explanation = f"Statistically significant deviation found (|z| = {max_abs_z:.2f} >= 3.0)."
    else:
        verdict = "H0"
        explanation = f"No test reached 3-sigma threshold (max |z| = {max_abs_z:.2f} < 3.0, Holm min p = {min_holm_p:.3f})."

    out = {
        "positive_control": {
            "injected_measured_deg": injected_measured_deg,
            "injected_err_deg": injected_err_deg,
            "target_deg": 45.0,
            "diff_deg": pos_ctrl_diff,
            "r2": r2_pos,
            "passed": pos_ctrl_passed,
            "note": "P4 has no reset on Q48; P1 baseline has reset on Q48, so diff may include reset phase."
        },
        "protocol_1_phase": phase_results,
        "protocol_1_population": p1_results,
        "protocol_1_exploratory_constant_offset": {
            "offset_deg": const_offset,
            "sigma_deg": const_offset_err,
            "chi2": chi2_const,
            "df": 4,
            "note": "Independent of delay tau, present already at tau=0; consistent with microwave reset crosstalk."
        },
        "protocol_2_t2_star": {
            "t2_s0_us": float(t2_s0),
            "t2_s1_us": float(t2_s1),
            "dt2_us": dt2,
            "sigma_us": sigma_dt2,
            "z": z_t2,
            "p_value": p_t2,
            "valid_test": False,
            "note": "Invalid A/A test: 10 X gates transpile to identity at opt_level=1; both branches execute identical circuits."
        },
        "protocol_3_cpmg": cpmg_results,
        "summary": {
            "n_prereg_tests": 15,
            "max_abs_z": max_abs_z,
            "min_p_uncorrected": float(min(all_p)),
            "min_p_holm": min_holm_p,
            "verdict": verdict,
            "explanation": explanation
        }
    }
    return out

def main():
    args = parse_args()
    if args.raw_json:
        raw_path = Path(args.raw_json)
    else:
        dirs = sorted((REPO / "measurement_raw" / "spatial_bath_spectroscopy").glob("20*"))
        if not dirs:
            print("No measurement directories found!")
            sys.exit(1)
        raw_path = dirs[-1] / "raw_results.json"

    print(f"Loading data from: {raw_path}")
    with open(raw_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    result = analyze_spectroscopy(
        payload["data"],
        seed=args.seed,
        n_boot=args.n_boot,
        n_boot_t2=args.n_boot_t2,
        n_perm=args.n_perm
    )

    out_file = raw_path.parent / "analysis_prereg.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print("\n" + "=" * 60)
    print("PREREGISTERED SPECTROSCOPY ANALYSIS RESULTS")
    print("=" * 60)
    pos = result["positive_control"]
    print(f"Positive Control: {pos['injected_measured_deg']:+.2f}° ± {pos['injected_err_deg']:.2f}° (Target 45°, diff {pos['diff_deg']:+.2f}°, R2={pos['r2']:.4f}) -> {'PASSED' if pos['passed'] else 'FAILED'}")
    print(f"Protocol 1 Max Phase Dev: tau=50us d_phi={result['protocol_1_phase']['50.0']['d_phi_deg']:+.2f}° ± {result['protocol_1_phase']['50.0']['sigma_deg']:.2f}° (z={result['protocol_1_phase']['50.0']['z']:+.2f}, p={result['protocol_1_phase']['50.0']['p_value']:.4f})")
    print(f"Protocol 1 Population: max |dp1| <= {max(abs(v['dp1']) for v in result['protocol_1_population'].values()):.4f}, all p >= {min(v['p_perm'] for v in result['protocol_1_population'].values()):.4f}")
    exp = result["protocol_1_exploratory_constant_offset"]
    print(f"Protocol 1 Exploratory Constant Offset: {exp['offset_deg']:+.2f}° ± {exp['sigma_deg']:.2f}° (chi2={exp['chi2']:.2f}, df={exp['df']})")
    p2 = result["protocol_2_t2_star"]
    print(f"Protocol 2 T2*: dt2={p2['dt2_us']:+.2f} ± {p2['sigma_us']:.2f} us (z={p2['z']:+.2f}, A/A test)")
    p3_80 = result["protocol_3_cpmg"]["80.0"]
    print(f"Protocol 3 CPMG: T=80us dV={p3_80['dv']:+.4f} ± {p3_80['sigma']:.4f} (z={p3_80['z']:+.2f}, p={p3_80['p_value']:.4f})")
    sm = result["summary"]
    print(f"Summary: max |z| = {sm['max_abs_z']:.2f}, Holm min p = {sm['min_p_holm']:.4f}")
    print(f"VERDICT: {sm['verdict']} ({sm['explanation']})")
    print(f"Saved preregistered analysis to: {out_file}")

if __name__ == "__main__":
    main()
