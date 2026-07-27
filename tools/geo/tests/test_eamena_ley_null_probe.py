#!/usr/bin/env python3
"""
Offline tests for eamena_ley_null_probe.

Run:  python3 tools/geo/tests/test_eamena_ley_null_probe.py
No network, no scipy. Synthetic coordinates only.
"""
import json
import os
import sys
import tempfile

import numpy as np

from tools.geo import eamena_ley_null_probe as p


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------

def test_haversine_known_distance():
    d = p._haversine_dist(0, 0, 0, 1)
    assert abs(d - 111.319) < 1.0, f"d={d}"
    d2 = p._haversine_dist(51.5, 0, 51.5, 1)
    assert abs(d2 - 69.1) < 1.0, f"d2={d2}"


def test_bearing_known_values():
    b = p._bearing(0, 0, 0, 1)
    assert abs(b - 90) < 0.1, f"bearing due east={b}"
    b2 = p._bearing(0, 0, 1, 0)
    assert abs(b2 - 0) < 0.1 or abs(b2 - 360) < 0.1, f"bearing due north={b2}"
    b3 = p._bearing(0, 0, 0, -1)
    assert abs(b3 - 270) < 0.1, f"bearing due west={b3}"


def test_angular_deviation_collinear():
    d = p._angular_deviation(0, 0, 0, 1, 0, 2)
    assert d < 0.1, f"collinear along equator deviation={d}"


def test_angular_deviation_perpendicular():
    d = p._angular_deviation(0, 0, 0, 1, 1, 0)
    assert d > 80 and d < 100, f"perpendicular deviation={d}"


# ---------------------------------------------------------------------------
# collinear_triples
# ---------------------------------------------------------------------------

def test_collinear_triples_finds_known():
    lats = np.array([0.0, 0.0, 0.0, 0.0, 1.0])
    lons = np.array([0.0, 1.0, 2.0, 3.0, 0.0])
    triples = p.collinear_triples(lats, lons, tol_deg=1.0)
    assert len(triples) >= 3, f"expected >=3 collinear triples, got {len(triples)}"


def test_collinear_triples_empty_for_scattered():
    rng = np.random.default_rng(0)
    lats = rng.uniform(-10, 10, 10)
    lons = rng.uniform(-10, 10, 10)
    triples = p.collinear_triples(lats, lons, tol_deg=0.01)
    assert len(triples) == 0, f"expected 0, got {len(triples)}"


def test_collinear_triples_fewer_at_stricter_tol():
    lats = np.array([0.0, 0.0, 0.0, 0.5, 0.5])
    lons = np.array([0.0, 1.0, 2.0, 0.0, 2.0])
    loose = len(p.collinear_triples(lats, lons, tol_deg=5.0))
    tight = len(p.collinear_triples(lats, lons, tol_deg=0.1))
    assert loose >= tight, f"loose={loose} < tight={tight}"


# ---------------------------------------------------------------------------
# max_collinear_run
# ---------------------------------------------------------------------------

def test_max_collinear_run_on_line():
    lats = np.array([0.0, 0.0, 0.0, 0.0])
    lons = np.array([0.0, 1.0, 2.0, 3.0])
    size, comp = p.max_collinear_run(lats, lons, tol_deg=1.0)
    assert size == 4, f"expected run of 4, got {size}"


def test_max_collinear_run_no_chain():
    rng = np.random.default_rng(1)
    lats = rng.uniform(-10, 10, 6)
    lons = rng.uniform(-10, 10, 6)
    size, comp = p.max_collinear_run(lats, lons, tol_deg=0.01)
    assert size == 0, f"expected 0, got {size}"


# ---------------------------------------------------------------------------
# mean_alignment_error
# ---------------------------------------------------------------------------

def test_mean_alignment_error_nan_for_n2():
    lats = np.array([0.0, 1.0])
    lons = np.array([0.0, 1.0])
    assert np.isnan(p.mean_alignment_error(lats, lons))


def test_mean_alignment_error_small_for_collinear():
    lats = np.array([0.0, 0.0, 0.0, 0.0])
    lons = np.array([0.0, 0.5, 1.0, 1.5])
    err = p.mean_alignment_error(lats, lons)
    assert err < 0.1, f"expected near zero, got {err}"


# ---------------------------------------------------------------------------
# load_geojson
# ---------------------------------------------------------------------------

def test_load_geojson_real_subset():
    path = os.path.join(os.path.dirname(__file__),
                        "..", "..", "..", "data", "geo", "eamena", "wadi_naqqat.geojson")
    lats, lons, props = p.load_geojson(path)
    assert len(lats) == 14, f"expected 14, got {len(lats)}"
    assert len(lons) == 14
    assert len(props) == 14


