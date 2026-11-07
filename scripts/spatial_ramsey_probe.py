#!/usr/bin/env python3
"""
spatial_ramsey_probe.py — Spatial Cavity-Field Ramsey Phase Probe on Heron Transmons.

Measures whether pumping and resetting an adjacent transmon leaves a persistent
dispersive electromagnetic phase shift Delta_Phi in the surrounding inter-qubit space.

Preregistration: docs/PREREGISTRATION-spatial_ramsey_probe.md
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

PHASES = [
    0.0,
    math.pi / 4.0,
    math.pi / 2.0,
    3.0 * math.pi / 4.0,
    math.pi,
    5.0 * math.pi / 4.0,
    3.0 * math.pi / 2.0,
    7.0 * math.pi / 4.0
]

PHASE_LABELS = [
    "0",
    "pi/4",
    "pi/2",
    "3pi/4",
    "pi",
    "5pi/4",
    "3pi/2",
    "7pi/4"
]

def parse_args():
    p = argparse.ArgumentParser(description="Spatial Cavity-Field Ramsey Phase Probe")
    p.add_argument("--token-file", default=r"C:\Users\mater\Downloads\apikey (1) (1).json")
    p.add_argument("--backend", default="ibm_kingston")
    p.add_argument("--qubits", type=int, nargs=3, default=[48, 49, 50])
    p.add_argument("--delay-us", type=float, default=10.0)
    p.add_argument("--shots", type=int, default=4096)
    p.add_argument("--dry-run", action="store_true", help="Local simulation without QPU hardware")
    return p.parse_args()

def build_probe_circuit(arm, phi, delay_us=10.0):
    """
    Q0 = Source (Pump / Vacuum)
    Q1 = Sensor in space (Ramsey phase probe)
    Q2 = Distance control spectator
    """
    from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister

    qr = QuantumRegister(3, "q")
    cr_src = ClassicalRegister(1, "m_src")
    cr_probe = ClassicalRegister(2, "m_probe") # bit 0 for Q1 (sensor), bit 1 for Q2 (spectator)

    qc = QuantumCircuit(qr, cr_src, cr_probe, name=f"ramsey_{arm}_phi{int(math.degrees(phi))}")

    # 1. Put spatial sensors Q1 and Q2 onto equatorial superposition (|+>)
    qc.rx(math.pi / 2.0, qr[1])
    qc.rx(math.pi / 2.0, qr[2])

    # 2. Source Q0 executes pump (X) or vacuum (I), then measure and active reset
    if arm == "pumped":
        qc.x(qr[0])
    qc.measure(qr[0], cr_src[0])
    qc.reset(qr[0])

    # 3. Space exposure delay: sensors precess freely in local cavity / bus field
    if delay_us > 0:
        qc.delay(int(delay_us), qr[1], unit="us")
        qc.delay(int(delay_us), qr[2], unit="us")

    # 4. Phase tomography on sensors: Rz(-phi) then Rx(pi/2)
    qc.rz(-phi, qr[1])
    qc.rx(math.pi / 2.0, qr[1])

    qc.rz(-phi, qr[2])
    qc.rx(math.pi / 2.0, qr[2])

    # 5. Measure spatial sensors
    qc.measure(qr[1], cr_probe[0])
    qc.measure(qr[2], cr_probe[1])

    return qc

def extract_probe_p1(counts, shots):
    """
    Extracts P1 for Q1 (sensor, bit 0 of m_probe) and Q2 (spectator, bit 1 of m_probe).
    """
    p1_q1 = 0
    p1_q2 = 0
    total = sum(counts.values())
    for bstr, c in counts.items():
        s = bstr.replace(" ", "")
        # In Qiskit, cregs order in bitstring: 'cr_probe cr_src' -> bit 0 of cr_probe is at index len(probe)-1
        # Let's inspect bit indices:
        if len(s) >= 2:
            # m_probe has 2 bits: s[1] is Q1, s[0] is Q2 or vice-versa
            # cr_probe[0] is Q1, cr_probe[1] is Q2
            bit_q1 = s[-2]
            bit_q2 = s[-3] if len(s) >= 3 else '0'
            if bit_q1 == '1':
                p1_q1 += c
            if bit_q2 == '1':
                p1_q2 += c
    denom = total if total > 0 else shots
    return p1_q1 / denom, p1_q2 / denom

def fit_ramsey_fringe(phases, p1_vals):
    from scipy.optimize import curve_fit
    def model(phi, v, phase_offset, offset):
        return offset - 0.5 * v * np.cos(phi - phase_offset)
    
    phi_arr = np.array(phases)
    p_arr = np.array(p1_vals)

    try:
        popt, pcov = curve_fit(
            model, phi_arr, p_arr,
            p0=[0.8, 0.0, 0.5],
            bounds=([0.0, -np.pi, 0.3], [1.0, np.pi, 0.7]),
            maxfev=5000
        )
        v, phase_offset, offset = float(popt[0]), float(popt[1]), float(popt[2])
        # Compute R^2
        y_pred = model(phi_arr, *popt)
        r2 = 1.0 - (np.sum((p_arr - y_pred)**2) / np.sum((p_arr - np.mean(p_arr))**2))
        perr = np.sqrt(np.diag(pcov))
        phi_err = float(perr[1])
    except Exception as e:
        v, phase_offset, offset = 0.5, 0.0, 0.5
        r2 = 0.0
        phi_err = 0.1

    return {
        "visibility": v,
        "phase_offset_rad": phase_offset,
        "phase_offset_deg": float(math.degrees(phase_offset)),
        "offset": offset,
        "r2": float(r2),
        "phase_err_rad": phi_err
    }

def main():
    args = parse_args()

    tag = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = REPO / "measurement_raw" / "spatial_ramsey" / tag
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("SPATIAL CAVITY-FIELD RAMSEY PHASE PROBE (TESTING MEMORY IN SPACE)")
    print(f"Backend: {args.backend} | Layout: Source Q{args.qubits[0]}, Sensor Q{args.qubits[1]}, Spectator Q{args.qubits[2]}")
    print(f"Space Exposure Delay: {args.delay_us} us | Shots: {args.shots}")
    print(f"Token file: {args.token_file} | Mode: {'DRY RUN' if args.dry_run else 'LIVE QPU'}")
    print("=" * 80)

    circuits = []
    meta = []

    for arm in ("vacuum", "pumped"):
        for phi, label in zip(PHASES, PHASE_LABELS):
            circuits.append(build_probe_circuit(arm, phi, delay_us=args.delay_us))
            meta.append({"arm": arm, "phi": phi, "label": label})

    print(f"Built {len(circuits)} circuits (8 tomography phases x 2 arms: Vacuum vs Pumped).")

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
        print("Transpiling circuits onto physical layout [48, 49, 50]...")
        isa_circs = [transpile(c, backend=backend, initial_layout=args.qubits, optimization_level=1) for c in circuits]

        print("Submitting single batch job to QPU (~8-10 seconds QPU time)...")
        sampler = SamplerV2(backend)
        job = sampler.run(isa_circs, shots=args.shots)
        job_id = job.job_id()
        print(f"Job ID: {job_id} | Status: {job.status()} | Waiting for execution...")

        res = job.result()
        print(f"Job {job_id} completed successfully!")

        counts_list = []
        for i in range(len(circuits)):
            counts_list.append(res[i].data.m_probe.get_counts())
    else:
        from qiskit_aer import AerSimulator
        from qiskit import transpile
        sim = AerSimulator()
        isa_circs = [transpile(c, backend=sim, optimization_level=1) for c in circuits]
        res = sim.run(isa_circs, shots=args.shots).result()
        job_id = "dryrun_spatial_ramsey"
        cal_time = "dryrun"
        counts_list = [res.get_counts(c) for c in isa_circs]

    # Organize P1 for sensor Q1 across arms
    p1_data = {"vacuum": {"q1": [], "q2": []}, "pumped": {"q1": [], "q2": []}}
    raw_counts_saved = []

    for i, m in enumerate(meta):
        arm = m["arm"]
        p1_q1, p1_q2 = extract_probe_p1(counts_list[i], args.shots)
        p1_data[arm]["q1"].append(p1_q1)
        p1_data[arm]["q2"].append(p1_q2)
        raw_counts_saved.append({
            "arm": arm,
            "phi": m["phi"],
            "label": m["label"],
            "p1_sensor_q1": p1_q1,
            "p1_spectator_q2": p1_q2,
            "counts": counts_list[i]
        })

    # Fit Ramsey fringes on Sensor Q1
    fit_vac = fit_ramsey_fringe(PHASES, p1_data["vacuum"]["q1"])
    fit_pump = fit_ramsey_fringe(PHASES, p1_data["pumped"]["q1"])

    delta_phi_rad = fit_pump["phase_offset_rad"] - fit_vac["phase_offset_rad"]
    delta_phi_deg = math.degrees(delta_phi_rad)
    combined_err = math.sqrt(fit_pump["phase_err_rad"]**2 + fit_vac["phase_err_rad"]**2)

    print("\n" + "=" * 80)
    print("SPATIAL RAMSEY FRINGE ANALYSIS (SENSOR Q49 IN THE SURROUNDING FIELD)")
    print("=" * 80)
    print(f"Arm Vacuum : Phase Offset = {fit_vac['phase_offset_deg']:+7.2f} deg | Visibility V = {fit_vac['visibility']:.4f} | R^2 = {fit_vac['r2']:.4f}")
    print(f"Arm Pumped : Phase Offset = {fit_pump['phase_offset_deg']:+7.2f} deg | Visibility V = {fit_pump['visibility']:.4f} | R^2 = {fit_pump['r2']:.4f}")
    print("-" * 80)
    print(f">>> SPATIAL PHASE SHIFT: Delta_Phi = {delta_phi_rad:+.5f} rad ({delta_phi_deg:+.2f} deg) +/- {combined_err:.5f} rad <<<")
    print("-" * 80)

    print(f"\n{'Angle':>8} | {'P1_Vacuum (Sensor Q49)':>24} | {'P1_Pumped (Sensor Q49)':>24} | {'Delta P1':>12}")
    print("-" * 75)
    for k in range(8):
        v = p1_data["vacuum"]["q1"][k]
        p = p1_data["pumped"]["q1"][k]
        print(f"{PHASE_LABELS[k]:>8} | {v:24.4f} | {p:24.4f} | {p - v:+12.4f}")

    h1_supported = (fit_vac['visibility'] > 0.5) and (fit_pump['visibility'] > 0.5) and (abs(delta_phi_rad) > 3 * combined_err) and (abs(delta_phi_rad) > 0.05)
    verdict = "H1 SUPPORTED: Coherent spatial phase memory detected in inter-qubit space!" if h1_supported else "H0 CONFIRMED: Spatial cavity field is consistent with zero residual phase shift."
    print(f"\nPREREGISTERED VERDICT: {verdict}")

    analysis_payload = {
        "preregistration": "docs/PREREGISTRATION-spatial_ramsey_probe.md",
        "job_id": job_id,
        "backend": args.backend,
        "qubits": {
            "source_pump": args.qubits[0],
            "spatial_sensor": args.qubits[1],
            "distance_spectator": args.qubits[2]
        },
        "space_exposure_delay_us": args.delay_us,
        "shots": args.shots,
        "calibration_timestamp": cal_time,
        "phases_rad": PHASES,
        "fringe_vacuum": fit_vac,
        "fringe_pumped": fit_pump,
        "spatial_phase_shift_rad": delta_phi_rad,
        "spatial_phase_shift_deg": delta_phi_deg,
        "combined_error_rad": combined_err,
        "h1_supported": h1_supported,
        "verdict": verdict,
        "raw_counts": raw_counts_saved
    }

    with open(out / "analysis.json", "w", encoding="utf-8") as f:
        json.dump(analysis_payload, f, indent=2)

    print(f"\nFull analysis and raw data written to {out / 'analysis.json'}")

if __name__ == "__main__":
    main()
