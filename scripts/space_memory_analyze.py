#!/usr/bin/env python3
"""
space_memory_analyze.py: elore rogzitett elemzes (docs/PREREGISTRATION-space_memory.md).

Fo mero: Delta = atlag_q [ atlag P1_B(s=1) - atlag P1_B(s=0) ], a B job fo meresebol.
Teszt: veletlen cimke-permutacio (qubitenkent fuggetlenul), 200 000 permutacio, ketoldali p.
Pozitiv kontroll (tau = 0): jobonkent d_k = atlag_q [P1_c2(u=1) - P1_c2(u=0)], egyoldali elojel-permutacio.
"""

import json
import sys
from pathlib import Path

import numpy as np

N_PERM = 200_000


def delta(p1b, S):
    ds = []
    for q in range(3):
        one, zero = p1b[S[:, q] == 1, q], p1b[S[:, q] == 0, q]
        ds.append(one.mean() - zero.mean())
    return float(np.mean(ds)), [float(x) for x in ds]


def perm_p(p1b, S, obs, rng, chunk=20_000):
    """Cimkek veletlen permutacioja qubitenkent fuggetlenul, vektorizalva."""
    n = S.shape[0]
    cnt = 0
    for start in range(0, N_PERM, chunk):
        m = min(chunk, N_PERM - start)
        tot = np.zeros(m)
        for q in range(3):
            idx = np.argsort(rng.random((m, n)), axis=1)
            L = S[:, q][idx]                      # permutalt cimkek [m, n]
            n1 = L.sum(axis=1)
            s1 = (L * p1b[:, q]).sum(axis=1)
            s0 = ((1 - L) * p1b[:, q]).sum(axis=1)
            tot += s1 / n1 - s0 / (n - n1)
        cnt += int((np.abs(tot / 3) >= abs(obs) - 1e-15).sum())
    return (cnt + 1) / (N_PERM + 1)


def signflip_p_one_sided(d, rng):
    d = np.asarray(d)
    obs = d.mean()
    signs = rng.choice([-1, 1], size=(N_PERM, len(d)))
    return float(((signs * d).mean(axis=1) >= obs - 1e-15).sum() + 1) / (N_PERM + 1)


def main():
    d = Path(sys.argv[1])
    camp = json.loads((d / "campaign.json").read_text(encoding="utf-8"))
    pairs = sorted(d.glob("pair*.json"))
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in pairs]
    S = np.array([r["secret_bits"] for r in recs])
    p1b = np.array([r["B"]["p1_main"] for r in recs])
    p1a = np.array([r["A"]["p1"] for r in recs])
    rng = np.random.default_rng(12345)

    D, Dq = delta(p1b, S)
    p = perm_p(p1b, S, D, rng)
    h = len(recs) // 2
    D1, _ = delta(p1b[:h], S[:h])
    D2, _ = delta(p1b[h:], S[h:])
    same_sign = bool(np.sign(D1) == np.sign(D2) and D1 != 0)

    # A jobok ellenorzese: a titkos bit tenyleg beallt-e
    a_ok = float(np.mean(np.abs(p1a - S) < 0.5))

    ctrl = {}
    for tau in camp["taus_us"]:
        dk = []
        for r in recs:
            c = {x["u"]: x for x in r["controls"] if x["tau_us"] == tau}
            dk.append(float(np.mean(np.array(c[1]["p1_c2"]) - np.array(c[0]["p1_c2"]))))
        ctrl[f"tau_{tau}us"] = {"mean_d": float(np.mean(dk)), "sd_d": float(np.std(dk, ddof=1)),
                                "p_one_sided": signflip_p_one_sided(dk, rng)}
    control_ok = ctrl["tau_0us"]["mean_d"] > 0 and ctrl["tau_0us"]["p_one_sided"] < 0.01

    gaps = [r.get("gap_s") for r in recs]
    sec_gap = None
    if all(g is not None for g in gaps):
        g = np.array(gaps)
        short = g <= np.median(g)
        sec_gap = {"median_gap_s": float(np.median(g)),
                   "delta_short_gaps": delta(p1b[short], S[short])[0],
                   "delta_long_gaps": delta(p1b[~short], S[~short])[0]}

    h1 = bool(control_ok and p < 0.01 and same_sign)
    if not control_ok:
        verdict = "INCONCLUSIVE: a pozitiv kontroll nem mutatta ki a reset-hibat, a modszer erzekenysege nem igazolt."
    elif h1:
        verdict = "H1 SUPPORTED: jobok kozotti informacio a reset utan (replikacio szukseges masik gepen)."
    else:
        verdict = "H1 NOT SUPPORTED: nincs kimutathato jobok kozotti informacio; a tankonyvi joslat all."

    res = {
        "preregistration": camp["preregistration"], "campaign": camp["tag"], "backend": camp["backend"],
        "pairs": len(recs), "A_bits_set_correctly_fraction": a_ok,
        "primary": {"Delta": D, "Delta_per_qubit": Dq, "p_two_sided": p,
                    "Delta_pairs_first_half": D1, "Delta_pairs_second_half": D2, "same_sign_halves": same_sign},
        "positive_control": ctrl, "positive_control_passed": bool(control_ok),
        "secondary_gap": sec_gap, "h1_supported": h1, "verdict": verdict,
    }
    (d / "analysis.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