def test_load_geojson_empty_feature_collection():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False) as f:
        json.dump({"type": "FeatureCollection", "features": []}, f)
        path = f.name
    try:
        lats, lons, props = p.load_geojson(path)
        assert len(lats) == 0
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# null generators
# ---------------------------------------------------------------------------

def test_sample_csr_bbox():
    rng = np.random.default_rng(2)
    lats, lons = p.sample_csr_bbox(100, (-1, -1, 1, 1), rng)
    assert len(lats) == 100
    assert lats.min() >= -1 and lats.max() <= 1
    assert lons.min() >= -1 and lons.max() <= 1


def test_sample_scramble_preserves_coords():
    orig_lats = np.array([1, 2, 3, 4, 5])
    orig_lons = np.array([10, 20, 30, 40, 50])
    rng = np.random.default_rng(3)
    slats, slons = p.sample_scramble(orig_lats, orig_lons, rng)
    assert sorted(slats) == sorted(orig_lats)
    assert sorted(slons) == sorted(orig_lons)


# ---------------------------------------------------------------------------
# calibration
# ---------------------------------------------------------------------------

def test_calibration_returns_allowed_verdict():
    rng = np.random.default_rng(4)
    lats = rng.uniform(-1, 1, 20)
    lons = rng.uniform(-1, 1, 20)
    res = p.run_calibration(lats, lons, n_sims=49, seed=5)
    assert res["verdict"] in {"NO_SIGNAL", "FPR_CALIBRATED", "UNDERDETERMINED"}, res


def test_calibration_underdetermined_for_n2():
    lats = np.array([0.0, 1.0])
    lons = np.array([0.0, 1.0])
    res = p.run_calibration(lats, lons, n_sims=10)
    assert res["verdict"] == "UNDERDETERMINED"


def test_calibration_no_signal_for_csr_data():
    rng = np.random.default_rng(6)
    lats = rng.uniform(-5, 5, 40)
    lons = rng.uniform(-5, 5, 40)
    res = p.run_calibration(lats, lons, n_sims=99, seed=7)
    assert res["verdict"] == "NO_SIGNAL", res


def test_calibration_outputs_contain_expected_keys():
    rng = np.random.default_rng(8)
    lats = rng.uniform(-1, 1, 15)
    lons = rng.uniform(-1, 1, 15)
    res = p.run_calibration(lats, lons, n_sims=19, seed=9)
    for key in ("verdict", "reason", "dataset", "per_tolerance",
                "parameters", "real_stats", "caveats"):
        assert key in res, f"missing key: {key}"


# ---------------------------------------------------------------------------
# main CLI
# ---------------------------------------------------------------------------

def test_main_cli_writes_expected_files():
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = os.path.join(tmp, "out")
        old_argv = sys.argv
        try:
            sys.argv = [
                "eamena_ley_null_probe.py",
                "--out-dir", out_dir,
                "--n-sims", "49",
            ]
            p.main()
        finally:
            sys.argv = old_argv
        run_path = os.path.join(out_dir, "run.json")
        notes_path = os.path.join(out_dir, "NOTES.md")
        assert os.path.exists(run_path), f"missing {run_path}"
        assert os.path.exists(notes_path), f"missing {notes_path}"
        with open(run_path) as fh:
            loaded = json.load(fh)
        assert "verdict" in loaded
        assert "per_tolerance" in loaded
        key = "per_tolerance"
        pt = loaded.get(key, {})
        assert "tol_1.0" in pt


# ---------------------------------------------------------------------------
# run all
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    fails = 0
    tests = [
        test_haversine_known_distance,
        test_bearing_known_values,
        test_angular_deviation_collinear,
        test_angular_deviation_perpendicular,
        test_collinear_triples_finds_known,
        test_collinear_triples_empty_for_scattered,
        test_collinear_triples_fewer_at_stricter_tol,
        test_max_collinear_run_on_line,
        test_max_collinear_run_no_chain,
        test_mean_alignment_error_nan_for_n2,
        test_mean_alignment_error_small_for_collinear,
        test_load_geojson_real_subset,
        test_load_geojson_empty_feature_collection,
        test_sample_csr_bbox,
        test_sample_scramble_preserves_coords,
        test_calibration_returns_allowed_verdict,
        test_calibration_underdetermined_for_n2,
        test_calibration_no_signal_for_csr_data,
        test_calibration_outputs_contain_expected_keys,
        test_main_cli_writes_expected_files,
    ]
    print(f"Running {len(tests)} tests...\n")
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            fails += 1
            print(f"  FAIL  {fn.__name__}: {str(e)[:200]}")
        except Exception as e:
            fails += 1
            print(f"  FAIL  {fn.__name__}: {type(e).__name__}: {str(e)[:200]}")
    print(f"\n{'ALL TESTS PASS' if fails == 0 else f'{fails} TEST(S) FAILED'}")
    sys.exit(1 if fails else 0)
