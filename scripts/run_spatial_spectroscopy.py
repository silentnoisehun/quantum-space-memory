#!/usr/bin/env python3
"""
run_spatial_spectroscopy.py
Preregistered experimental test of spatial field and substrate bath memory on IBM Quantum Heron r2.
Target: ibm_kingston, Transmons [48, 49, 50] (48=Source, 49=Spectator, 50=Distant Spectator)
Preregistration: docs/PREREGISTRATION-spatial_bath_spectroscopy.md
"""

import argparse
import json
import time
import sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--token-file", default=r"C:\Users\mater\Downloads\apikey (1) (1).json")
    p.add_argument("--instance", default="open-instance")
    p.add_argument("--backend", default="ibm_kingston")
    p.add_argument("--qubits", type=int, nargs=3, default=[48, 49, 50])
    p.add_argument("--shots", type=int, default=4096)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()

def build_all_circuits():
    from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister

    circuits = []
    metadata = []

    # -------------------------------------------------------------
    # Protocol 1: Spatial Phase & Population Tomography (40 circuits)
    # -------------------------------------------------------------
    p1_taus = [0.0, 10.0, 25.0, 50.0, 100.0]
    p1_thetas = [0.0, np.pi/2, np.pi, 3*np.pi/2]
    p1_theta_names = ["0", "pi/2", "pi", "3pi/2"]

    for s in [0, 1]:
        for tau in p1_taus:
            for th_idx, th in enumerate(p1_thetas):
                qr = QuantumRegister(3, "q")
                cr = ClassicalRegister(3, "c")
                qc = QuantumCircuit(qr, cr, name=f"P1_s{s}_tau{int(tau)}_th{th_idx}")
                
                # Source Q0 preparation
                if s == 1:
                    qc.x(0)
                qc.reset(0)

                # Spectator Q1 Ramsey
                qc.sx(1)
                if tau > 0:
                    qc.delay(tau, 1, unit="us")
                if th > 0:
                    qc.rz(th, 1)
                qc.sx(1)

                qc.measure(qr, cr)
                circuits.append(qc)
                metadata.append({
                    "protocol": "P1_phase_tomography",
                    "s": s,
                    "tau_us": tau,
                    "theta": th,
                    "theta_name": p1_theta_names[th_idx]
                })

    # -------------------------------------------------------------
    # Protocol 2: Substrate TLS Bath Dephasing T2* Envelope (32 circuits)
    # -------------------------------------------------------------
    p2_taus = [2.0, 10.0, 25.0, 50.0, 75.0, 100.0, 150.0, 200.0]
    p2_thetas = [0.0, np.pi/2]
    p2_theta_names = ["0", "pi/2"]

    for s in [0, 1]:
        for tau in p2_taus:
            for th_idx, th in enumerate(p2_thetas):
                qr = QuantumRegister(3, "q")
                cr = ClassicalRegister(3, "c")
                qc = QuantumCircuit(qr, cr, name=f"P2_s{s}_tau{int(tau)}_th{th_idx}")

                # Source Q0: vacuum (s=0) vs saturation pulse train (s=1)
                if s == 1:
                    for _ in range(10):
                        qc.x(0)
                qc.reset(0)

                # Spectator Q1 Ramsey envelope
                qc.sx(1)
                qc.delay(tau, 1, unit="us")
                if th > 0:
                    qc.rz(th, 1)
                qc.sx(1)

                qc.measure(qr, cr)
                circuits.append(qc)
                metadata.append({
                    "protocol": "P2_tls_dephasing",
                    "s": s,
                    "tau_us": tau,
                    "theta": th,
                    "theta_name": p2_theta_names[th_idx]
                })

    # -------------------------------------------------------------
    # Protocol 3: CPMG-4 Dynamical Decoupling AC Noise (16 circuits)
    # -------------------------------------------------------------
    p3_total_times = [10.0, 20.0, 40.0, 80.0]
    p3_thetas = [0.0, np.pi]
    p3_theta_names = ["0", "pi"]

    for s in [0, 1]:
        for T_tot in p3_total_times:
            dt = T_tot / 8.0  # CPMG-4 spacing: dt, 2dt, 2dt, 2dt, dt
            for th_idx, th in enumerate(p3_thetas):
                qr = QuantumRegister(3, "q")
                cr = ClassicalRegister(3, "c")
                qc = QuantumCircuit(qr, cr, name=f"P3_s{s}_T{int(T_tot)}_th{th_idx}")

                # If s=1, flip Q0 to create AC displacement in environment
                if s == 1:
                    qc.x(0)

                # Spectator Q1 CPMG-4
                qc.sx(1)
                qc.delay(dt, 1, unit="us")
                qc.x(1)
                qc.delay(2 * dt, 1, unit="us")
                qc.x(1)
                qc.delay(2 * dt, 1, unit="us")
                qc.x(1)
                qc.delay(2 * dt, 1, unit="us")
                qc.x(1)
                qc.delay(dt, 1, unit="us")

                if th > 0:
                    qc.rz(th, 1)
                qc.sx(1)

                qc.measure(qr, cr)
                circuits.append(qc)
                metadata.append({
                    "protocol": "P3_cpmg_decoupling",
                    "s": s,
                    "total_us": T_tot,
                    "theta": th,
                    "theta_name": p3_theta_names[th_idx]
                })

    # -------------------------------------------------------------
    # Protocol 4: Positive Control (4 circuits)
    # -------------------------------------------------------------
    p4_thetas = [0.0, np.pi/2, np.pi, 3*np.pi/2]
    p4_theta_names = ["0", "pi/2", "pi", "3pi/2"]

    for th_idx, th in enumerate(p4_thetas):
        qr = QuantumRegister(3, "q")
        cr = ClassicalRegister(3, "c")
        qc = QuantumCircuit(qr, cr, name=f"P4_pos_ctrl_th{th_idx}")

        # Injected calibrated phase shift Rz(pi/4) = 45 degrees
        qc.sx(1)
        qc.delay(10.0, 1, unit="us")
        qc.rz(np.pi/4, 1)
        if th > 0:
            qc.rz(th, 1)
        qc.sx(1)

        qc.measure(qr, cr)
        circuits.append(qc)
        metadata.append({
            "protocol": "P4_positive_control",
            "s": "control",
            "tau_us": 10.0,
            "injected_phase": np.pi/4,
            "theta": th,
            "theta_name": p4_theta_names[th_idx]
        })

    return circuits, metadata

