"""
test_spatial_pattern.py — comprehensive tests for the reusable spatial pattern
analysis module (Clark-Evans, collinear triple detection, FPR nulls).

Run:
  python tools/ccat/tests/test_spatial_pattern.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from tools.ccat import spatial_pattern as SP  # noqa: E402


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def test_haversine_known_distance() -> None:
    """1° of latitude ≈ 111.2 km at equator."""
    d = SP.haversine_km(0.0, 0.0, 1.0, 0.0)
    assert 110.0 < d < 112.0


def test_haversine_zero() -> None:
    assert SP.haversine_km(30.0, 35.0, 30.0, 35.0) < 0.001


def test_haversine_symmetric() -> None:
    d1 = SP.haversine_km(10.0, 20.0, 30.0, 40.0)
    d2 = SP.haversine_km(30.0, 40.0, 10.0, 20.0)
    assert abs(d1 - d2) < 0.001


def test_perpendicular_distance_collinear_meridian() -> None:
    """Points on the same meridian → distance ≈ 0."""
    d = SP.perpendicular_distance_km(0.0, 0.0, 1.0, 0.0, -1.0, 0.0)
    assert d < 0.1


def test_perpendicular_distance_far() -> None:
    """Point far from the line → large distance."""
    d = SP.perpendicular_distance_km(0.0, 1.0, 0.0, 0.0, 0.0, 0.0)
    assert d > 100.0


def test_perpendicular_distance_degenerate_pair() -> None:
    """If the two anchor points are identical, fallback to haversine."""
    d = SP.perpendicular_distance_km(1.0, 1.0, 0.0, 0.0, 0.0, 0.0)
    assert d > 100.0


# ---------------------------------------------------------------------------
# Nearest-neighbour (Clark-Evans)
# ---------------------------------------------------------------------------

def test_mean_nn_handles_n_lt_2() -> None:
    assert math.isnan(SP.mean_nn_km([]))
    assert math.isnan(SP.mean_nn_km([(30.0, 35.0)]))


def test_mean_nn_two_points() -> None:
    # Two points at 30.0 and 30.01 → ~1.1 km apart
    d = SP.mean_nn_km([(30.0, 35.0), (30.01, 35.0)])
    assert 0.5 < d < 2.0


def test_clark_evans_clustered_is_negative() -> None:
    """Tight cluster → negative z, R << 1."""
    # 10 pts at one spot + 40 spread wide → strong clustering signal
    coords = [(30.00001, 35.00001)] * 10
    coords += [(30.5, 35.5), (30.8, 35.2), (30.2, 35.8),
               (31.0, 35.0), (30.0, 36.0), (31.5, 34.5)]
    ce = SP.clark_evans_analysis(coords, n_sims=29, seed=0)
    assert ce["clark_evans_R"] < 0.8, f"R={ce['clark_evans_R']} not <0.8"
    assert ce["z_vs_csr"] < -2.0, f"z={ce['z_vs_csr']} not <-2.0"


def test_clark_evans_uniform_near_zero() -> None:
    """Uniform CSR data → R ≈ 1, z near 0."""
    coords, _ = SP.generate_synthetic_csr(n=100, seed=0)
    ce = SP.clark_evans_analysis(coords, n_sims=49, seed=1)
    assert 0.8 < ce["clark_evans_R"] < 1.2
    assert abs(ce["z_vs_csr"]) < 2.5


def test_clark_evans_returns_expected_keys() -> None:
    coords, _ = SP.generate_synthetic_csr(n=50, seed=0)
    ce = SP.clark_evans_analysis(coords, n_sims=10, seed=0)
    for k in ("n", "area_km2_approx", "density_sites_per_km2",
              "obs_mean_nn_km", "clark_evans_R", "z_vs_csr"):
        assert k in ce, f"missing key: {k}"


# ---------------------------------------------------------------------------
# Collinear triple detection
# ---------------------------------------------------------------------------

def test_count_collinear_n_lt_3() -> None:
    result = SP.count_collinear_triples([(30.0, 35.0), (31.0, 36.0)])
    assert result["pairs_evaluated"] == 0


def test_count_collinear_zero_on_spread() -> None:
    """Widely spaced points → no collinear triples at 0.5 km tolerance."""
    coords = [(30.0, 35.0), (31.0, 35.0), (30.0, 36.0)]
    result = SP.count_collinear_triples(coords, tolerance_km=0.5,
                                         n_triple_samples=10, seed=0)
    assert result["collinear_triples_per_pair"] == 0.0


def test_count_collinear_detects_aligned() -> None:
    """Three points on same meridian with ~1.1 km spacing → collinear."""
    coords = [(30.0, 35.0), (30.01, 35.0), (30.02, 35.0)]
    result = SP.count_collinear_triples(coords, tolerance_km=1.0,
                                         n_triple_samples=10, seed=0)
    assert result["collinear_triples_per_pair"] > 0.0


def test_count_collinear_tolerance_zero_no_alignment() -> None:
    """Zero tolerance → no triples for points not exactly collinear."""
    # Three points forming a shallow triangle: third is ~0.1 km off the line
    coords = [(0.0, 0.0), (1.0, 0.0), (0.5, 0.001)]
    result = SP.count_collinear_triples(coords, tolerance_km=0.0,
                                         n_triple_samples=10, seed=0)
    assert result["collinear_triples_per_pair"] == 0.0


# ---------------------------------------------------------------------------
# FPR null models
# ---------------------------------------------------------------------------

def test_ley_fpr_underdetermined_n_lt_3() -> None:
    fpr = SP.ley_line_fpr_analysis(
        [(30.0, 35.0), (31.0, 36.0)], n_sims=5, n_triple_samples=5)
    assert "UNDERDETERMINED" in str(fpr.get("verdict", ""))


def test_ley_fpr_csr_data_not_significant() -> None:
    """On CSR data, the FPR should NOT beat the null."""
    coords, _ = SP.generate_synthetic_csr(n=100, seed=0)
    fpr = SP.ley_line_fpr_analysis(coords, n_sims=49, n_triple_samples=200,
                                    seed=0)
    sc_fpr = fpr["null_scrambled_coord"]["fpr_empirical"]
    csr_fpr = fpr["null_csr"]["fpr_empirical"]
    # Both should be >> 0 (easily > 0.01)
    assert sc_fpr > 0.01 or csr_fpr > 0.01


def test_ley_fpr_returns_expected_keys() -> None:
    coords, _ = SP.generate_synthetic_csr(n=30, seed=0)
    fpr = SP.ley_line_fpr_analysis(coords, n_sims=10, n_triple_samples=50, seed=0)
    for k in ("n_sites", "tolerance_km", "observed",
              "null_scrambled_coord", "null_csr"):
        assert k in fpr, f"missing key: {k}"
    for null_k in ("mean_per_pair", "sd_per_pair", "z", "fpr_empirical"):
        assert null_k in fpr["null_scrambled_coord"]
        assert null_k in fpr["null_csr"]


# ---------------------------------------------------------------------------
# Synthetic CSR generation
# ---------------------------------------------------------------------------

def test_generate_synthetic_csr_n() -> None:
    coords, meta = SP.generate_synthetic_csr(n=50, seed=0)
    assert len(coords) == 50
    assert meta["n_sites"] == 50


def test_generate_synthetic_csr_bounds() -> None:
    coords, meta = SP.generate_synthetic_csr(n=100, seed=42)
    bbox = meta["bbox"]
    for lat, lon in coords:
        assert bbox[1] <= lat <= bbox[3]
        assert bbox[0] <= lon <= bbox[2]


def test_generate_synthetic_csr_seeded() -> None:
    c1, _ = SP.generate_synthetic_csr(n=10, seed=0)
    c2, _ = SP.generate_synthetic_csr(n=10, seed=0)
    assert c1 == c2


# ---------------------------------------------------------------------------
# Demo (__main__) smoke test
# ---------------------------------------------------------------------------

def test_demo_runs() -> None:
    """Running spatial_pattern.py as __main__ should complete."""
    import subprocess
    proc = subprocess.run(
        [sys.executable, str(HERE.parent / "spatial_pattern.py")],
        capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, f"demo failed: {proc.stderr[:500]}"


if __name__ == "__main__":
    fns = [(k, v) for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    ok = bad = 0
    for name, fn in fns:
        try:
            fn()
            print(f"PASS {name}")
            ok += 1
        except AssertionError as e:
            print(f"FAIL {name}: {e}")
            bad += 1
        except Exception as e:
            print(f"ERROR {name}: {type(e).__name__}: {e}")
            bad += 1
    print(f"\n{ok}/{len(fns)} passed, {bad} failed")
    sys.exit(0 if bad == 0 else 1)
