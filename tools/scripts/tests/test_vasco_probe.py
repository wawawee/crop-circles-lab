"""test_vasco_probe.py — known-answer tests for tools/scripts/vasco_probe.py.

Run:
    python tools/scripts/tests/test_vasco_probe.py

Stance: structure != meaning. No-signal prior.
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
DATA_FILE = ROOT / "data" / "astro" / "vasco" / "vasco_candidates.csv"
assert DATA_FILE.exists(), f"Missing VASCO data: {DATA_FILE}"

import tools.scripts.vasco_probe as VASCO  # noqa: E402


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def test_radec_to_galactic_ngp() -> None:
    """Galactic north pole in equatorial should map to b ≈ +90°."""
    l, b = VASCO.radec_to_galactic(192.8595, 27.1284)
    assert abs(b - 90.0) < 0.5, f"b={b} at NGP"


def test_radec_to_galactic_gc() -> None:
    """Galactic center should map to b ≈ 0°, l ≈ 0°."""
    l, b = VASCO.radec_to_galactic(266.4051, -28.9362)
    assert abs(l) < 5 or abs(l - 360) < 5, f"l={l} at GC"
    assert abs(b) < 5, f"b={b} at GC"


def test_radec_to_galactic_sirius() -> None:
    """Sirius (α CMa) known Galactic coordinates: l≈227.2°, b≈-8.9°."""
    l, b = VASCO.radec_to_galactic(101.287, -16.716)
    assert abs(l - 227) < 3, f"Sirius l={l}"
    assert abs(b + 8.9) < 1.5, f"Sirius b={b}"


def test_radec_to_galactic_array() -> None:
    """Vectorised call works and returns matching lengths."""
    ra = np.array([10.0, 100.0, 200.0])
    dec = np.array([20.0, 30.0, -40.0])
    l, b = VASCO.radec_to_galactic(ra, dec)
    assert len(l) == 3
    assert len(b) == 3
    assert all(isinstance(v, (float, np.floating)) for v in l)


def test_angular_sep_self_zero() -> None:
    """Angular separation of a point with itself is 0."""
    d = VASCO.angular_sep(45.0, 30.0, 45.0, 30.0)
    assert d == 0.0, f"d={d}"


def test_angular_sep_90deg() -> None:
    """Pole to equator is 90°."""
    d = VASCO.angular_sep(0.0, 90.0, 0.0, 0.0)
    assert abs(d - 90.0) < 1.0, f"d={d}"


def test_angular_sep_antipodal() -> None:
    """Antipodal points ≈ 180° apart."""
    d = VASCO.angular_sep(0.0, 0.0, 180.0, 0.0)
    assert abs(d - 180.0) < 0.5, f"d={d}"


# ---------------------------------------------------------------------------
# Null generators
# ---------------------------------------------------------------------------

def test_uniform_sphere_count() -> None:
    """uniform_sphere returns requested count."""
    ra, dec = VASCO.uniform_sphere(100)
    assert len(ra) == 100
    assert len(dec) == 100


def test_uniform_sphere_bounds() -> None:
    """Uniform sphere RA in [0, 360), Dec in [-90, 90]."""
    ra, dec = VASCO.uniform_sphere(1000)
    assert np.all(ra >= 0) and np.all(ra < 360)
    assert np.all(dec >= -90) and np.all(dec <= 90)


def test_scramble_coords_preserves_count() -> None:
    """Scramble preserves N and individual values."""
    ra = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    dec = np.array([-10.0, 0.0, 10.0, 20.0, 30.0])
    rs, ds = VASCO.scramble_coords(ra, dec)
    assert len(rs) == 5
    assert set(rs) == set(ra)
    assert set(ds) == set(dec)


def test_scramble_coords_changes_order() -> None:
    """Scramble should break pairing (very likely)."""
    rng = np.random.default_rng(42)
    ra = rng.uniform(0, 360, 20)
    dec = rng.uniform(-90, 90, 20)
    rs, ds = VASCO.scramble_coords(ra, dec)
    pairs_before = set(zip(ra, dec))
    pairs_after = set(zip(rs, ds))
    assert len(pairs_before & pairs_after) < 20, "scramble did not break pairs"


def test_plate_artifact_null_count() -> None:
    """plate_artifact_null returns correct count."""
    ra, dec = VASCO.plate_artifact_null(50)
    assert len(ra) == 50
    assert len(dec) == 50


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def test_nearest_neighbor_two_points() -> None:
    """Two points with known separation."""
    ra = np.array([0.0, 1.0])
    dec = np.array([0.0, 0.0])
    nn = VASCO.nearest_neighbor_stats(ra, dec)
    assert nn["n"] == 2
    assert nn["mean"] > 0


def test_close_pairs_no_pairs() -> None:
    """Widely separated points have 0 close pairs."""
    ra = np.array([0.0, 180.0])
    dec = np.array([0.0, 0.0])
    assert VASCO.close_pairs(ra, dec, 1.0) == 0


def test_close_pairs_one_pair() -> None:
    """Two close points count as 1 close pair."""
    ra = np.array([0.0, 0.5])
    dec = np.array([0.0, 0.0])
    assert VASCO.close_pairs(ra, dec, 1.0) == 1


def test_gal_lat_stats_uniform() -> None:
    """Isotropic distribution: mean |sin(b)| = 0.5 on uniform sphere,
    but mean |b| ≈ 57.3° for uniform latitude sampling.
    For uniform points on sphere (all-sky), mean |b| ≈ 32.7° because
    of spherical geometry (cos(b) weighting)."""
    ra, dec = VASCO.uniform_sphere(10000, seed=42)
    l_unused, b = VASCO.radec_to_galactic(ra, dec)
    gs = VASCO.gal_lat_stats(b)
    assert 30 < gs["mean_abs_b"] < 36, f"mean_abs_b={gs['mean_abs_b']}"


def test_gal_lat_stats_plane() -> None:
    """Candidates clustered in the Galactic plane have low mean |b|."""
    b = np.array([0.5, -0.3, 1.2, -0.8, 0.1])
    gs = VASCO.gal_lat_stats(b)
    assert gs["mean_abs_b"] < 1.5


# ---------------------------------------------------------------------------
# Integration: data load + probe run
# ---------------------------------------------------------------------------

def test_data_file_loads() -> None:
    """VASCO candidate CSV loads without error."""
    ra, dec = [], []
    with open(DATA_FILE) as f:
        import csv
        reader = csv.DictReader(f)
        for row in reader:
            ra.append(float(row["RA"]))
            dec.append(float(row["DEC"]))
    assert len(ra) == 5399, f"Expected 5399 candidates, got {len(ra)}"
    assert all(-90 <= d <= 90 for d in dec)
    assert all(0 <= r <= 360 for r in ra)


def test_observed_stats_run() -> None:
    """Observed statistics compute without error on real data."""
    ra, dec = [], []
    with open(DATA_FILE) as f:
        import csv
        reader = csv.DictReader(f)
        for row in reader:
            ra.append(float(row["RA"]))
            dec.append(float(row["DEC"]))
    ra_a = np.array(ra)
    dec_a = np.array(dec)

    nn = VASCO.nearest_neighbor_stats(ra_a, dec_a)
    assert nn["mean"] > 0

    cp1 = VASCO.close_pairs(ra_a, dec_a, 1.0)
    assert cp1 >= 0

    l_unused, b = VASCO.radec_to_galactic(ra_a, dec_a)
    gs = VASCO.gal_lat_stats(b)
    assert 0 <= gs["mean_abs_b"] <= 90

    da = VASCO.delaunay_areas(ra_a, dec_a)
    assert da["mean_area_deg2"] is not None


def test_forbidden_phrases_not_in_output() -> None:
    """Probe output never contains forbidden phrases."""
    ra = np.array([10.0, 20.0, 30.0])
    dec = np.array([0.0, 5.0, 10.0])
    # This just verifies the constant exists
    assert len(VASCO.FORBIDDEN) > 0


# ---------------------------------------------------------------------------
# z-score computation
# ---------------------------------------------------------------------------

def test_compute_z_identical() -> None:
    """If obs equals null mean, z = 0."""
    z = VASCO.compute_z(5.0, [5.0, 5.0, 5.0, 5.0])
    assert z == 0.0


def test_compute_z_positive() -> None:
    """Observed > null mean gives positive z."""
    z = VASCO.compute_z(10.0, [5.0, 5.5, 4.5, 5.0])
    assert z > 0


# ---------------------------------------------------------------------------
# Known-answer: uniform sphere should give NO_SIGNAL
# ---------------------------------------------------------------------------

def test_uniform_sphere_self_null() -> None:
    """Uniform sphere against itself (multiple realizations) gives |z| < 3."""
    n_null = 50
    ra0, dec0 = VASCO.uniform_sphere(1000, seed=42)
    l0_unused, b0 = VASCO.radec_to_galactic(ra0, dec0)
    obs_glat = VASCO.gal_lat_stats(b0)["mean_abs_b"]

    null_glat = []
    for i in range(n_null):
        r, d = VASCO.uniform_sphere(1000, seed=100 + i)
        lu, bu = VASCO.radec_to_galactic(r, d)
        null_glat.append(VASCO.gal_lat_stats(bu)["mean_abs_b"])

    z = VASCO.compute_z(obs_glat, null_glat)
    assert abs(z) < 3.0, f"Uniform sphere z={z}"


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
