"""Validation for ratios.py -- run: python3 tools/forensics/tests/test_ratios.py"""
import sys
from fractions import Fraction

from tools.forensics import ratios as R


def test_perfect_fourth_exact():
    m = R.nearest_diatonic(4 / 3)
    assert m.note.startswith("perfect 4th"), m.note
    assert m.within_tol and abs(m.cents_error) < 1e-6


def test_octave_folding_to_fourth():
    # 8:3 == a perfect fourth plus one octave; folds back to the fourth.
    m = R.nearest_diatonic(8 / 3)
    assert m.note.startswith("perfect 4th"), m.note


def test_nearest_small_integer():
    im = R.nearest_small_integer_ratio(1.4999)
    assert im.fraction == Fraction(3, 2), im.fraction


def test_triangle_theorem():
    top = R.classify_polygon_area_ratio(4.0)[0]
    assert top[0].startswith("triangle") and top[3], top


def test_square_theorem():
    top = R.classify_polygon_area_ratio(2.0)[0]
    assert top[0].startswith("square") and top[3], top


def test_hexagon_theorem():
    top = R.classify_polygon_area_ratio(4 / 3)[0]
    assert top[0].startswith("hexagon") and top[3], top


def test_golden_ratio_detected():
    top = R.hunt_constants(1.6180339)[0]
    assert top[0].startswith("phi") and top[3], top


def test_non_diatonic_rejected():
    # a tritone-ish 1.41 (~sqrt2) should NOT read as a clean diatonic note
    m = R.nearest_diatonic(1.41, tol_cents=20.0)
    assert not m.within_tol, (m.note, m.cents_error)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}"); ok += 1
        except AssertionError as e:
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{ok}/{len(fns)} passed")
    sys.exit(0 if ok == len(fns) else 1)
