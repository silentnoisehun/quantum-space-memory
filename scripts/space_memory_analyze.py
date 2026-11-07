#!/usr/bin/env python3
"""
space_memory_analyze.py — Preregistered exact analysis and decision rule for Space Memory experiment.

Preregistration: docs/PREREGISTRATION-space_memory.md
Author: Máté Róbert (ORCID 0009-0003-3986-6039)
Repository: https://github.com/silentnoisehun/qhf-bell-spectator
"""

import argparse
import json
import math
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

N_PERM = 200_000

def extract_p1(counts, num_bits=3):
    ones = [0.0] * num_bits
    total = sum(counts.values())
    if total == 0:
        return [0.0] * num_bits
    for bstr, c in counts.items():
        s = bstr.replace(" ", "")
        for q in range(num_bits):
            bit_idx = len(s) - 1 - q
            if bit_idx >= 0 and s[bit_idx] == '1':
                ones[q] += c
    return [c_val / total for c_val in ones]

def analyze_run(run_dir_path):
    run_dir = Path(run_dir_path)
    
    with open(run_dir / "campaign.json", encoding="utf-8") as f:
        campaign = json.load(f)

    pair_files = sorted(list(run_dir.glob("pair_*.json")))
    n_pairs = len(pair_files)

    print("\n" + "=" * 80)
    print("PREREGISTERED ANALYSIS: SPACE MEMORY CROSS-JOB EXPERIMENT")
    print(f"Directory: {run_dir.name} | Backend: {campaign.get('backend')} | Completed Pairs: {n_pairs}")
    print("=" * 80)

    if n_pairs < 20:
        print(f"[ERROR] Preregistered minimum pairs is 20, but only {n_pairs} pairs available.")
        return

    pairs = []
    for pf in pair_files:
        with open(pf, encoding="utf-8") as f:
            pairs.append(json.load(f))

    # 1. Positive Control Analysis (tau = 0 us)
    # circuits 1: u=000, tau=0; circuit 2: u=111, tau=0
    # In each, 'm2' is second measurement after reset
    d_k_list = []
    d_k_tau20_list = []
    gaps = []
    job_A_fidelity = []

    p1_B_all = [] # shape (n_pairs, 3)
    secret_bits_all = [] # shape (n_pairs, 3)

    for p in pairs:
        s_bits = p["secret_bits"]
        secret_bits_all.append(s_bits)
        p1_B0 = p["job_B"]["main_measurement_p1"]
        p1_B_all.append(p1_B0)
        gaps.append(p["job_B"]["gap_seconds"])

        # Check job A fidelity
        p1_A = p["job_A"]["p1"]
        matched_A = sum(p1_A[q] if s_bits[q] == 1 else (1.0 - p1_A[q]) for q in range(3)) / 3.0
        job_A_fidelity.append(matched_A)

        # Positive controls
        # ctrl[0] is u=000, tau=0; ctrl[1] is u=111, tau=0
        # ctrl[2] is u=000, tau=20; ctrl[3] is u=111, tau=20
        ctrls = p["job_B"]["positive_control_counts"]
        p1_m2_u0_tau0 = extract_p1(ctrls[0]["m2"])
        p1_m2_u1_tau0 = extract_p1(ctrls[1]["m2"])
        d_k = sum(p1_m2_u1_tau0[q] - p1_m2_u0_tau0[q] for q in range(3)) / 3.0
        d_k_list.append(d_k)

        p1_m2_u0_tau20 = extract_p1(ctrls[2]["m2"])
        p1_m2_u1_tau20 = extract_p1(ctrls[3]["m2"])
        d_k_20 = sum(p1_m2_u1_tau20[q] - p1_m2_u0_tau20[q] for q in range(3)) / 3.0
        d_k_tau20_list.append(d_k_20)

    p1_B_all = np.array(p1_B_all)
    secret_bits_all = np.array(secret_bits_all)
    d_k_arr = np.array(d_k_list)

    # Statistical test for Positive Control: One-sided sign-flip permutation test
    mean_d = float(np.mean(d_k_arr))
    rng = np.random.default_rng(20261110)
    flips = rng.choice([-1.0, 1.0], size=(N_PERM, n_pairs))
    perm_d = np.mean(flips * d_k_arr, axis=1)
    p_control = float((np.sum(perm_d >= mean_d) + 1.0) / (N_PERM + 1.0))

    control_passed = (mean_d > 0) and (p_control < 0.01)

    print("\n[1. POSITIVE CONTROL: RESET IMPERFECTION (tau = 0 us)]")
    print(f"  Mean d_k: {mean_d:+.6f} ({mean_d*100:+.4f}%)")
    print(f"  One-sided sign-flip permutation p-value: {p_control:.6f} (N={N_PERM})")
    print(f"  Positive Control Status: {'PASSED (Valid detector)' if control_passed else 'FAILED (INCONCLUSIVE)'}")

    # 2. Primary Metric: Delta
    def compute_delta(p1_mat, s_mat):
        delta_q = []
        for q in range(3):
            mask1 = (s_mat[:, q] == 1)
            mask0 = (s_mat[:, q] == 0)
            p1_when_1 = np.mean(p1_mat[mask1, q]) if np.sum(mask1) > 0 else 0.0
            p1_when_0 = np.mean(p1_mat[mask0, q]) if np.sum(mask0) > 0 else 0.0
            delta_q.append(float(p1_when_1 - p1_when_0))
        return delta_q, float(np.mean(delta_q))

    delta_q, delta_main = compute_delta(p1_B_all, secret_bits_all)

    # Permutation test for Delta: random relabelling of secret bits independently per qubit
    perm_deltas = np.zeros(N_PERM)
    for q in range(3):
        # Generate N_PERM permutations of secret_bits_all[:, q]
        s_col = secret_bits_all[:, q].copy()
        # Vectorized random permutations
        perms = np.array([rng.permutation(s_col) for _ in range(N_PERM)])
        # Compute mean difference for each perm
        # mask1: perms == 1, mask0: perms == 0
        y = p1_B_all[:, q] # shape (n_pairs,)
        mean1 = np.dot(perms, y) / np.sum(s_col == 1)
        mean0 = np.dot(1 - perms, y) / np.sum(s_col == 0)
        perm_deltas += (mean1 - mean0) / 3.0

    p_primary = float((np.sum(np.abs(perm_deltas) >= abs(delta_main)) + 1.0) / (N_PERM + 1.0))

    # Split-half consistency
    half = n_pairs // 2
    _, delta_first = compute_delta(p1_B_all[:half], secret_bits_all[:half])
    _, delta_second = compute_delta(p1_B_all[half:], secret_bits_all[half:])
    same_sign = (delta_first * delta_second > 0)

    # 3. Decision Rule
    h1_supported = False
    verdict = ""
    if not control_passed:
        verdict = "INCONCLUSIVE (Positive control failed)"
    elif (p_primary < 0.01) and same_sign:
        h1_supported = True
        verdict = "H1 SUPPORTED (Information persists across jobs!)"
    else:
        verdict = "H1 NOT SUPPORTED (Consistent with H0 / textbook quantum mechanics)"

    print("\n[2. PRIMARY METRIC & DECISION RULE: DELTA]")
    print(f"  Primary Delta (mean over 3 qubits): {delta_main:+.6f} ({delta_main*100:+.4f}%)")
    print(f"  Per-qubit Delta: Q0={delta_q[0]:+.6f}, Q1={delta_q[1]:+.6f}, Q2={delta_q[2]:+.6f}")
    print(f"  Two-sided permutation p-value: {p_primary:.6f} (N={N_PERM})")
    print(f"  Split-half consistency: First half={delta_first:+.6f}, Second half={delta_second:+.6f} (Same sign: {same_sign})")
    print(f"\n>>> FINAL PREREGISTERED VERDICT: {verdict} <<<")

    # 4. Secondary Metrics
    median_gap = float(np.median(gaps))
    short_mask = np.array(gaps) <= median_gap
    long_mask = np.array(gaps) > median_gap
    _, delta_short = compute_delta(p1_B_all[short_mask], secret_bits_all[short_mask])
    _, delta_long = compute_delta(p1_B_all[long_mask], secret_bits_all[long_mask])

    mean_d_tau20 = float(np.mean(d_k_tau20_list))
    mean_A_fidelity = float(np.mean(job_A_fidelity))

    print("\n[3. SECONDARY METRICS]")
    print(f"  Median Job Gap: {median_gap:.2f} s")
    print(f"  Delta for Short Gap (<= {median_gap:.2f}s): {delta_short:+.6f}")
    print(f"  Delta for Long Gap  (>  {median_gap:.2f}s): {delta_long:+.6f}")
    print(f"  Positive Control at tau = 20 us: {mean_d_tau20:+.6f} ({mean_d_tau20*100:+.4f}%)")
    print(f"  Job A Bit Setting Fidelity: {mean_A_fidelity*100:.2f}%")

    analysis_out = {
        "preregistration": "docs/PREREGISTRATION.md",
        "backend": campaign.get("backend"),
        "qubits": campaign.get("physical_qubits"),
        "n_pairs": n_pairs,
        "positive_control": {
            "mean_d": mean_d,
            "p_value_one_sided": p_control,
            "passed": control_passed
        },
        "primary_metric": {
            "delta_main": delta_main,
            "delta_q": delta_q,
            "p_value_two_sided": p_primary,
            "delta_first_half": delta_first,
            "delta_second_half": delta_second,
            "split_half_same_sign": same_sign,
            "h1_supported": h1_supported
        },
        "verdict": verdict,
        "secondary_metrics": {
            "median_gap_seconds": median_gap,
            "delta_short_gap": delta_short,
            "delta_long_gap": delta_long,
            "positive_control_tau20_us": mean_d_tau20,
            "job_A_fidelity": mean_A_fidelity
        }
    }

    with open(run_dir / "analysis.json", "w", encoding="utf-8") as f:
        json.dump(analysis_out, f, indent=2)

    with open(run_dir / "report.txt", "w", encoding="utf-8") as f:
        f.write(f"PREREGISTERED VERDICT: {verdict}\n")
        f.write(f"Primary Delta: {delta_main:+.6f} (p = {p_primary:.6f})\n")
        f.write(f"Positive Control mean d: {mean_d:+.6f} (p = {p_control:.6f})\n")

    print(f"\nAnalysis saved to {run_dir / 'analysis.json'}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=str, help="Path to run directory")
    args = parser.parse_args()
    analyze_run(args.run_dir)
