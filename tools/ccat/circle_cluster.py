"""Cluster Hough circle detections (Kimi imported DBSCAN but never wired it — now it is)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from sklearn.cluster import DBSCAN

try:
    from .ccat import detect_circles, load_bgr
except ImportError:
    from ccat import detect_circles, load_bgr


def cluster_circles(path: Path, eps_frac: float = 0.04, min_samples: int = 2) -> dict:
    """Collapse overlapping/noisy Hough hits into cluster centroids.

    Returns raw count vs clustered count — useful when raw Hough explodes (Kimi demo: 2064).
    """
    bgr = load_bgr(path)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    circs, raw_n = detect_circles(gray, return_array=True)
    if circs is None or raw_n == 0:
        return {"path": str(path), "raw_circles": 0, "clustered_circles": 0, "clusters": []}

    pts = circs[0][:, :2].astype(float)  # x, y
    radii = circs[0][:, 2].astype(float)
    eps = max(8.0, eps_frac * min(h, w))
    labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(pts)

    clusters = []
    for lab in sorted(set(labels)):
        if lab < 0:
            continue
        mask = labels == lab
        clusters.append(
            {
                "id": int(lab),
                "x": float(pts[mask, 0].mean()),
                "y": float(pts[mask, 1].mean()),
                "r": float(radii[mask].mean()),
                "members": int(mask.sum()),
            }
        )

    noise = int((labels < 0).sum())
    return {
        "path": str(path),
        "raw_circles": raw_n,
        "clustered_circles": len(clusters),
        "noise_points": noise,
        "eps_px": round(eps, 1),
        "clusters": clusters,
        "note": "Clustered count ≈ distinct circle centers after DBSCAN merge.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    result = cluster_circles(Path(args.image))
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)


if __name__ == "__main__":
    main()
