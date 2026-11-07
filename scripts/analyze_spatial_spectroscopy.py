#!/usr/bin/env python3
"""
analyze_spatial_spectroscopy.py
Analyzes the comprehensive spatial field and substrate bath spectroscopy data.
Evaluates H0 vs H1 against preregistered thresholds.
"""

import argparse
import json
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

REPO = Path(__file__).resolve().parent.parent

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("raw_json", nargs="?", default=None, help="Path to raw_results.json")
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

def fit_fringe(thetas, p1s):
    """Fits P1(theta) = A - 0.5 * V * cos(theta + phi)"""
    def model(th, a, v, phi):
        return a - 0.5 * v * np.cos(th + phi)
    
    # Initial guess
    a_guess = np.mean(p1s)
    v_guess = (np.max(p1s) - np.min(p1s))
    phi_guess = 0.0
    
    try:
        popt, pcov = curve_fit(model, thetas, p1s, p0=[a_guess, v_guess, phi_guess],
                               bounds=([0, 0, -np.pi], [1, 1, np.pi]))
        res = p1s - model(thetas, *popt)
        ss_res = np.sum(res**2)
        ss_tot = np.sum((p1s - np.mean(p1s))**2)
        r2 = 1 - ss_res / (ss_tot + 1e-12)
        perr = np.sqrt(np.diag(pcov))
        return popt[0], popt[1], popt[2], perr[2], r2
    except Exception as e:
        return a_guess, v_guess, 0.0, 1.0, 0.0

