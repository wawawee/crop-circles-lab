"""Validation for fractal.py -- run: python3 tools/forensics/tests/test_fractal.py"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fractal as F  # noqa: E402


def test_solid_square_dim_near_2():
    b = np.zeros((512, 512), bool); b[64:448, 64:448] = True
    r = F.fractal_dimension(b)
    assert 1.90 <= r.dimension <= 2.06, r.dimension
    assert r.r_squared > 0.99, r.r_squared


def test_single_line_dim_near_1():
    b = np.zeros((512, 512), bool); b[256, 32:480] = True
    r = F.fractal_dimension(b)
    assert 0.90 <= r.dimension <= 1.10, r.dimension


def test_koch_curve_dimension():
    b = F.rasterize_polyline(F.koch_points(6), size=2048)
    r = F.fractal_dimension(b)
    assert abs(r.dimension - 1.2619) < 0.06, (r.dimension, r.r_squared, r.fit_slice)


def test_sierpinski_carpet_dimension():
    b = F.sierpinski_carpet(5)
    r = F.fractal_dimension(b)
    assert abs(r.dimension - 1.8928) < 0.10, (r.dimension, r.r_squared, r.fit_slice)


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