def main():
    args = parse_args()
    print("=" * 70)
    print("RUN SPATIAL FIELD & SUBSTRATE BATH MEMORY SPECTROSCOPY")
    print(f"Backend: {args.backend} | Target Qubits: {args.qubits} | Shots: {args.shots}")
    print("=" * 70)

    circuits, metadata = build_all_circuits()
    n_circ = len(circuits)
    print(f"Total compiled circuits: {n_circ}")

    # Deterministic interleave / shuffle to avoid systematic temporal drift
    rng = np.random.default_rng(20261107)
    order = np.arange(n_circ)
    rng.shuffle(order)

    shuffled_circuits = [circuits[i] for i in order]
    shuffled_metadata = [metadata[i] for i in order]

    tag = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + ("_dry" if args.dry_run else "")
    out_dir = REPO / "measurement_raw" / "spatial_bath_spectroscopy" / tag
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        print("[DRY RUN] Simulating results locally...")
        results_data = []
        for meta in shuffled_metadata:
            # Ideal or small noise counts
            c = {"000": args.shots // 2, "010": args.shots // 2}
            results_data.append({"meta": meta, "counts": c})
        job_id = "dry-run-job"
        cal_date = "N/A"
    else:
        from qiskit import transpile
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

        with open(args.token_file, encoding="utf-8") as f:
            kd = json.load(f)
        token = kd.get("apikey") or kd.get("token")
        
        service = QiskitRuntimeService(channel="ibm_quantum_platform", token=token, instance=args.instance)
        backend = service.backend(args.backend)
        props = backend.properties(refresh=True)
        cal_date = str(props.last_update_date)
        print(f"Connected to {args.backend} (Calibrated: {cal_date})")

        print("Transpiling 92 circuits with layout [48, 49, 50]...")
        isa_circuits = [transpile(c, backend=backend, initial_layout=args.qubits, optimization_level=1) for c in shuffled_circuits]
        print(f"Transpilation complete. Average depth: {np.mean([c.depth() for c in isa_circuits]):.1f}")

        sampler = SamplerV2(backend)
        print("Submitting unified batch job to QPU...")
        t0 = time.time()
        job = sampler.run(isa_circuits, shots=args.shots)
        job_id = job.job_id()
        print(f"Job ID: {job_id}. Waiting for completion on {args.backend}...")
        res = job.result()
        t1 = time.time()
        print(f"Job finished in {t1 - t0:.1f} s!")

        results_data = []
        for i, meta in enumerate(shuffled_metadata):
            d = res[i].data
            counts = d.c.get_counts()
            results_data.append({
                "meta": meta,
                "counts": counts
            })

    output_payload = {
        "preregistration": "docs/PREREGISTRATION-spatial_bath_spectroscopy.md",
        "tag": tag,
        "backend": args.backend,
        "physical_qubits": args.qubits,
        "calibration_date": cal_date,
        "shots": args.shots,
        "job_id": job_id,
        "total_circuits": n_circ,
        "data": results_data
    }

    raw_file = out_dir / "raw_results.json"
    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)
    print(f"Saved raw data to {raw_file}")

    print("\nNext: Running analysis...")
    return str(raw_file)

if __name__ == "__main__":
    main()