def main():
    args = parse_args()
    if args.raw_json:
        raw_path = Path(args.raw_json)
    else:
        # Find latest raw_results.json
        dirs = sorted((REPO / "measurement_raw" / "spatial_bath_spectroscopy").glob("20*"))
        if not dirs:
            print("No measurement directories found!")
            sys.exit(1)
        raw_path = dirs[-1] / "raw_results.json"

    print(f"Loading data from: {raw_path}")
    with open(raw_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    data = payload["data"]
    print(f"Loaded {len(data)} circuit records. Backend: {payload['backend']}")

    # =========================================================
    # 1. POSITIVE CONTROL ANALYSIS
    # =========================================================
    pos_items = [d for d in data if d["meta"]["protocol"] == "P4_positive_control"]
    pos_items.sort(key=lambda x: x["meta"]["theta"])
    pos_thetas = np.array([d["meta"]["theta"] for d in pos_items])
    pos_p1s = np.array([get_p1(d["counts"], q_idx=1) for d in pos_items])

    a_pos, v_pos, phi_pos, phi_err_pos, r2_pos = fit_fringe(pos_thetas, pos_p1s)
    phi_pos_deg = np.rad2deg(phi_pos)
    phi_err_pos_deg = np.rad2deg(phi_err_pos)

    print("\n" + "=" * 60)
    print("1. POSITIVE CONTROL (Injected Rz(pi/4) = 45 deg phase)")
    print(f"Visibility: V = {v_pos:.4f} (R2 = {r2_pos:.4f})")
    print(f"Fitted Phase Shift: {phi_pos_deg:.2f}° ± {phi_err_pos_deg:.2f}° (Expected: 45.0°)")
    pos_ctrl_passed = abs(phi_pos_deg - 45.0) < 5.0 and r2_pos > 0.90
    print(f"Positive Control Verdict: {'PASSED [OK]' if pos_ctrl_passed else 'FAILED [INCONCLUSIVE]'}")
    print("=" * 60)

    # =========================================================
    # 2. PROTOCOL 1: SPATIAL PHASE & POPULATION TOMOGRAPHY
    # =========================================================
    p1_items = [d for d in data if d["meta"]["protocol"] == "P1_phase_tomography"]
    taus = sorted(list(set([d["meta"]["tau_us"] for d in p1_items])))

    phase_diffs = []
    phase_errs = []
    p1_diffs = []

    print("\n2. PROTOCOL 1: SPATIAL PHASE & POPULATION IMPRINT (Q49 Spectator)")
    print(f"{'Tau (us)':<10} | {'Phi(s=0)':<14} | {'Phi(s=1)':<14} | {'Delta_Phi':<16} | {'Delta_P1':<10}")
    print("-" * 72)

    for tau in taus:
        # s=0
        items_s0 = sorted([d for d in p1_items if d["meta"]["tau_us"] == tau and d["meta"]["s"] == 0],
                          key=lambda x: x["meta"]["theta"])
        th0 = np.array([d["meta"]["theta"] for d in items_s0])
        p0 = np.array([get_p1(d["counts"], q_idx=1) for d in items_s0])
        _, _, phi0, err0, _ = fit_fringe(th0, p0)

        # s=1
        items_s1 = sorted([d for d in p1_items if d["meta"]["tau_us"] == tau and d["meta"]["s"] == 1],
                          key=lambda x: x["meta"]["theta"])
        th1 = np.array([d["meta"]["theta"] for d in items_s1])
        p1 = np.array([get_p1(d["counts"], q_idx=1) for d in items_s1])
        _, _, phi1, err1, _ = fit_fringe(th1, p1)

        d_phi = phi1 - phi0
        d_phi_deg = np.rad2deg(d_phi)
        tot_err = np.sqrt(err0**2 + err1**2)
        tot_err_deg = np.rad2deg(tot_err)

        d_p1 = np.mean(p1) - np.mean(p0)

        phase_diffs.append(d_phi_deg)
        phase_errs.append(tot_err_deg)
        p1_diffs.append(d_p1)

        print(f"{tau:<10.1f} | {np.rad2deg(phi0):<6.2f}° ± {np.rad2deg(err0):<4.2f}° | "
              f"{np.rad2deg(phi1):<6.2f}° ± {np.rad2deg(err1):<4.2f}° | "
              f"{d_phi_deg:+6.2f}° ± {tot_err_deg:<6.2f}° | {d_p1:+7.4f}")

    # =========================================================
    # 3. PROTOCOL 2: SUBSTRATE TLS BATH DEPHASING (T2*)
    # =========================================================
    p2_items = [d for d in data if d["meta"]["protocol"] == "P2_tls_dephasing"]
    p2_taus = sorted(list(set([d["meta"]["tau_us"] for d in p2_items])))

    contrast_s0 = []
    contrast_s1 = []

    print("\n3. PROTOCOL 2: SUBSTRATE TLS BATH DEPHASING ENVELOPE (T2*)")
    print(f"{'Tau (us)':<10} | {'Contrast (Vacuum s=0)':<22} | {'Contrast (Pumped s=1)':<22} | {'Delta Contrast':<14}")
    print("-" * 75)

    for tau in p2_taus:
        items_s0 = [d for d in p2_items if d["meta"]["tau_us"] == tau and d["meta"]["s"] == 0]
        p_th0_s0 = get_p1([d for d in items_s0 if d["meta"]["theta"] == 0.0][0]["counts"], 1)
        p_th1_s0 = get_p1([d for d in items_s0 if d["meta"]["theta"] > 0.0][0]["counts"], 1)
        c0 = 2.0 * np.sqrt((p_th0_s0 - 0.5)**2 + (p_th1_s0 - 0.5)**2)

        items_s1 = [d for d in p2_items if d["meta"]["tau_us"] == tau and d["meta"]["s"] == 1]
        p_th0_s1 = get_p1([d for d in items_s1 if d["meta"]["theta"] == 0.0][0]["counts"], 1)
        p_th1_s1 = get_p1([d for d in items_s1 if d["meta"]["theta"] > 0.0][0]["counts"], 1)
        c1 = 2.0 * np.sqrt((p_th0_s1 - 0.5)**2 + (p_th1_s1 - 0.5)**2)

        contrast_s0.append(c0)
        contrast_s1.append(c1)
        print(f"{tau:<10.1f} | {c0:<22.4f} | {c1:<22.4f} | {c1 - c0:+14.4f}")

    # =========================================================
    # 4. PROTOCOL 3: CPMG-4 DYNAMICAL DECOUPLING
    # =========================================================
    p3_items = [d for d in data if d["meta"]["protocol"] == "P3_cpmg_decoupling"]
    p3_totals = sorted(list(set([d["meta"]["total_us"] for d in p3_items])))

    print("\n4. PROTOCOL 3: CPMG-4 DYNAMICAL DECOUPLING AC NOISE SPECTROSCOPY")
    print(f"{'T_total (us)':<14} | {'Filter Freq (kHz)':<18} | {'W(s=0)':<10} | {'W(s=1)':<10} | {'Delta W':<10}")
    print("-" * 70)

    for T_tot in p3_totals:
        f_filter_khz = 1000.0 / T_tot  # 1/T_tot in kHz
        items_s0 = [d for d in p3_items if d["meta"]["total_us"] == T_tot and d["meta"]["s"] == 0]
        w0 = get_p1([d for d in items_s0 if d["meta"]["theta"] > 0.0][0]["counts"], 1) - \
             get_p1([d for d in items_s0 if d["meta"]["theta"] == 0.0][0]["counts"], 1)

        items_s1 = [d for d in p3_items if d["meta"]["total_us"] == T_tot and d["meta"]["s"] == 1]
        w1 = get_p1([d for d in items_s1 if d["meta"]["theta"] > 0.0][0]["counts"], 1) - \
             get_p1([d for d in items_s1 if d["meta"]["theta"] == 0.0][0]["counts"], 1)

        print(f"{T_tot:<14.1f} | {f_filter_khz:<18.1f} | {w0:<10.4f} | {w1:<10.4f} | {w1 - w0:+10.4f}")

    # =========================================================
    # VERDICT DETERMINATION
    # =========================================================
    max_phase_dev = np.max(np.abs(phase_diffs))
    mean_phase_dev = np.mean(np.abs(phase_diffs))
    max_p1_dev = np.max(np.abs(p1_diffs))

    h1_supported = (max_phase_dev > 3.0 * np.mean(phase_errs)) or (max_p1_dev > 0.03)
    verdict = "H1 SUPPORTED (Spatial Memory Detected)" if h1_supported else "H0 CONFIRMED (Markovian Vacuum / No Spatial Memory)"

    print("\n" + "=" * 60)
    print("FINAL SCIENTIFIC VERDICT:")
    print(f"  Max Spectator Phase Shift: {max_phase_dev:.2f}° (Mean 3-sigma bound: {3*np.mean(phase_errs):.2f}°)")
    print(f"  Max Spectator Population Bias: {max_p1_dev:.4f}")
    print(f"  VERDICT: {verdict}")
    print("=" * 60)

    # Plot figure
    fig_dir = REPO / "docs" / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig_path = fig_dir / "spatial_bath_spectroscopy.png"

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Subplot 1: Positive Control
    th_fine = np.linspace(0, 2*np.pi, 100)
    axes[0, 0].scatter(np.rad2deg(pos_thetas), pos_p1s, color="red", label="Measured")
    axes[0, 0].plot(np.rad2deg(th_fine), a_pos - 0.5 * v_pos * np.cos(th_fine + phi_pos), "r--",
                    label=f"Fit (Phi={phi_pos_deg:.1f} deg)")
    axes[0, 0].set_title(f"Positive Control: Calibrated Phase Shift (R2={r2_pos:.3f})")
    axes[0, 0].set_xlabel("Projection Angle (deg)")
    axes[0, 0].set_ylabel("P(1)")
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)

    # Subplot 2: Phase Shift vs Delay
    axes[0, 1].errorbar(taus, phase_diffs, yerr=phase_errs, fmt="o-", color="blue", capsize=4)
    axes[0, 1].axhline(0, color="gray", linestyle="--")
    axes[0, 1].set_title("Spectator Phase Shift Delta_Phi vs Delay")
    axes[0, 1].set_xlabel("Delay tau (us)")
    axes[0, 1].set_ylabel("Delta_Phi (deg)")
    axes[0, 1].grid(True, alpha=0.3)

    # Subplot 3: T2* Dephasing Contrast
    axes[1, 0].plot(p2_taus, contrast_s0, "g-o", label="Vacuum (s=0)")
    axes[1, 0].plot(p2_taus, contrast_s1, "m-s", label="Pumped Substrate (s=1)")
    axes[1, 0].set_title("Substrate TLS Bath: Spectator T2* Coherence Contrast")
    axes[1, 0].set_xlabel("Delay tau (us)")
    axes[1, 0].set_ylabel("Fringe Contrast")
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)

    # Subplot 4: Population Bias
    axes[1, 1].plot(taus, p1_diffs, "k-o")
    axes[1, 1].axhline(0, color="gray", linestyle="--")
    axes[1, 1].set_title("Spectator Population Delta P(1) vs Delay")
    axes[1, 1].set_xlabel("Delay tau (us)")
    axes[1, 1].set_ylabel("Delta P(1)")
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(fig_path, dpi=200)
    print(f"Saved summary figure to: {fig_path}")

    # Write summary json
    summary_file = raw_path.parent / "analysis_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump({
            "pos_ctrl_passed": bool(pos_ctrl_passed),
            "phi_pos_deg": float(phi_pos_deg),
            "max_phase_dev_deg": float(max_phase_dev),
            "mean_phase_err_deg": float(np.mean(phase_errs)),
            "max_p1_dev": float(max_p1_dev),
            "verdict": verdict
        }, f, indent=2)

if __name__ == "__main__":
    main()
