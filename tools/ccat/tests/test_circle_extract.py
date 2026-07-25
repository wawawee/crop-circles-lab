"""Known-answer tests for tools/ccat/circle_extract.py (B4).
Run: python tools/ccat/tests/test_circle_extract.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import circle_extract as C  # noqa: E402


def test_synthetic_log_spiral_count():
    mask, placed = C.synthetic_log_spiral(target=150)
    assert placed >= 120, f"generator only placed {placed}"
    circ = C.extract_circles(mask)
    err = abs(len(circ) - placed) / placed
    assert err <= 0.10, (len(circ), placed, err)


def test_finds_three_clean_circles():
    import cv2
    img = np.zeros((400, 400), np.uint8)
    for (x, y, r) in [(100, 100, 30), (300, 120, 25), (200, 300, 40)]:
        cv2.circle(img, (x, y), r, 255, -1)
    circ = C.extract_circles(img > 0)
    assert len(circ) == 3, len(circ)
    assert sorted(round(c["r"]) for c in circ) == [25, 30, 40]


def test_rejects_random_texture():
    # random salt texture must NOT explode into hundreds of "circles"
    rng = np.random.default_rng(0)
    noise = (rng.random((600, 600)) < 0.15)
    circ = C.extract_circles(noise, min_area=25, min_circularity=0.7, min_radius=3)
    assert len(circ) < 40, len(circ)


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
