"""Known-answer tests for tools/ccat/grid_analyze.py.
Run: python tools/ccat/tests/test_grid_analyze.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import grid_analyze as G  # noqa: E402


def _rng():
    return np.random.default_rng(0)


def test_constant_grid_zero_entropy():
    g = np.ones((40, 40), int)
    assert G.shannon_entropy(g) == 0.0


def test_random_grid_high_entropy_low_structure():
    g = _rng().integers(0, 2, (73, 23))
    assert G.shannon_entropy(g) > 0.9
    assert abs(G.structuredness_z(g, n=150)) < 3.0
    assert G.dominant_period(g)["corr"] < 0.5


def test_vertical_stripes_periodic():
    # columns repeat every 4 -> strong column periodicity + spectral peak
    stripes = np.tile(np.array([1, 0, 0, 0]), (60, 30))[:60, :100]
    dp = G.dominant_period(stripes)
    assert dp["axis"] == "col" and dp["period"] == 4 and dp["corr"] > 0.8
    assert G.fft_peakiness(stripes) > G.fft_peakiness(_rng().integers(0, 2, stripes.shape))


def test_mirror_symmetry_detected():
    half = _rng().integers(0, 2, (40, 20))
    g = np.hstack([half, half[:, ::-1]])   # horizontally mirror-symmetric
    assert G.symmetry(g)["horizontal"] > 0.99


def test_block_structure_is_nonrandom():
    # 4x4 solid blocks -> neighbours agree far more than chance
    base = _rng().integers(0, 2, (10, 10))
    g = np.kron(base, np.ones((4, 4), int))
    assert G.structuredness_z(g, n=150) > 5.0
    assert G.analyze(g, n_shuffles=150).verdict.startswith("structured")


def test_random_verdict_is_random_like():
    g = _rng().integers(0, 2, (73, 23))
    assert G.analyze(g, n_shuffles=150).verdict.startswith("random-like")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}"); ok += 1
        except AssertionError as e:
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{ok}/{len(fns)} passed")
    sys.exit(0 if ok == len(fns) else 1)
