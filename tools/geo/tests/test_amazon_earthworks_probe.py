#!/usr/bin/env python3
"""
Offline known-answer + negative-control tests for amazon_earthworks_probe.

Run:  python3 tools/geo/tests/test_amazon_earthworks_probe.py
No network, no scipy. Synthetic coordinates only.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import amazon_earthworks_probe as p  # noqa: E402


def test_known_answer_cluster_fires():
    """A planted tight cluster MUST read STRUCTURE_ONLY / clustered (R<1)."""
    rng = np.random.default_rng(0)
    # a few tight blobs inside a wide arena of sparse background points
    blob_lat = np.concatenate([rng.normal(-10, 0.15, 150),
                               rng.normal(-8.5, 0.15, 150)])
    blob_lon = np.concatenate([rng.normal(-67, 0.15, 150),
                               rng.normal(-64, 0.15, 150)])
    bg_lat = rng.uniform(-12, -6, 60)
    bg_lon = rng.uniform(-70, -60, 60)
    lat = np.concatenate([blob_lat, bg_lat])
    lon = np.concatenate([blob_lon, bg_lon])
    r = p.analyze(lat, lon, n_sims=99, seed=1)
    assert r["verdict"] == "STRUCTURE_ONLY", r
    assert r["clark_evans"]["R"] < 1.0, r
    assert r["clark_evans"]["z"] <= -3, r
    print("PASS known_answer_cluster_fires  R=%.3f z=%.2f" %
          (r["clark_evans"]["R"], r["clark_evans"]["z"]))


def test_negative_control_csr_is_silent():
    """CSR points fed as data must NOT light up -> NO_SIGNAL, R~1, |z| small.

    This is the control that proves the probe does not hallucinate structure.
    It is NOT a verdict on any real dataset.
    """
    rng = np.random.default_rng(7)
    lat = rng.uniform(-12, -6, 800)
    lon = rng.uniform(-70, -60, 800)
    r = p.analyze(lat, lon, n_sims=99, seed=2)
    assert r["verdict"] == "NO_SIGNAL", r
    assert 0.9 < r["clark_evans"]["R"] < 1.1, r
    assert abs(r["clark_evans"]["z"]) < 3, r
    print("PASS negative_control_csr_is_silent  R=%.3f z=%.2f" %
          (r["clark_evans"]["R"], r["clark_evans"]["z"]))


def test_small_n_underdetermined():
    """Too few points -> honest UNDERDETERMINED, never a fabricated verdict."""
    rng = np.random.default_rng(3)
    lat = rng.uniform(-11, -9, 12)
    lon = rng.uniform(-68, -66, 12)
    r = p.analyze(lat, lon, n_sims=20)
    assert r["verdict"] == "UNDERDETERMINED", r
    print("PASS small_n_underdetermined  n=%d" % r["n"])


def test_geometry_area_positive():
    xy, _ = p.project_km(np.array([-10, -9, -11, -10.5]),
                         np.array([-67, -66, -65, -66.5]))
    hull = p.convex_hull(xy)
    assert p.polygon_area(hull) > 0
    print("PASS geometry_area_positive")


if __name__ == "__main__":
    fails = 0
    for fn in [test_geometry_area_positive,
               test_known_answer_cluster_fires,
               test_negative_control_csr_is_silent,
               test_small_n_underdetermined]:
        try:
            fn()
        except AssertionError as e:
            fails += 1
            print("FAIL", fn.__name__, "->", str(e)[:400])
    print("\n%s" % ("ALL TESTS PASS" if fails == 0 else f"{fails} TEST(S) FAILED"))
    sys.exit(1 if fails else 0)
