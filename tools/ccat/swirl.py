"""
Swirl / lay-direction probe (CW vs CCW).

Heuristic: in annular sectors around the formation centroid, estimate the dominant
orientation of edge gradients. Positive mean angle ≈ one swirl sense; negative the other.
This is a first-cut tool — works best on clean overhead aerials, not angled tourism shots.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def dominant_swirl(path: Path, rings: int = 4) -> dict:
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(path)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    cy, cx = h / 2.0, w / 2.0
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    yy, xx = np.mgrid[0:h, 0:w]
    dx = xx - cx
    dy = yy - cy
    r = np.sqrt(dx * dx + dy * dy)
    r_max = r.max() + 1e-6
    # Tangential component: gradient dotted with tangential unit vector
    # Tangential vector for CCW: (-dy, dx) / r
    tx = -dy / (r + 1e-6)
    ty = dx / (r + 1e-6)
    tangential = gx * tx + gy * ty
    mag = np.sqrt(gx * gx + gy * gy) + 1e-6
    weight = mag

    ring_stats = []
    for i in range(rings):
        lo = (i / rings) * r_max
        hi = ((i + 1) / rings) * r_max
        mask = (r >= lo) & (r < hi) & (mag > np.percentile(mag, 60))
        if not np.any(mask):
            ring_stats.append({"ring": i, "mean_tangential": None, "sense": "unknown"})
            continue
        mean_t = float(np.average(tangential[mask], weights=weight[mask]))
        sense = "ccw" if mean_t > 0 else "cw"
        ring_stats.append({"ring": i, "mean_tangential": round(mean_t, 4), "sense": sense})

    votes = [s["sense"] for s in ring_stats if s["sense"] in ("cw", "ccw")]
    overall = max(set(votes), key=votes.count) if votes else "unknown"
    return {
        "path": str(path),
        "overall_sense": overall,
        "rings": ring_stats,
        "note": "Heuristic only; confirm visually on overhead shots.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--rings", type=int, default=4)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    result = dominant_swirl(Path(args.image), rings=args.rings)
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)


if __name__ == "__main__":
    main()
