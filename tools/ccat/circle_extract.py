"""B4 — mask-first circle extraction that survives wheat texture.

Running Hough on a raw grayscale aerial explodes into thousands of spurious
circles (the Kimi demo hit 2064). Instead we go mask-first:

    binarize -> (light) morphological cleanup -> connected contours ->
    keep blobs that are round enough + big enough -> cv2.minEnclosingCircle.

This counts *distinct flattened blobs*, which is what a circle formation actually
is. Validated on a synthetic logarithmic spiral of non-overlapping shrinking
circles (the shape the 1996 "Julia Set" really is): recovers N within +/-10%.

Feeds radii into forensics.encoding.is_true_julia_set / info_theory.

CLI:  python tools/ccat/circle_extract.py data/images/julia_set_1996_tt_oh.jpg --out outputs/julia_circles.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from preprocess import binarize, morphological_cleanup  # noqa: E402
except Exception:  # keep import cheap if preprocess/cv2 unavailable at import time
    binarize = None
    morphological_cleanup = None


def extract_circles(mask, min_area: float = 12.0, min_circularity: float = 0.60,
                    min_radius: float = 2.0):
    """Extract circle-like blobs from a boolean mask (True = flattened crop).

    Returns a list of {x, y, r, area, circularity} sorted largest-first.
    circularity = 4*pi*area / perimeter^2  (1.0 = perfect circle).
    """
    m = (np.asarray(mask, dtype=np.uint8) * 255)
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cnts:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        per = cv2.arcLength(c, True)
        if per <= 0:
            continue
        circ = 4.0 * math.pi * area / (per * per)
        (x, y), r = cv2.minEnclosingCircle(c)
        if r < min_radius or circ < min_circularity:
            continue
        out.append({"x": float(x), "y": float(y), "r": float(r),
                    "area": float(area), "circularity": round(float(circ), 3)})
    out.sort(key=lambda d: d["r"], reverse=True)
    return out


def extract_from_image(path, method: str = "otsu", open_px: int = 1, close_px: int = 1,
                       **kw):
    if binarize is None:
        raise RuntimeError("preprocess/cv2 unavailable")
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise SystemExit(f"cannot read {path}")
    mask = morphological_cleanup(binarize(bgr, method=method), open_px, close_px)
    circles = extract_circles(mask, **kw)
    return circles, mask


def synthetic_log_spiral(target: int = 150, size: int = 2400, a: float = 6.0,
                         b: float = 0.11, r_start: float = 28.0, r_shrink: float = 0.988,
                         gap: float = 3.0):
    """Draw up to `target` NON-overlapping shrinking circles along a log spiral.

    Returns (bool_mask, placed_count). placed_count is the ground truth to test
    the extractor against (some circles may not fit -> placed < target).
    """
    img = np.zeros((size, size), np.uint8)
    cx, cy = size / 2.0, size / 2.0
    placed = []
    theta = 0.6
    r = r_start
    guard = 0
    while len(placed) < target and guard < 400000:
        guard += 1
        rc = a * math.exp(b * theta)
        x = cx + rc * math.cos(theta)
        y = cy + rc * math.sin(theta)
        rr = max(2.0, r)
        theta += 0.05
        if x - rr < 1 or y - rr < 1 or x + rr >= size - 1 or y + rr >= size - 1:
            if rc > size:
                break
            continue
        if all(math.hypot(x - px, y - py) >= (rr + pr + gap) for px, py, pr in placed):
            cv2.circle(img, (int(round(x)), int(round(y))), int(round(rr)), 255, -1)
            placed.append((x, y, rr))
            r *= r_shrink
    return img > 0, len(placed)


def main() -> None:
    ap = argparse.ArgumentParser(description="Mask-first circle extraction")
    ap.add_argument("image", nargs="?", help="image path; omit to run the synthetic self-check")
    ap.add_argument("--method", choices=["otsu", "adaptive"], default="otsu")
    ap.add_argument("--min-circularity", type=float, default=0.60)
    ap.add_argument("--min-radius", type=float, default=2.0)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.image is None:
        mask, placed = synthetic_log_spiral()
        circ = extract_circles(mask)
        print(f"synthetic log-spiral: placed={placed} recovered={len(circ)} "
              f"err={abs(len(circ) - placed) / placed:.1%}")
        return

    circles, _ = extract_from_image(args.image, method=args.method,
                                    min_circularity=args.min_circularity,
                                    min_radius=args.min_radius)
    result = {
        "path": str(args.image),
        "n_circles": len(circles),
        "radii_px": [round(c["r"], 2) for c in circles],
        "circles": circles,
        "note": "Mask-first blob count (distinct flattened regions), not raw Hough votes.",
    }
    text = json.dumps(result, indent=2)
    print(f"{args.image}: {len(circles)} circles")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
