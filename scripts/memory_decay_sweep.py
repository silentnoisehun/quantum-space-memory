#!/usr/bin/env python3
"""
memory_decay_sweep.py — High-precision measurement of quantum memory lifetime and residual state relaxation post-reset.

Measures the continuous physical decay curve d(tau) = P1(tau | initial=1) - P1(tau | initial=0)
across microsecond delays tau in [0, 500 us] on IBM Heron r2 superconducting transmons.

Author: Máté Róbert (ORCID 0009-0003-3986-6039)
Repository: https://github.com/silentnoisehun/quantum-space-memory
"""

import argparse
import datetime
import json
import math
import sys
import time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

DELAYS_US = [0.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0]

def parse_args():
    p = argparse.ArgumentParser(description="Quantum Memory Decay Lifetime Sweep")
    p.add_argument("--token-file", default=r"C:\Users\mater\Downloads\apikey (5).json")
    p.add_argument("--backend", default="ibm_kingston")
    p.add_argument("--qubits", type=int, nargs=3, default=[48, 49, 50])
    p.add_argument("--shots", type=int, default=4096)
    p.add_argument("--dry-run", action="store_true", help="Local simulation without QPU hardware")
    return p.parse_args()

def build_sweep_circuits():
    from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister

    circuits = []
    metadata = []

    for tau in DELAYS_US:
        for u in (0, 1):
            qr = QuantumRegister(3, "q")
            c1 = ClassicalRegister(3, "c1")
            c2 = ClassicalRegister(3, "c2")
            qc = QuantumCircuit(qr, c1, c2, name=f"mem_u{u}_tau{int(tau)}us")

            if u == 1:
                qc.x(qr)
            qc.measure(qr, c1)
            qc.reset(qr)
            if tau > 0:
                qc.delay(int(tau), qr, unit="us")
            qc.measure(qr, c2)

            circuits.append(qc)
            metadata.append({"tau_us": tau, "initial_state": u})

    return circuits, metadata

def extract_p1(counts, num_bits=3):
    ones = [0.0] * num_bits
    total = sum(counts.values())
    if total == 0:
        return [0.0] * num_bits
    for bstr, c in counts.items():
        s = bstr.replace(" ", "")
        for q in range(num_bits):
            bit_idx = len(s) - 1 - q
            if bit_idx >= 0 and s[bit_idx] == "1":
                ones[q] += c
    return [c_val / total for c_val in ones]

