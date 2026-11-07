#!/usr/bin/env python3
"""
zero_iq_memory.py: "nezzunk bele a 0-ba" teszt, futtatas + elemzes egy fajlban.
Elore regisztralva: docs/PREREGISTRATION-zero_iq_memory.md

Kerdes: a 0-nak kerekitett lovesek nyers IQ-pontjai (a "0-felho") hordoznak-e nyomot
arrol, mit csinalt az elozo, kulon job ugyanazokon a qubiteken?

  A_k job: titkos bit s[k,q] szerint X, majd meres (IQ).
  B_k job (kozvetlenul A_k utan):
    0  main : csak meres                          <- FO MERES (a 0-felho kozeppontja)
    1  cal0 : csak meres                          <- tengelybecsleshez
    2  cal1 : X, meres                            <- tengelybecsleshez
    3  ctrl_u0: meres(c1), reset, meres(c2)       <- pozitiv kontroll, jobon belul
    4  ctrl_u1: X, meres(c1), reset, meres(c2)

Hasznalat:
  python zero_iq_memory.py run --qubits 48 49 50 --backend ibm_kingston --token-file <kulcs.json>
  python zero_iq_memory.py run --dry-run [--dry-memory 0.003]
  python zero_iq_memory.py analyze measurement_raw/zero_iq/<mappa>
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
N_PERM = 200_000
B_NAMES = ["main", "cal0", "cal1", "ctrl_u0", "ctrl_u1"]


# ----------------------------------------------------------------------------- aramkorok

def secret_bits(pairs, seed):
    rng = np.random.default_rng(seed)
    cols = []
    for _ in range(3):
        col = np.array([1] * (pairs // 2) + [0] * (pairs - pairs // 2))
        rng.shuffle(col)
        cols.append(col)
    return np.stack(cols, axis=1)  # [pairs, 3]


def build_circuits(s_bits):
    from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister

    def simple(name, xs):
        qc = QuantumCircuit(3, 3, name=name)
        for q in range(3):
            if xs[q]:
                qc.x(q)
        qc.measure(range(3), range(3))
        return qc

    def ctrl(u):
        qr = QuantumRegister(3, "q")
        c1, c2 = ClassicalRegister(3, "c1"), ClassicalRegister(3, "c2")
        qc = QuantumCircuit(qr, c1, c2, name=f"ctrl_u{u}")
        if u:
            qc.x(qr)
        qc.measure(qr, c1)
        qc.reset(qr)
        qc.measure(qr, c2)
        return qc

    A = simple("A", s_bits)
    B = [simple("main", [0, 0, 0]), simple("cal0", [0, 0, 0]), simple("cal1", [1, 1, 1]), ctrl(0), ctrl(1)]
    return A, B


# ----------------------------------------------------------------------------- dry-run szimulacio

class DryChip:
    """Gauss-felhok az IQ-sikon, jobonkenti kis erosites/fazis drifttel."""

    def __init__(self, rng, memory=0.0, reset_err=0.015, thermal=0.01, ro=0.01, photon=0.01):
        self.rng, self.memory, self.reset_err, self.thermal, self.ro, self.photon = rng, memory, reset_err, thermal, ro, photon
        self.c0 = np.array([3 + 1j, 2.5 - 1.5j, 3.5 + 0.5j])
        self.sep = np.array([1.2 * np.exp(0.4j), 1.0 * np.exp(-0.9j), 1.1 * np.exp(2.0j)])
        self.sigma = np.abs(self.sep) / 8
        self.new_job()

    def new_job(self):
        self.drift = (1 + 0.01 * self.rng.standard_normal()) * np.exp(1j * np.deg2rad(0.5) * self.rng.standard_normal())

    def shots(self, q, n, p_excited, shift=0.0):
        exc = self.rng.random(n) < p_excited
        centre = np.where(exc, self.c0[q] + self.sep[q], self.c0[q] + shift * self.sep[q])
        noise = self.sigma[q] * (self.rng.standard_normal(n) + 1j * self.rng.standard_normal(n))
        return ((centre + noise) * self.drift).astype(np.complex64)

    def run_A(self, s, n):
        self.new_job()
        return {"c": np.stack([self.shots(q, n, 1 - self.ro if s[q] else self.thermal) for q in range(3)], axis=1)}

    def run_B(self, s, n):
        self.new_job()
        out = {}
        out["main"] = {"c": np.stack([self.shots(q, n, self.thermal, self.memory * s[q]) for q in range(3)], axis=1)}
        out["cal0"] = {"c": np.stack([self.shots(q, n, self.thermal) for q in range(3)], axis=1)}
        out["cal1"] = {"c": np.stack([self.shots(q, n, 1 - self.ro) for q in range(3)], axis=1)}
        for u in (0, 1):
            c1 = np.stack([self.shots(q, n, 1 - self.ro if u else self.thermal) for q in range(3)], axis=1)
            c2 = np.stack([self.shots(q, n, self.thermal + self.reset_err * u, self.photon * u) for q in range(3)], axis=1)
            out[f"ctrl_u{u}"] = {"c1": c1, "c2": c2}
        return out


# ----------------------------------------------------------------------------- futtatas

def cmd_run(args):
    S = secret_bits(args.pairs, args.seed)
    tag = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + ("_dry" if args.dry_run else "")
    out = REPO / "measurement_raw" / "zero_iq" / tag
    out.mkdir(parents=True, exist_ok=True)
    camp = {"preregistration": "docs/PREREGISTRATION-zero_iq_memory.md", "tag": tag,
            "backend": "dry-run" if args.dry_run else args.backend, "physical_qubits": args.qubits,
            "pairs": args.pairs, "shots": args.shots, "seed": args.seed, "meas_type": "kerneled",
            "dry_run": args.dry_run, "secret_bits": S.tolist(),
            "start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    if args.dry_run:
        chip = DryChip(np.random.default_rng(args.seed + 1), memory=args.dry_memory)
        camp["dry_params"] = {"memory": args.dry_memory}
    else:
        from qiskit import transpile
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
        kd = json.load(open(args.token_file, encoding="utf-8"))
        service = QiskitRuntimeService(channel="ibm_quantum_platform",
                                       token=kd.get("apikey") or kd.get("token"), instance=args.instance)
        backend = service.backend(args.backend)
        levels = getattr(backend.configuration(), "meas_levels", None)
        camp["backend_meas_levels"] = levels
        if levels is not None and 1 not in levels:
            sys.exit(f"A {args.backend} nem ad nyers IQ-adatot (meas_levels={levels}). Leallok, kvota nem fogyott.")
        camp["calibration_start"] = str(backend.properties(refresh=True).last_update_date)
        sampler = SamplerV2(backend)
        sampler.options.execution.meas_type = "kerneled"

        def run(circs):
            isa = [transpile(c, backend=backend, initial_layout=args.qubits, optimization_level=1) for c in circs]
            t0 = time.time()
            job = sampler.run(isa, shots=args.shots)
            res = job.result()
            t1 = time.time()
            regs = []
            for i, c in enumerate(circs):
                d = res[i].data
                regs.append({cr.name: np.asarray(getattr(d, cr.name)).astype(np.complex64) for cr in c.cregs})
            return job.job_id(), t0, t1, regs

    (out / "campaign.json").write_text(json.dumps(camp, indent=2), encoding="utf-8")

    done = 0
    for k in range(args.pairs):
        s = S[k]
        meta = {"pair": k, "secret_bits": s.tolist()}
        arrays = {}
        try:
            if args.dry_run:
                regsA = chip.run_A(s, args.shots)
                regsB = chip.run_B(s, args.shots)
                meta["A"] = meta["B"] = None
            else:
                A, B = build_circuits(s)
                ja, ta0, ta1, rA = run([A])
                jb, tb0, tb1, rB = run(B)
                regsA = rA[0]
                regsB = dict(zip(B_NAMES, rB))
                meta["A"] = {"job_id": ja, "t_submit": ta0, "t_done": ta1}
                meta["B"] = {"job_id": jb, "t_submit": tb0, "t_done": tb1}
                meta["local_gap_s"] = tb0 - ta1  # helyi falioraido, NEM a chipen eltelt ido
        except Exception as e:
            print(f"[INFO] Leallt a(z) {k}. parnal: {e}")
            camp["interrupted_reason"] = str(e)
            break
        arrays["A__c"] = regsA["c"]
        for name, regs in regsB.items():
            for cr, arr in regs.items():
                arrays[f"B__{name}__{cr}"] = arr
        np.savez_compressed(out / f"pair{k:03d}.npz", **arrays)
        (out / f"pair{k:03d}.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        done += 1
        print(f"par {k:02d} kesz")  # szandekosan nem ir ki eredmenyt: vak futas

    camp["end_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    camp["completed_pairs"] = done
    if not args.dry_run:
        camp["calibration_end"] = str(backend.properties(refresh=True).last_update_date)
    (out / "campaign.json").write_text(json.dumps(camp, indent=2), encoding="utf-8")
    print("Kesz:", out)
    if done >= 20:
        analyze(out)
    else:
        print("Kevesebb mint 20 par: az elore rogzitett szabaly szerint nem ertekelheto.")


# ----------------------------------------------------------------------------- elemzes

def load(d):
    camp = json.loads((d / "campaign.json").read_text(encoding="utf-8"))
    pairs = []
    for f in sorted(d.glob("pair*.npz")):
        meta = json.loads(f.with_suffix(".json").read_text(encoding="utf-8"))
        z = np.load(f)
        pairs.append((meta, {k: z[k] for k in z.files}))
    return camp, pairs


def cmedian(z):
    """Felho kozeppontja: a valos es kepzetes resz medianja (robosztus a kis szatellitekre)."""
    return complex(float(np.median(z.real)), float(np.median(z.imag)))


def global_axes(pairs):
    """Kozos 0->1 tengely qubitenkent, az osszes B job cal0/cal1 korenek medianjabol."""
    axes = []
    for q in range(3):
        z0 = np.concatenate([p["B__cal0__c"][:, q] for _, p in pairs])
        z1 = np.concatenate([p["B__cal1__c"][:, q] for _, p in pairs])
        axes.append((cmedian(z0), cmedian(z1)))
    return axes


def job_axis(p, q):
    return cmedian(p["B__cal0__c"][:, q]), cmedian(p["B__cal1__c"][:, q])


def project(z, axis):
    """x: 0 = a 0-felho kozepe, 1 = az 1-felho kozepe; y: meroleges osszetevo, ugyanabban az egysegben."""
    c0, c1 = axis
    v = c1 - c0
    w = (z.astype(np.complex128) - c0) / v
    return w.real, w.imag


def blob_stats(z, axis):
    x, y = project(z, axis)
    core = x < 0.5
    return {"x0": float(x[core].mean()), "y0": float(y[core].mean()), "w0": float(x[core].std()),
            "p_exc": float((x >= 0.5).mean()), "p_tail": float((x >= 1.5).mean()), "x_all": float(x.mean())}


def label_delta(vals, S):
    return float(np.mean([vals[S[:, q] == 1, q].mean() - vals[S[:, q] == 0, q].mean() for q in range(3)]))


def perm_p(vals, S, obs, rng, chunk=20_000):
    n = S.shape[0]
    cnt = 0
    for start in range(0, N_PERM, chunk):
        m = min(chunk, N_PERM - start)
        tot = np.zeros(m)
        for q in range(3):
            L = S[:, q][np.argsort(rng.random((m, n)), axis=1)]
            n1 = L.sum(axis=1)
            tot += (L * vals[:, q]).sum(axis=1) / n1 - ((1 - L) * vals[:, q]).sum(axis=1) / (n - n1)
        cnt += int((np.abs(tot / 3) >= abs(obs) - 1e-15).sum())
    return (cnt + 1) / (N_PERM + 1)


def signflip_one_sided(d, rng):
    d = np.asarray(d)
    signs = rng.choice([-1, 1], size=(N_PERM, len(d)))
    return float((((signs * d).mean(axis=1)) >= d.mean() - 1e-15).sum() + 1) / (N_PERM + 1)


def analyze(d):
    d = Path(d)
    camp, pairs = load(d)
    S = np.array([m["secret_bits"] for m, _ in pairs])
    rng = np.random.default_rng(12345)
    G = global_axes(pairs)

    # A job ellenorzes: bitek es oszlopsorrend
    a_ok = float(np.mean([[(project(p["A__c"][:, q], G[q])[0] >= 0.5).mean() > 0.5 for q in range(3)] == np.array(m["secret_bits"]).astype(bool)
                          for m, p in pairs]))

    # Fo meres: globalis tengely + jobonkenti drift-korrekcio a cal1 (1-felho) kozeppontjahoz kotve.
    # A cal1 friss gerjesztett allapot, igy egy csak a 0-felhot erinto nyom nem tunik el a korrekcioval.
    def corr(pp, q):
        return G[q][1] / cmedian(pp["B__cal1__c"][:, q])

    st = [[blob_stats(p["B__main__c"][:, q] * corr(p, q), G[q]) for q in range(3)] for _, p in pairs]
    st_raw = [[blob_stats(p["B__main__c"][:, q], G[q]) for q in range(3)] for _, p in pairs]
    arr = {k: np.array([[st[i][q][k] for q in range(3)] for i in range(len(pairs))]) for k in st[0][0]}
    D = label_delta(arr["x0"], S)
    p = perm_p(arr["x0"], S, D, rng)
    h = len(pairs) // 2
    D1, D2 = label_delta(arr["x0"][:h], S[:h]), label_delta(arr["x0"][h:], S[h:])
    same = bool(np.sign(D1) == np.sign(D2) and D1 != 0)

    # Pozitiv kontroll: reset utani meres atlagos x-e, u=1 minusz u=0
    dk, dk_core = [], []
    for _, pp in pairs:
        s1 = [blob_stats(pp["B__ctrl_u1__c2"][:, q] * corr(pp, q), G[q]) for q in range(3)]
        s0 = [blob_stats(pp["B__ctrl_u0__c2"][:, q] * corr(pp, q), G[q]) for q in range(3)]
        dk.append(np.mean([s1[q]["x_all"] - s0[q]["x_all"] for q in range(3)]))
        dk_core.append(np.mean([s1[q]["x0"] - s0[q]["x0"] for q in range(3)]))
    p_ctrl = signflip_one_sided(dk, rng)
    ctrl_ok = bool(np.mean(dk) > 0 and p_ctrl < 0.01)

    # Masodlagos
    sec = {}
    for k in ("y0", "w0", "p_exc", "p_tail"):
        dd = label_delta(arr[k], S)
        sec[k] = {"Delta": dd, "p_two_sided": perm_p(arr[k], S, dd, rng)}
    xj = np.array([[blob_stats(pp["B__main__c"][:, q], job_axis(pp, q))["x0"] for q in range(3)] for _, pp in pairs])
    dj = label_delta(xj, S)
    sec["x0_per_job_cal0_cal1_axis"] = {"Delta": dj, "p_two_sided": perm_p(xj, S, dj, rng),
                                        "note": "erzekenyebb, de egy B jobon beluli tartos nyomot a cal0 is hordozna, es kiejtene"}
    xr = np.array([[st_raw[i][q]["x0"] for q in range(3)] for i in range(len(pairs))])
    dr = label_delta(xr, S)
    sec["x0_global_axis_no_drift_correction"] = {"Delta": dr, "p_two_sided": perm_p(xr, S, dr, rng)}
    sec["Delta_per_qubit_x0"] = [float(arr["x0"][S[:, q] == 1, q].mean() - arr["x0"][S[:, q] == 0, q].mean()) for q in range(3)]
    sec["in_job_core_shift_after_reset"] = {"mean": float(np.mean(dk_core)), "p_one_sided": signflip_one_sided(dk_core, rng)}
    se_x0 = float(np.std([label_delta(arr["x0"], np.stack([rng.permutation(S[:, q]) for q in range(3)], 1)) for _ in range(2000)]))
    sec["null_sd_of_Delta"] = se_x0

    valid = len(pairs) >= 20 and a_ok >= 0.95
    h1 = bool(valid and ctrl_ok and p < 0.01 and same)
    if not valid:
        verdict = "INVALID: kevesebb mint 20 par, vagy az A job bitjei nem egyeznek (oszlopsorrend/tengely hiba)."
    elif not ctrl_ok:
        verdict = "INCONCLUSIVE: a pozitiv kontroll nem ment at, a modszer erzekenysege nem igazolt."
    elif h1:
        verdict = "H1 SUPPORTED: a B job 0-felhoje elmozdul az A job titkos bitjevel (masik gepen replikalni kell)."
    else:
        verdict = "H1 NOT SUPPORTED: a 0-felho nem hordoz kimutathato nyomot az elozo jobrol; a tankonyvi joslat all."

    res = {"preregistration": camp["preregistration"], "campaign": camp["tag"], "backend": camp["backend"],
           "pairs": len(pairs), "A_bits_correct_fraction": a_ok,
           "primary": {"metric": "x0 = 0-felho kozeppontja a 0->1 tengely menten (globalis tengely, cal1-hez kotott drift-korrekcio)",
                       "Delta": D, "p_two_sided": p, "Delta_first_half": D1, "Delta_second_half": D2,
                       "same_sign_halves": same},
           "positive_control": {"mean_d": float(np.mean(dk)), "p_one_sided": p_ctrl, "passed": ctrl_ok},
           "secondary": sec, "h1_supported": h1, "verdict": verdict}
    (d / "analysis.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))
    return res


# ----------------------------------------------------------------------------- belepesi pont

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--token-file", default=r"C:\Users\mater\Downloads\apikey (1) (1).json")
    r.add_argument("--instance", default="open-instance")
    r.add_argument("--backend", default="ibm_kingston")
    r.add_argument("--qubits", type=int, nargs=3, default=[48, 49, 50])
    r.add_argument("--pairs", type=int, default=40)
    r.add_argument("--shots", type=int, default=1024)
    r.add_argument("--seed", type=int, default=20261111)
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--dry-memory", type=float, default=0.0, help="Csak dry run: beepitett eltolas a 0->1 tengely menten, ha s=1")
    a = sub.add_parser("analyze")
    a.add_argument("dir")
    args = ap.parse_args()
    if args.cmd == "run":
        cmd_run(args)
    else:
        analyze(args.dir)


if __name__ == "__main__":
    main()
