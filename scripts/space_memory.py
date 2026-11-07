#!/usr/bin/env python3
"""
space_memory.py — Does information persist on a qubit from one job to the next? ("Memory in space")

Preregistration: docs/PREREGISTRATION-space_memory.md
Author: Máté Róbert (ORCID 0009-0003-3986-6039)
Repository: https://github.com/silentnoisehun/qhf-bell-spectator
"""

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

def parse_args():
    parser = argparse.ArgumentParser(description="Space Memory Cross-Job Persistence Experiment")
    parser.add_argument("--token-file", default=r"C:\Users\mater\Downloads\apikey (5).json")
    parser.add_argument("--backend", default="ibm_kingston")
    parser.add_argument("--qubits", type=int, nargs="+", default=None)
    parser.add_argument("--pairs", type=int, default=40)
    parser.add_argument("--shots", type=int, default=1024)
    parser.add_argument("--seed", type=int, default=20261110)
    parser.add_argument("--dry-run", action="store_true", help="Local simulation without QPU hardware")
    return parser.parse_args()

def generate_secret_bits(n_pairs=40, seed=20261110):
    """
    For each of the 3 qubits separately: 20 ones and 20 zeros, shuffled with seed.
    """
    rng = np.random.default_rng(seed)
    secret_bits = np.zeros((n_pairs, 3), dtype=int)
    for q in range(3):
        bits = np.array([1] * (n_pairs // 2) + [0] * (n_pairs - n_pairs // 2))
        rng.shuffle(bits)
        secret_bits[:, q] = bits
    return secret_bits

def extract_p1_from_counts(counts, shots, num_bits=3):
    """
    Returns [P(1)_q0, P(1)_q1, P(1)_q2] from counts dictionary where bitstring has format 'b2 b1 b0'.
    """
    ones = [0.0] * num_bits
    total = 0
    for bstr, c in counts.items():
        s = bstr.replace(" ", "")
        total += c
        for q in range(num_bits):
            bit_idx = len(s) - 1 - q
            if bit_idx >= 0 and s[bit_idx] == '1':
                ones[q] += c
    denom = total if total > 0 else shots
    return [c_val / denom for c_val in ones]

def build_job_A_circuit(bits):
    from qiskit import QuantumCircuit
    qc = QuantumCircuit(3, 3)
    for q in range(3):
        if bits[q] == 1:
            qc.x(q)
    qc.measure([0, 1, 2], [0, 1, 2])
    return qc

def build_job_B_circuits():
    """
    Returns 5 circuits for Job B:
    0: Main measurement (no gates, measure 3 qubits)
    1: Positive control: u=000, tau=0 us
    2: Positive control: u=111, tau=0 us
    3: Positive control: u=000, tau=20 us
    4: Positive control: u=111, tau=20 us
    """
    from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister

    circuits = []

    # Circuit 0: Main measurement
    qc0 = QuantumCircuit(3, 3)
    qc0.measure([0, 1, 2], [0, 1, 2])
    circuits.append(qc0)

    # Circuits 1-4: Positive control
    controls = [
        ("000", 0),
        ("111", 0),
        ("000", 20),
        ("111", 20),
    ]

    for u_str, tau_us in controls:
        qr = QuantumRegister(3, 'q')
        cr1 = ClassicalRegister(3, 'm1')
        cr2 = ClassicalRegister(3, 'm2')
        qc = QuantumCircuit(qr, cr1, cr2)

        if u_str == "111":
            qc.x(qr)
        qc.measure(qr, cr1)
        qc.reset(qr)
        if tau_us > 0:
            qc.delay(tau_us, qr, unit='us')
        qc.measure(qr, cr2)
        circuits.append(qc)

    return circuits

def main():
    args = parse_args()

    # Generate secret bits
    secret_bits = generate_secret_bits(n_pairs=args.pairs, seed=args.seed)

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = REPO / "measurement_raw" / "space_memory" / f"{timestamp}_{args.backend}"
    run_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 75)
    print("EXPERIMENT: SPACE MEMORY (DOES INFORMATION PERSIST ACROSS JOBS?)")
    print(f"Backend: {args.backend} | Pairs: {args.pairs} | Shots: {args.shots} | Seed: {args.seed}")
    print(f"Token file: {args.token_file} | Mode: {'DRY RUN' if args.dry_run else 'LIVE QPU'}")
    print(f"Output directory: {run_dir}")
    print("=" * 75)

    # Backend setup and layout selection
    service = None
    backend = None
    cal_timestamp = None

    if not args.dry_run:
        with open(args.token_file, encoding="utf-8") as f:
            key_data = json.load(f)
        token = key_data.get("apikey") or key_data.get("token")

        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
        from qiskit import transpile

        service = QiskitRuntimeService(channel="ibm_quantum_platform", token=token, instance="open-instance")
        backend = service.backend(args.backend)
        props = backend.properties(refresh=True)
        cal_timestamp = str(props.last_update_date) if props else "unknown"

        # Qubit selection if not given
        if args.qubits is None:
            # Algorithmic selection using preregistered rule
            coupling_map = backend.coupling_map
            adj = {}
            for edge in coupling_map:
                u, v = edge[0], edge[1]
                adj.setdefault(u, set()).add(v)
                adj.setdefault(v, set()).add(u)
            candidates = []
            seen = set()
            for b in adj:
                neighbors = sorted(list(adj[b]))
                for i in range(len(neighbors)):
                    for j in range(i + 1, len(neighbors)):
                        a, c = neighbors[i], neighbors[j]
                        chain = (min(a, c), b, max(a, c))
                        if chain not in seen:
                            seen.add(chain)
                            candidates.append(chain)
            valid = []
            for a, b, c in candidates:
                err_a = props.readout_error(a)
                err_b = props.readout_error(b)
                err_c = props.readout_error(c)
                if err_a <= 0.03 and err_b <= 0.03 and err_c <= 0.03:
                    valid.append(((err_a + err_b + err_c), (a, b, c)))
            valid.sort(key=lambda x: (x[0], x[1][0]))
            args.qubits = list(valid[0][1])
            print(f"Algorithmic layout selected: {args.qubits} (Readout error sum: {valid[0][0]*100:.2f}%)")
        else:
            print(f"Using explicitly specified layout: {args.qubits}")
    else:
        from qiskit_aer import AerSimulator
        from qiskit import transpile
        backend = AerSimulator()
        cal_timestamp = "dryrun_sim"
        if args.qubits is None:
            args.qubits = [0, 1, 2]

    # Save campaign metadata
    campaign_info = {
        "preregistration": "docs/PREREGISTRATION.md",
        "backend": args.backend,
        "physical_qubits": args.qubits,
        "seed": args.seed,
        "planned_pairs": args.pairs,
        "shots": args.shots,
        "calibration_timestamp": cal_timestamp,
        "start_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "secret_bits": secret_bits.tolist(),
        "completed_pairs": 0,
        "status": "RUNNING"
    }
    with open(run_dir / "campaign.json", "w", encoding="utf-8") as f:
        json.dump(campaign_info, f, indent=2)

    # Transpile circuit templates once
    circ_B_templates = build_job_B_circuits()
    if not args.dry_run:
        isa_B_circuits = [transpile(c, backend=backend, initial_layout=args.qubits, optimization_level=1) for c in circ_B_templates]
    else:
        isa_B_circuits = [transpile(c, backend=backend, optimization_level=1) for c in circ_B_templates]

    completed_pairs = 0
    pairs_data = []

    print("\nStarting 40 Job Pairs Execution...")
    print(f"{'Pair':>5} | {'Secret':>8} | {'Job A ID':>20} | {'Job B ID':>20} | {'Gap (s)':>8} | {'B P1 (Q0, Q1, Q2)':>24}")
    print("-" * 95)

    sampler = None if args.dry_run else SamplerV2(backend)

    for k in range(args.pairs):
        s_bits = secret_bits[k].tolist()
        circ_A = build_job_A_circuit(s_bits)

        # Transpile A circuit
        if not args.dry_run:
            isa_A = transpile(circ_A, backend=backend, initial_layout=args.qubits, optimization_level=1)
        else:
            isa_A = transpile(circ_A, backend=backend, optimization_level=1)

        # 1. Execute Job A_k
        t_submit_A = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            if not args.dry_run:
                job_A = sampler.run([isa_A], shots=args.shots)
                id_A = job_A.job_id()
                res_A = job_A.result()
                counts_A = res_A[0].data.c.get_counts()
            else:
                id_A = f"dry_A_{k:03d}"
                res_A = backend.run(isa_A, shots=args.shots).result()
                counts_A = res_A.get_counts()
        except Exception as e:
            print(f"\n[ERROR] Job A_{k} failed: {e}")
            break

        t_return_A = datetime.datetime.now(datetime.timezone.utc).isoformat()
        t_return_A_epoch = time.time()

        # 2. Immediately submit Job B_k
        t_submit_B_epoch = time.time()
        t_submit_B = datetime.datetime.now(datetime.timezone.utc).isoformat()
        gap_seconds = t_submit_B_epoch - t_return_A_epoch

        try:
            if not args.dry_run:
                job_B = sampler.run(isa_B_circuits, shots=args.shots)
                id_B = job_B.job_id()
                res_B = job_B.result()
                # Circuit 0 is main measurement (classical register c)
                counts_B0 = res_B[0].data.c.get_counts()
                # Circuits 1-4 are positive control (registers m1, m2)
                counts_ctrl = []
                for c_idx in range(1, 5):
                    counts_ctrl.append({
                        "m1": res_B[c_idx].data.m1.get_counts(),
                        "m2": res_B[c_idx].data.m2.get_counts()
                    })
            else:
                id_B = f"dry_B_{k:03d}"
                res_B = backend.run(isa_B_circuits, shots=args.shots).result()
                counts_B0 = res_B.get_counts(isa_B_circuits[0])
                counts_ctrl = []
                for c_idx in range(1, 5):
                    raw_c = res_B.get_counts(isa_B_circuits[c_idx])
                    # Parse 'm2 m1'
                    c_m1 = {}
                    c_m2 = {}
                    for bstr, cnt in raw_c.items():
                        parts = bstr.split(" ")
                        m2_str = parts[0]
                        m1_str = parts[1] if len(parts) > 1 else parts[0]
                        c_m1[m1_str] = c_m1.get(m1_str, 0) + cnt
                        c_m2[m2_str] = c_m2.get(m2_str, 0) + cnt
                    counts_ctrl.append({"m1": c_m1, "m2": c_m2})
        except Exception as e:
            print(f"\n[ERROR] Job B_{k} failed: {e}")
            break

        t_return_B = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Extract P1 for Circuit 0 (main measurement)
        p1_B0 = extract_p1_from_counts(counts_B0, args.shots)
        p1_A = extract_p1_from_counts(counts_A, args.shots)

        pair_record = {
            "pair_index": k,
            "secret_bits": s_bits,
            "job_A": {
                "job_id": id_A,
                "submit_time": t_submit_A,
                "return_time": t_return_A,
                "p1": p1_A,
                "counts": counts_A
            },
            "job_B": {
                "job_id": id_B,
                "submit_time": t_submit_B,
                "return_time": t_return_B,
                "gap_seconds": gap_seconds,
                "main_measurement_p1": p1_B0,
                "main_counts": counts_B0,
                "positive_control_counts": counts_ctrl
            }
        }

        # Save pair file
        with open(run_dir / f"pair_{k:04d}.json", "w", encoding="utf-8") as f:
            json.dump(pair_record, f, indent=2)

        pairs_data.append(pair_record)
        completed_pairs += 1

        # Console print
        bits_str = "".join(str(b) for b in s_bits)
        p1_str = f"[{p1_B0[0]:.4f}, {p1_B0[1]:.4f}, {p1_B0[2]:.4f}]"
        print(f"{k:5d} | {bits_str:>8} | {id_A:>20} | {id_B:>20} | {gap_seconds:8.2f} | {p1_str:>24}")

        # Update campaign json periodically
        campaign_info["completed_pairs"] = completed_pairs
        with open(run_dir / "campaign.json", "w", encoding="utf-8") as f:
            json.dump(campaign_info, f, indent=2)

    campaign_info["status"] = "COMPLETED" if completed_pairs == args.pairs else "INTERRUPTED"
    campaign_info["end_time"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(run_dir / "campaign.json", "w", encoding="utf-8") as f:
        json.dump(campaign_info, f, indent=2)

    print("\n" + "=" * 75)
    print(f"Data acquisition finished! Completed pairs: {completed_pairs}/{args.pairs}")
    print("Invoking preregistered analysis script...")
    print("=" * 75)

    # Run analysis script
    from space_memory_analyze import analyze_run
    analyze_run(run_dir)

if __name__ == "__main__":
    main()
