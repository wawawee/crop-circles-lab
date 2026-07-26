"""test_alpha_variation_probe.py — known-answer tests for tools/scripts/alpha_variation_probe.py.

Run:
    python tools/scripts/tests/test_alpha_variation_probe.py

Stance: structure != meaning. No-signal prior. Instrument-systematics null mandatory.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

# Ensure data file exists
DATA_FILE = ROOT / "data" / "astro" / "alpha_variation" / "king_2012_vlt_keck.dat"
assert DATA_FILE.exists(), f"Missing alpha variation data: {DATA_FILE}"

import tools.scripts.alpha_variation_probe as AV  # noqa: E402


# ---------------------------------------------------------------------------
# J2000 parser tests
# ---------------------------------------------------------------------------


def test_parse_j2000_positive_dec() -> None:
    """J000520+052410 → RA=1.3333°, Dec=5.4028°."""
    ra, dec = AV.parse_j2000("J000520+052410")
    assert abs(ra - 1.3333) < 0.01, f"RA={ra}"
    assert abs(dec - 5.4028) < 0.01, f"Dec={dec}"


def test_parse_j2000_negative_dec() -> None:
    """J042315-012033 → RA=65.8125°, Dec=-1.3425°."""
    ra, dec = AV.parse_j2000("J042315-012033")
    assert abs(ra - 65.8125) < 0.01, f"RA={ra}"
    assert abs(dec - (-1.3425)) < 0.01, f"Dec={dec}"


def test_parse_j2000_southern_high_dec() -> None:
    """J235034-432559 → RA≈357.64°, Dec≈-43.43°."""
    ra, dec = AV.parse_j2000("J235034-432559")
    assert abs(ra - 357.6417) < 0.01, f"RA={ra}"
    assert abs(dec - (-43.4331)) < 0.01, f"Dec={dec}"


def test_parse_j2000_northern_high_dec() -> None:
    """J163429+703132 → RA≈248.62°, Dec≈70.53°."""
    ra, dec = AV.parse_j2000("J163429+703132")
    assert abs(ra - 248.6208) < 0.01, f"RA={ra}"
    assert abs(dec - 70.5256) < 0.01, f"Dec={dec}"


# ---------------------------------------------------------------------------
# Angular distance tests
# ---------------------------------------------------------------------------


def test_angular_distance_self() -> None:
    """Angular distance from a point to itself is 0."""
    d = AV.angular_distance(45.0, 30.0, 45.0, 30.0)
    assert d == 0.0, f"d={d}"


def test_angular_distance_90deg() -> None:
    """Pole to equator is ≈90°."""
    d = AV.angular_distance(0.0, 90.0, 0.0, 0.0)
    assert abs(d - 90.0) < 1.0, f"d={d}"


def test_angular_distance_antipodal() -> None:
    """Antipodal points ≈ 180°."""
    d = AV.angular_distance(0.0, 0.0, 180.0, 0.0)
    assert abs(d - 180.0) < 0.5, f"d={d}"


def test_angular_distance_array_consistent() -> None:
    """Array version matches scalar version."""
    ra = np.array([10.0, 20.0, 30.0])
    dec = np.array([-10.0, 0.0, 10.0])
    d_arr = AV.angular_distance_array(ra, dec, 15.0, 5.0)
    for i in range(3):
        d_scalar = AV.angular_distance(ra[i], dec[i], 15.0, 5.0)
        assert abs(d_arr[i] - d_scalar) < 1e-10, f"Mismatch at {i}"


# ---------------------------------------------------------------------------
# Total error tests
# ---------------------------------------------------------------------------


def test_total_error_no_sigma_rand() -> None:
    """VLT (flag=3) with sigma_rand=0.905: sqrt(1² + 0.905²)."""
    e = AV.total_error(1.0, 3)
    expected = math.sqrt(1.0 + 0.905**2)
    assert abs(e - expected) < 1e-6, f"e={e}"


def test_total_error_keck_lc() -> None:
    """Keck LC (flag=1) with sigma_rand=0.0: total = err."""
    e = AV.total_error(2.5, 1)
    assert abs(e - 2.5) < 1e-6, f"e={e}"


def test_total_error_keck_hc() -> None:
    """Keck HC (flag=2) with sigma_rand=1.743: sqrt(1² + 1.743²)."""
    e = AV.total_error(1.0, 2)
    expected = math.sqrt(1.0 + 1.743**2)
    assert abs(e - expected) < 1e-6, f"e={e}"


# ---------------------------------------------------------------------------
# Dipole model tests (inline reconstruction)
# ---------------------------------------------------------------------------


def _dipole_model(theta_deg, amplitude, monopole):
    """Inline dipole model for testing."""
    return amplitude * math.cos(math.radians(theta_deg)) + monopole


def test_dipole_model_at_pole() -> None:
    """At dipole axis (θ=0°): model = A + m."""
    expected = 1.5 + 0.5
    assert abs(_dipole_model(0.0, 1.5, 0.5) - expected) < 1e-10


def test_dipole_model_at_90deg() -> None:
    """At θ=90°: cos(90°)=0, model = m."""
    assert abs(_dipole_model(90.0, 1.5, 0.5) - 0.5) < 1e-10


def test_dipole_model_anti_pole() -> None:
    """At θ=180°: cos(180°)=-1, model = -A + m."""
    expected = -1.5 + 0.5
    assert abs(_dipole_model(180.0, 1.5, 0.5) - expected) < 1e-10


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def test_load_data_returns_correct_count() -> None:
    """Load data returns expected number of absorbers (295)."""
    data = AV.load_data(DATA_FILE)
    assert data["n"] == 295, f"Expected 295, got {data['n']}"


def test_load_data_contains_key_fields() -> None:
    """Loaded data contains all required arrays."""
    data = AV.load_data(DATA_FILE)
    for key in ("ra_deg", "dec_deg", "da_a", "err", "source", "sig_rand_flag", "outlier"):
        assert key in data, f"Missing key: {key}"
    assert len(data["ra_deg"]) == 295


def test_load_data_source_counts() -> None:
    """Expected Keck=141, VLT=154."""
    data = AV.load_data(DATA_FILE)
    n_keck = int(np.sum(data["source"] == "Keck"))
    n_vlt = int(np.sum(data["source"] == "VLT"))
    assert n_keck == 141, f"Expected 141 Keck, got {n_keck}"
    assert n_vlt == 154, f"Expected 154 VLT, got {n_vlt}"


# ---------------------------------------------------------------------------
# Dipole fit at known axis
# ---------------------------------------------------------------------------


def test_dipole_fit_converges() -> None:
    """Dipole fit at a known axis returns valid parameters."""
    data = AV.load_data(DATA_FILE)
    mask = data["outlier"] == 0
    ra = data["ra_deg"][mask]
    dec = data["dec_deg"][mask]
    da_a = data["da_a"][mask]
    err = np.array([AV.total_error(data["err"][mask][i], data["sig_rand_flag"][mask][i])
                    for i in range(len(ra))])
    fit = AV.dipole_fit(ra, dec, da_a, err, 262.5, -58.0)
    assert "error" not in fit, f"Fit failed: {fit}"
    assert fit["n"] > 200
    assert isinstance(fit["amplitude_x1e5"], float)


# ---------------------------------------------------------------------------
# Forbidden phrases
# ---------------------------------------------------------------------------


def test_forbidden_phrases_nonempty() -> None:
    """Forbidden phrases list is non-empty."""
    assert len(AV.FORBIDDEN_PHRASES) > 0


# ---------------------------------------------------------------------------
# z-score computation
# ---------------------------------------------------------------------------


def test_compute_z_identical() -> None:
    """If obs equals null mean, z = 0."""
    z = AV.compute_z(5.0, [5.0, 5.0, 5.0, 5.0])
    assert z == 0.0


def test_compute_z_positive() -> None:
    """Observed > null mean gives positive z."""
    z = AV.compute_z(10.0, [5.0, 5.5, 4.5, 5.0])
    assert z > 0


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------


def test_verdict_underdetermined_low_z() -> None:
    """Low z-scores with inst rejected produce UNDERDETERMINED."""
    zs = {"instrument_systematics": 2.5, "a": 0.5, "b": 1.2}
    verdict, max_z = AV.determine_verdict(zs, None)
    assert "UNDERDETERMINED" in verdict, f"verdict={verdict}"


def test_verdict_instrument_not_rejected() -> None:
    """When instrument-systematics null is not rejected, UNDERDETERMINED."""
    zs = {"instrument_systematics": 1.0, "scramble_coordinates": 4.0}
    verdict, max_z = AV.determine_verdict(zs, {"ra_deg": 75, "dec_deg": 57})
    assert "UNDERDETERMINED" in verdict, f"verdict={verdict}"
    assert "INSTRUMENT_SYSTEMATICS_NULL_NOT_REJECTED" in verdict


# ---------------------------------------------------------------------------]
# percentile_rank
# ---------------------------------------------------------------------------


def test_percentile_rank_median() -> None:
    """Observed at 50th percentile when equal to median."""
    p = AV.percentile_rank(5.0, [1.0, 3.0, 5.0, 7.0, 9.0])
    assert abs(p - 0.4) < 0.1, f"p={p}"  # 2 of 5 are below 5.0


if __name__ == "__main__":
    # Run all test_* functions
    tests = [v for k, v in globals().items()
             if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✅ {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed + failed} tests passed")
    sys.exit(0 if failed == 0 else 1)
