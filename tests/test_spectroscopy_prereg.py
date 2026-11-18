import copy
import json
import sys
from pathlib import Path
import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from scripts.analyze_spatial_spectroscopy_prereg import analyze_spectroscopy
RAW_JSON = REPO / "measurement_raw" / "spatial_bath_spectroscopy" / "20261107T062103Z" / "raw_results.json"


@pytest.fixture(scope="module")
def kingston_data():
    with open(RAW_JSON, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload["data"]


def test_null_effect_yields_h0(kingston_data):
    """Synthetic null data where s=0 and s=1 share identical distribution must yield H0."""
    null_data = copy.deepcopy(kingston_data)
    # Clone s=0 counts into s=1 for all protocols
    for d in null_data:
        if d["meta"].get("s") == 1:
            match = next(
                x for x in null_data
                if x["meta"]["protocol"] == d["meta"]["protocol"]
                and x["meta"].get("tau_us") == d["meta"].get("tau_us")
                and x["meta"].get("total_us") == d["meta"].get("total_us")
                and x["meta"].get("theta") == d["meta"].get("theta")
                and x["meta"].get("s") == 0
            )
            d["counts"] = copy.deepcopy(match["counts"])

    res = analyze_spectroscopy(null_data, seed=20261118, n_boot=1000, n_boot_t2=200, n_perm=1000)
    assert res["positive_control"]["passed"] is True
    assert res["summary"]["verdict"] == "H0"
    assert res["summary"]["max_abs_z"] < 3.0


def test_injected_phase_shift_yields_h1(kingston_data):
    """Synthetic data with an injected 12 deg phase shift in Protocol 1 must trigger H1 (|z| >= 3)."""
    injected_data = copy.deepcopy(kingston_data)
    # Inject 12 deg phase shift into Protocol 1 s=1: P1(theta) = A - 0.5 * V * cos(theta + phi + delta)
    delta = np.deg2rad(12.0)
    for d in injected_data:
        if d["meta"]["protocol"] == "P1_phase_tomography" and d["meta"]["s"] == 1:
            theta = d["meta"]["theta"]
            shots = 4096
            # Base fringe: A ~ 0.5, V ~ 0.86, phi ~ -2.8 rad
            p1_inj = 0.5 - 0.5 * 0.86 * np.cos(theta - 2.8 + delta)
            k = int(np.round(p1_inj * shots))
            d["counts"] = {"000": shots - k, "010": k}

    res = analyze_spectroscopy(injected_data, seed=20261118, n_boot=2000, n_boot_t2=200, n_perm=2000)
    assert res["positive_control"]["passed"] is True
    assert res["summary"]["verdict"] == "H1 SUPPORTED"
    assert res["summary"]["max_abs_z"] >= 3.0


def test_failed_positive_control_yields_inconclusive(kingston_data):
    """If positive control deviates >= 5 deg from 45 deg or R2 <= 0.95, verdict must be INCONCLUSIVE."""
    corrupted_data = copy.deepcopy(kingston_data)
    for d in corrupted_data:
        if d["meta"]["protocol"] == "P4_positive_control":
            # Flatten counts so R2 collapses
            d["counts"] = {"000": 2048, "010": 2048}

    res = analyze_spectroscopy(corrupted_data, seed=20261118, n_boot=1000, n_boot_t2=200, n_perm=1000)
    assert res["positive_control"]["passed"] is False
    assert res["summary"]["verdict"] == "INCONCLUSIVE"


def test_preregistered_thresholds(kingston_data):
    """Verify decision rules match frozen preregistration: |diff| < 5 deg, R2 > 0.95, |z| >= 3.0."""
    res = analyze_spectroscopy(kingston_data, seed=20261118, n_boot=500, n_boot_t2=100, n_perm=500)
    pos = res["positive_control"]
    assert pos["target_deg"] == 45.0
    # Boundary test: |diff| < 5.0
    assert abs(pos["diff_deg"]) < 5.0
    assert pos["r2"] > 0.95
    assert pos["passed"] is True
    # Verify threshold rule: 3-sigma
    assert res["summary"]["n_prereg_tests"] == 15
    assert res["summary"]["max_abs_z"] < 3.0


def test_kingston_recalculated_numbers(kingston_data):
    """
    On ibm_kingston raw data, verify exact numbers:
    - Positive control: +49.27° ± 0.95° (Target 45°, diff +4.27°), R2 = 0.9999, PASSED
    - Protocol 1 phase: max d_phi = -4.07° ± 1.45° at tau = 50 us (z = -2.81, p = 0.005); other taus |z| <= 2.22
    - Protocol 1 population: max |dp1| <= 0.0076, all p >= 0.16
    - Protocol 1 exploratory constant offset: -1.89° ± 0.50°, chi2 = 3.87-3.92 (df 4)
    - Protocol 2 T2*: dt2 = -2.2 ± 3.5 us (z = -0.61 to -0.63)
    - Protocol 3 CPMG: max dV = +0.040 ± 0.014 at T = 80 us (z = +2.89, p = 0.004); other T |z| <= 1.27
    - Verdict: H0, max |z| = 2.89 < 3.0, Holm min p >= 0.05
    """
    res = analyze_spectroscopy(kingston_data, seed=20261118, n_boot=20000, n_boot_t2=2000, n_perm=200000)

    # Positive control
    pos = res["positive_control"]
    assert pos["passed"] is True
    assert pytest.approx(pos["injected_measured_deg"], abs=0.1) == 49.27
    assert pytest.approx(pos["injected_err_deg"], abs=0.1) == 0.95
    assert pytest.approx(pos["diff_deg"], abs=0.1) == 4.27
    assert pos["r2"] > 0.999

    # Protocol 1 phase
    p1_phase = res["protocol_1_phase"]
    assert pytest.approx(p1_phase["50.0"]["d_phi_deg"], abs=0.1) == -4.07
    assert pytest.approx(p1_phase["50.0"]["sigma_deg"], abs=0.1) == 1.45
    assert pytest.approx(p1_phase["50.0"]["z"], abs=0.1) == -2.81
    assert pytest.approx(p1_phase["50.0"]["p_value"], abs=0.002) == 0.005
    for tau_str, v in p1_phase.items():
        if tau_str != "50.0":
            assert abs(v["z"]) <= 2.25

    # Protocol 1 population
    p1_pop = res["protocol_1_population"]
    for tau_str, v in p1_pop.items():
        assert abs(v["dp1"]) <= 0.0077
        assert v["p_perm"] >= 0.155

    # Protocol 1 exploratory offset
    exp = res["protocol_1_exploratory_constant_offset"]
    assert pytest.approx(exp["offset_deg"], abs=0.1) == -1.89
    assert pytest.approx(exp["sigma_deg"], abs=0.1) == 0.50
    assert pytest.approx(exp["chi2"], abs=0.2) == 3.88

    # Protocol 2 T2*
    p2 = res["protocol_2_t2_star"]
    assert pytest.approx(p2["dt2_us"], abs=0.3) == -2.2
    assert pytest.approx(p2["sigma_us"], abs=0.3) == 3.5
    assert pytest.approx(p2["z"], abs=0.1) == -0.62

    # Protocol 3 CPMG
    cpmg = res["protocol_3_cpmg"]
    assert pytest.approx(cpmg["80.0"]["dv"], abs=0.003) == 0.040
    assert pytest.approx(cpmg["80.0"]["sigma"], abs=0.002) == 0.014
    assert pytest.approx(cpmg["80.0"]["z"], abs=0.1) == 2.89
    assert pytest.approx(cpmg["80.0"]["p_value"], abs=0.002) == 0.004
    for t_str, v in cpmg.items():
        if t_str != "80.0":
            assert abs(v["z"]) <= 1.28

    # Verdict
    sm = res["summary"]
    assert sm["verdict"] == "H0"
    assert pytest.approx(sm["max_abs_z"], abs=0.05) == 2.89
    assert sm["max_abs_z"] < 3.0
    assert sm["min_p_holm"] >= 0.05


def test_protocol2_identical_transpiled_circuits():
    """Protocol 2: 10 X gates on Q48 transpile to identity, making s=0 and s=1 identical (A/A test)."""
    qiskit = pytest.importorskip("qiskit")
    fake_prov = pytest.importorskip("qiskit_ibm_runtime.fake_provider")
    FakeKingston = fake_prov.FakeKingston

    qr = qiskit.QuantumRegister(3, "q")
    cr = qiskit.ClassicalRegister(3, "c")

    # s=0
    qc0 = qiskit.QuantumCircuit(qr, cr)
    qc0.reset(0)
    qc0.sx(1)
    qc0.delay(2.0, 1, unit="us")
    qc0.sx(1)
    qc0.measure(qr, cr)

    # s=1 (10 X gates)
    qc1 = qiskit.QuantumCircuit(qr, cr)
    for _ in range(10):
        qc1.x(0)
    qc1.reset(0)
    qc1.sx(1)
    qc1.delay(2.0, 1, unit="us")
    qc1.sx(1)
    qc1.measure(qr, cr)

    backend = FakeKingston()
    t0 = qiskit.transpile(qc0, backend, initial_layout=[48, 49, 50], optimization_level=1)
    t1 = qiskit.transpile(qc1, backend, initial_layout=[48, 49, 50], optimization_level=1)

    ops0 = [(inst.operation.name, [q._index for q in inst.qubits]) for inst in t0.data]
    ops1 = [(inst.operation.name, [q._index for q in inst.qubits]) for inst in t1.data]
    assert ops0 == ops1, "Circuits must compile to identical operations under optimization_level=1"


def test_alpha_vs_3sigma_ambiguity_and_holm(kingston_data):
    """
    Documents the preregistration contradiction between alpha=0.01 and 3-sigma:
    - Under uncorrected alpha=0.01 (z=2.58), tau=50us phase (p=0.005) and CPMG 80us (p=0.004) would pass.
    - Under 3-sigma (|z| >= 3.0, two-sided p=0.0027), neither passes (|z| <= 2.89).
    - Under Holm-Bonferroni correction over 15 tests, min p_holm = 0.057-0.058 > 0.05.
    """
    res = analyze_spectroscopy(kingston_data, seed=20261118, n_boot=5000, n_boot_t2=500, n_perm=5000)
    p_phase50 = res["protocol_1_phase"]["50.0"]["p_value"]
    p_cpmg80 = res["protocol_3_cpmg"]["80.0"]["p_value"]
    assert p_phase50 < 0.01
    assert p_cpmg80 < 0.01
    assert res["protocol_1_phase"]["50.0"]["z"] < 3.0
    assert res["protocol_3_cpmg"]["80.0"]["z"] < 3.0
    assert res["summary"]["min_p_holm"] > 0.05
    assert res["summary"]["verdict"] == "H0"
