#!/usr/bin/env python3
"""
select_chain.py — Algorithmic 3-qubit linear chain selection on Heron QPU.

Selection rule (fixed in PREREGISTRATION-qpu_vs_rng_replication.md):
- Candidates are all connected 3-qubit linear chains a-b-c on the backend's coupling map.
- Excluded if any qubit has readout error > 0.03 or if any link has no reported gate error.
- Selected: chain with lowest sum of readout errors (tie-breaker: lowest first qubit index).
- Saves selection and calibration snapshot to layout_selection.json.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

def main():
    parser = argparse.ArgumentParser(description="Algorithmic chain selection on IBM Quantum backend")
    parser.add_argument("--token-file", default=r"C:\Users\mater\Downloads\apikey (2).json")
    parser.add_argument("--backend", default="ibm_kingston")
    parser.add_argument("--output", default=str(REPO / "measurement_raw" / "qpu_vs_rng_replication" / "layout_selection.json"))
    args = parser.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(args.token_file, encoding="utf-8") as f:
        key_data = json.load(f)
    token = key_data.get("apikey") or key_data.get("token")

    from qiskit_ibm_runtime import QiskitRuntimeService
    service = QiskitRuntimeService(channel="ibm_quantum_platform", token=token, instance="open-instance")
    backend = service.backend(args.backend)
    props = backend.properties(refresh=True)

    coupling_map = backend.coupling_map
    # Build undirected adjacency
    adj = {}
    for edge in coupling_map:
        u, v = edge[0], edge[1]
        adj.setdefault(u, set()).add(v)
        adj.setdefault(v, set()).add(u)

    # Find all linear 3-qubit chains a-b-c
    candidates = []
    seen = set()
    for b in adj:
        neighbors = sorted(list(adj[b]))
        for i in range(len(neighbors)):
            for j in range(i + 1, len(neighbors)):
                a, c = neighbors[i], neighbors[j]
                chain_tuple = (min(a, c), b, max(a, c))
                if chain_tuple not in seen:
                    seen.add(chain_tuple)
                    candidates.append((min(a, c), b, max(a, c)))

    valid_chains = []
    for a, b, c in candidates:
        # Check readout error
        ro_a = props.readout_error(a)
        ro_b = props.readout_error(b)
        ro_c = props.readout_error(c)

        if ro_a is None or ro_b is None or ro_c is None:
            continue
        if ro_a > 0.03 or ro_b > 0.03 or ro_c > 0.03:
            continue

        # Check gate errors
        g_ab = props.gate_error("cz", [a, b]) if "cz" in [g.gate for g in props.gates] else None
        if g_ab is None:
            g_ab = props.gate_error("ecr", [a, b])
        if g_ab is None:
            g_ab = props.gate_error("ecr", [b, a])

        g_bc = props.gate_error("cz", [b, c]) if "cz" in [g.gate for g in props.gates] else None
        if g_bc is None:
            g_bc = props.gate_error("ecr", [b, c])
        if g_bc is None:
            g_bc = props.gate_error("ecr", [c, b])

        # If gate errors not found with gate name, try general lookup
        if g_ab is None:
            for g in props.gates:
                if set(g.qubits) == {a, b}:
                    for param in g.parameters:
                        if param.name == "gate_error":
                            g_ab = param.value
                            break
                    if g_ab is not None:
                        break

        if g_bc is None:
            for g in props.gates:
                if set(g.qubits) == {b, c}:
                    for param in g.parameters:
                        if param.name == "gate_error":
                            g_bc = param.value
                            break
                    if g_bc is not None:
                        break

        if g_ab is None or g_bc is None:
            continue

        score = ro_a + ro_b + ro_c
        valid_chains.append({
            "chain": [a, b, c],
            "score_sum_readout_error": score,
            "readout_errors": {"q" + str(a): ro_a, "q" + str(b): ro_b, "q" + str(c): ro_c},
            "gate_errors_2q": {f"({a},{b})": g_ab, f"({b},{c})": g_bc}
        })

    if not valid_chains:
        print("Error: No valid 3-qubit chain found meeting readout error <= 0.03.")
        sys.exit(1)

    # Sort by score ascending, tie-breaker: lowest first qubit index
    valid_chains.sort(key=lambda x: (x["score_sum_readout_error"], x["chain"][0], x["chain"][1]))
    best = valid_chains[0]

    record = {
        "backend": backend.name,
        "calibration_timestamp": str(props.last_update_date),
        "selected_chain": best["chain"],
        "sum_readout_error": best["score_sum_readout_error"],
        "readout_errors": best["readout_errors"],
        "gate_errors_2q": best["gate_errors_2q"],
        "all_valid_candidates_count": len(valid_chains)
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    print("=" * 78)
    print("ALGORITHMIC 3-QUBIT CHAIN SELECTION")
    print(f"  Backend        : {backend.name}")
    print(f"  Calibration    : {record['calibration_timestamp']}")
    print(f"  Valid chains   : {len(valid_chains)} candidates meeting RO <= 0.03")
    print(f"  SELECTED CHAIN : {best['chain']}")
    print(f"  Sum RO error   : {best['score_sum_readout_error']:.5f}")
    print(f"  Readout errors : {best['readout_errors']}")
    print(f"  2Q gate errors : {best['gate_errors_2q']}")
    print(f"  Selection file : {out_path}")
    print("=" * 78)
    print(f"Next command to run replication:")
    qubits_arg = " ".join(str(q) for q in best["chain"])
    print(f"python scripts/qpu_vs_rng.py --backend {backend.name} --seed 20261109 --qubits {qubits_arg}")

if __name__ == "__main__":
    main()
