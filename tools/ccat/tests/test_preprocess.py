"""Known-answer tests for tools/ccat/preprocess.py B3 additions.
Run: python tools/ccat/tests/test_preprocess.py
"""
import json
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import preprocess as P  # noqa: E402


def test_perspective_correct_fills_frame():
    import cv2
    size = 400
    img = np.zeros((size, size), np.uint8)
    quad = np.array([[80, 60], [320, 90], [300, 340], [60, 300]], np.float32)  # TL,TR,BR,BL
    cv2.fillConvexPoly(img, quad.astype(np.int32), 255)
    out = P.perspective_correct(img, quad, out_size=(200, 200))
    assert (out > 127).mean() > 0.9, (out > 127).mean()


def test_crop_stubble_mask_splits_green_vs_tan():
    size = 200
    bgr = np.zeros((size, size, 3), np.uint8)
    bgr[:, :size // 2] = (40, 150, 40)     # BGR green  -> standing crop
    bgr[:, size // 2:] = (150, 190, 210)   # BGR tan    -> laid stubble
    laid = P.crop_stubble_mask(bgr)
    assert laid[:, size // 2:].mean() > 0.8, laid[:, size // 2:].mean()
    assert laid[:, :size // 2].mean() < 0.2, laid[:, :size // 2].mean()


def test_load_corners_json():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "c.json")
    with open(p, "w") as f:
        f.write(json.dumps({"corners": [[0, 0], [10, 0], [10, 10], [0, 10]]}))
    q = P.load_corners_json(p)
    assert q.shape == (4, 2)


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
