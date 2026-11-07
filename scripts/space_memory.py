#!/usr/bin/env python3
"""
space_memory.py: "emlek a terben" teszt (elore regisztralva: docs/PREREGISTRATION-space_memory.md).

Kerdes: marad-e informacio a qubiten egyik jobrol a kovetkezore, reset utan?

  A_k job: titkos bit s[k,q] szerint X a qubiten, majd meres (1 aramkor).
  B_k job: kozvetlenul A_k utan. 0. aramkor: csak meres (FO MERES).
           1-4. aramkor: POZITIV KONTROLL jobon belul:
             u in {000, 111} x tau in {0, 20 us}: X^u, meres (c1), reset, delay tau, meres (c2).
             A reset tokeletlensege miatt c2-ben tobb az 1-es, ha u = 1 (ismert, nem nulla hatas).

Kimenet: measurement_raw/space_memory/<tag>/pairNNN.json + campaign.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
TAUS_US = [0, 20]


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--token-file", default=r"C:\Users\mater\Downloads\apikey (5).json")
    p.add_argument("--instance", default="open-instance")
    p.add_argument("--backend", default="ibm_kingston")
    p.add_argument("--qubits", type=int, nargs=3, default=[48, 49, 50])
    p.add_argument("--pairs", type=int, default=40)
    p.add_argument("--shots", type=int, default=1024)
    p.add_argument("--seed", type=int, default=20261110)
    p.add_argument("--dry-run", action="store_true", help="Helyi szimulacio QPU nelkul")
    p.add_argument("--dry-memory", type=float, default=0.0,
                   help="Csak dry run: beepitett jobok kozotti memoria (P1 novekmeny, ha s=1)")
    p.add_argument("--dry-reset-err", type=float, default=0.01, help="Csak dry run: reset hiba")
    p.add_argument("--dry-ro", type=float, default=0.008, help="Csak dry run: P(1|0) kiolvasasi hiba")
    return p.parse_args()


def secret_bits(pairs, seed):
    """Qubitenkent kiegyensulyozott (fele 1, fele 0), egymastol fuggetlenul keverve."""
    rng = np.random.default_rng(seed)
    cols = []
    for _ in range(3):
        col = np.array([1] * (pairs // 2) + [0] * (pairs - pairs // 2))
        rng.shuffle(col)
        cols.append(col)
    return np.stack(cols, axis=1)  # [pairs, 3]


def build_circuits(s_bits):
    from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister

    qa = QuantumCircuit(3, 3, name="A")
    for q in range(3):
        if s_bits[q]:
            qa.x(q)
    qa.measure(range(3), range(3))

    qb = QuantumCircuit(3, 3, name="B_main")
    qb.measure(range(3), range(3))

    ctrls = []
    for tau in TAUS_US:
        for u in (0, 1):
            qr = QuantumRegister(3, "q")
            c1 = ClassicalRegister(3, "c1")
            c2 = ClassicalRegister(3, "c2")
            qc = QuantumCircuit(qr, c1, c2, name=f"ctrl_u{u}_tau{tau}")
            if u:
                qc.x(qr)
            qc.measure(qr, c1)
            qc.reset(qr)
            if tau > 0:
                qc.delay(tau, qr, unit="us")
            qc.measure(qr, c2)
            ctrls.append({"u": u, "tau_us": tau, "circuit": qc})
    return qa, qb, ctrls


def marginals(counts, nbits=3):
    """P(1) qubitenkent egy 3 bites regiszter counts-abol (bitstring: q2 q1 q0)."""
    shots = sum(counts.values())
    p1 = [0.0] * nbits
    for bs, n in counts.items():
        bs = bs.replace(" ", "")
        for q in range(nbits):
            if bs[-1 - q] == "1":
                p1[q] += n
    return [x / shots for x in p1], shots


def dry_counts(p1s, shots, rng):
    """Fuggetlen qubitenkenti binomialis mintavetel -> counts (a dontes csak marginalisokat hasznal)."""
    bits = np.stack([rng.random(shots) < p for p in p1s], axis=1)
    counts = {}
    for row in bits:
        key = "".join("1" if row[q] else "0" for q in (2, 1, 0))
        counts[key] = counts.get(key, 0) + 1
    return counts


def main():
    args = parse_args()
    S = secret_bits(args.pairs, args.seed)
    tag = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + ("_dry" if args.dry_run else "")
    out = REPO / "measurement_raw" / "space_memory" / tag
    out.mkdir(parents=True, exist_ok=True)

    campaign = {
        "preregistration": "docs/PREREGISTRATION-space_memory.md",
        "tag": tag, "backend": "dry-run" if args.dry_run else args.backend,
        "physical_qubits": args.qubits, "pairs": args.pairs, "shots": args.shots,
        "seed": args.seed, "taus_us": TAUS_US, "dry_run": args.dry_run,
        "secret_bits": S.tolist(), "start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if args.dry_run:
        campaign["dry_params"] = {"memory": args.dry_memory, "reset_err": args.dry_reset_err, "ro": args.dry_ro}
        rng = np.random.default_rng(args.seed + 1)
    else:
        from qiskit import transpile
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
        with open(args.token_file, encoding="utf-8") as f:
            kd = json.load(f)
        service = QiskitRuntimeService(channel="ibm_quantum_platform",
                                       token=kd.get("apikey") or kd.get("token"), instance=args.instance)
        backend = service.backend(args.backend)
        props = backend.properties(refresh=True)
        campaign["calibration_start"] = str(props.last_update_date)
        sampler = SamplerV2(backend)

        def run(circs):
            isa = [transpile(c, backend=backend, initial_layout=args.qubits, optimization_level=1) for c in circs]
            t0 = time.time()
            job = sampler.run(isa, shots=args.shots)
            res = job.result()
            t1 = time.time()
            regs = []
            for i, c in enumerate(circs):
                d = res[i].data
                regs.append({name: getattr(d, name).get_counts() for name in [cr.name for cr in c.cregs]})
            return job.job_id(), t0, t1, regs

    (out / "campaign.json").write_text(json.dumps(campaign, indent=2), encoding="utf-8")

    for k in range(args.pairs):
        s = S[k]
        qa, qb, ctrls = build_circuits(s)
        rec = {"pair": k, "secret_bits": s.tolist()}

        if args.dry_run:
            ca = dry_counts([1 - args.dry_ro if s[q] else args.dry_ro for q in range(3)], args.shots, rng)
            cb = dry_counts([args.dry_ro + args.dry_memory * s[q] for q in range(3)], args.shots, rng)
            regsA = [{"c": ca}]
            regsB = [{"c": cb}]
            for ct in ctrls:
                p2 = args.dry_ro + (args.dry_reset_err * (1.0 if ct["tau_us"] == 0 else 0.5)) * ct["u"]
                regsB.append({"c1": dry_counts([1 - args.dry_ro if ct["u"] else args.dry_ro] * 3, args.shots, rng),
                              "c2": dry_counts([p2] * 3, args.shots, rng)})
            rec["A"] = {"job_id": None, "t_submit": None, "t_done": None}
            rec["B"] = {"job_id": None, "t_submit": None, "t_done": None}
        else:
            try:
                ja, ta0, ta1, regsA = run([qa])
                jb, tb0, tb1, regsB = run([qb] + [ct["circuit"] for ct in ctrls])
            except Exception as e:
                print(f"\n[INFO] Run stopped at pair {k}: {e}")
                campaign["interrupted_reason"] = str(e)
                break
            rec["A"] = {"job_id": ja, "t_submit": ta0, "t_done": ta1}
            rec["B"] = {"job_id": jb, "t_submit": tb0, "t_done": tb1}
            rec["gap_s"] = tb0 - ta1

        rec["A"]["p1"] = marginals(regsA[0]["c"])[0]
        rec["A"]["counts"] = regsA[0]["c"]
        rec["B"]["p1_main"] = marginals(regsB[0]["c"])[0]
        rec["B"]["counts_main"] = regsB[0]["c"]
        rec["controls"] = []
        for ct, rg in zip(ctrls, regsB[1:]):
            rec["controls"].append({"u": ct["u"], "tau_us": ct["tau_us"],
                                    "p1_c1": marginals(rg["c1"])[0], "p1_c2": marginals(rg["c2"])[0],
                                    "counts_c1": rg["c1"], "counts_c2": rg["c2"]})
        (out / f"pair{k:03d}.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
        print(f"pair {k:02d} s={s.tolist()} B_main P1={np.round(rec['B']['p1_main'], 4).tolist()}")

    completed_count = len(list(out.glob("pair*.json")))
    campaign["end_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    campaign["completed_pairs"] = completed_count
    if not args.dry_run:
        campaign["calibration_end"] = str(backend.properties(refresh=True).last_update_date)
    (out / "campaign.json").write_text(json.dumps(campaign, indent=2), encoding="utf-8")
    print("Kesz:", out)

    if completed_count >= 20:
        import subprocess
        print("\nFut az elemzes...")
        subprocess.run([sys.executable, str(REPO / "scripts" / "space_memory_analyze.py"), str(out)])


if __name__ == "__main__":
    main()