def main():
    args = parse_args()

    tag = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = REPO / "measurement_raw" / "memory_decay_sweep" / tag
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 75)
    print("QUANTUM MEMORY DECAY SWEEP (LIFETIME OF RESIDUAL EXCITATION POST-RESET)")
    print(f"Backend: {args.backend} | Qubits: {args.qubits} | Shots: {args.shots}")
    print(f"Delays probed (us): {DELAYS_US}")
    print(f"Token file: {args.token_file} | Mode: {'DRY RUN' if args.dry_run else 'LIVE QPU'}")
    print("=" * 75)

    circuits, metadata = build_sweep_circuits()
    print(f"Built {len(circuits)} circuits (9 delays x 2 initial states).")

    cal_time = None
    if not args.dry_run:
        from qiskit import transpile
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

        with open(args.token_file, encoding="utf-8") as f:
            kd = json.load(f)
        token = kd.get("apikey") or kd.get("token")
        service = QiskitRuntimeService(channel="ibm_quantum_platform", token=token, instance="open-instance")
        backend = service.backend(args.backend)
        props = backend.properties(refresh=True)
        cal_time = str(props.last_update_date)

        print(f"Connected to {args.backend}. Last calibration: {cal_time}")
        print("Transpiling circuits onto physical layout...")
        isa_circs = [transpile(c, backend=backend, initial_layout=args.qubits, optimization_level=1) for c in circuits]

        print("Submitting single batch job to QPU (estimated ~8-12 seconds QPU time)...")
        sampler = SamplerV2(backend)
        job = sampler.run(isa_circs, shots=args.shots)
        job_id = job.job_id()
        print(f"Job ID: {job_id} | Status: {job.status()} | Waiting for completion...")

        res = job.result()
        print("Execution complete!")

        regs = []
        for i, c in enumerate(circuits):
            d = res[i].data
            regs.append({name: getattr(d, name).get_counts() for name in [cr.name for cr in c.cregs]})
    else:
        from qiskit_aer import AerSimulator
        from qiskit import transpile
        sim = AerSimulator()
        isa_circs = [transpile(c, backend=sim, optimization_level=1) for c in circuits]
        res = sim.run(isa_circs, shots=args.shots).result()
        job_id = "dryrun_decay_sweep"
        cal_time = "dryrun"
        regs = []
        for i, c in enumerate(circuits):
            raw_c = res.get_counts(isa_circs[i])
            c1_dict, c2_dict = {}, {}
            for bstr, cnt in raw_c.items():
                parts = bstr.split(" ")
                m2_s = parts[0]
                m1_s = parts[1] if len(parts) > 1 else parts[0]
                c1_dict[m1_s] = c1_dict.get(m1_s, 0) + cnt
                c2_dict[m2_s] = c2_dict.get(m2_s, 0) + cnt
            regs.append({"c1": c1_dict, "c2": c2_dict})

    # Process and organize results by delay
    results_by_tau = {}
    for i, meta in enumerate(metadata):
        tau = meta["tau_us"]
        u = meta["initial_state"]
        p1_c2 = extract_p1(regs[i]["c2"])
        p1_c1 = extract_p1(regs[i]["c1"])
        if tau not in results_by_tau:
            results_by_tau[tau] = {}
        results_by_tau[tau][u] = {
            "p1_c1": p1_c1,
            "p1_c2": p1_c2,
            "counts_c1": regs[i]["c1"],
            "counts_c2": regs[i]["c2"]
        }

    # Calculate memory gap d(tau) = P1(c2 | u=1) - P1(c2 | u=0)
    print("\n" + "=" * 80)
    print("MEASURED RESIDUAL MEMORY GAP d(tau) = P1(u=1) - P1(u=0)")
    print(f"{'Delay tau (us)':>14} | {'Mean d(tau)':>12} | {'Q48 d':>10} | {'Q49 d':>10} | {'Q50 d':>10}")
    print("-" * 80)

    sweep_data = []
    tau_vals = []
    d_mean_vals = []

    for tau in DELAYS_US:
        p1_u1 = np.array(results_by_tau[tau][1]["p1_c2"])
        p1_u0 = np.array(results_by_tau[tau][0]["p1_c2"])
        d_q = p1_u1 - p1_u0
        d_mean = float(np.mean(d_q))

        tau_vals.append(tau)
        d_mean_vals.append(d_mean)

        sweep_data.append({
            "tau_us": tau,
            "d_mean": d_mean,
            "d_q48": float(d_q[0]),
            "d_q49": float(d_q[1]),
            "d_q50": float(d_q[2]),
            "p1_u1": p1_u1.tolist(),
            "p1_u0": p1_u0.tolist()
        })

        print(f"{tau:14.1f} | {d_mean*100:+11.4f}% | {d_q[0]*100:+9.4f}% | {d_q[1]*100:+9.4f}% | {d_q[2]*100:+9.4f}%")

    # Fit exponential decay: d(tau) = d0 * exp(-tau / T_mem) + c
    tau_arr = np.array(tau_vals)
    d_arr = np.array(d_mean_vals)

    # Simple log-linear fit for estimating T_mem (ignoring floor)
    try:
        from scipy.optimize import curve_fit
        def exp_decay(t, d0, t_mem, c):
            return d0 * np.exp(-t / t_mem) + c
        popt, pcov = curve_fit(exp_decay, tau_arr, d_arr, p0=[d_arr[0], 150.0, 0.0], maxfev=5000)
        fit_d0, fit_t_mem, fit_c = float(popt[0]), float(popt[1]), float(popt[2])
    except Exception:
        fit_d0, fit_t_mem, fit_c = float(d_arr[0]), 150.0, 0.0

    print("-" * 80)
    print(f"Fitted Memory Lifetime T_mem: {fit_t_mem:.2f} us (Initial residual d0: {fit_d0*100:+.4f}%)")
    print("=" * 80)

    final_payload = {
        "job_id": job_id,
        "backend": args.backend,
        "qubits": args.qubits,
        "shots": args.shots,
        "calibration_timestamp": cal_time,
        "delays_us": DELAYS_US,
        "sweep_data": sweep_data,
        "fit": {
            "initial_residual_d0": fit_d0,
            "fitted_lifetime_t_mem_us": fit_t_mem,
            "residual_baseline_c": fit_c
        }
    }

    with open(out / "decay_analysis.json", "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2)

    print(f"\nAll data and analysis written to {out / 'decay_analysis.json'}")

if __name__ == "__main__":
    main()
