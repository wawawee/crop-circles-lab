"""Geometry information probes: radius-sequence entropy, diatonic hits, log-spiral fit.

Run on circle lists from Hough (prefer preprocessed masks) or synthetic generators.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np

try:
    from .ccat import detect_circles, load_bgr
    from .preprocess import pipeline, to_grayscale
except ImportError:
    from ccat import detect_circles, load_bgr
    from preprocess import pipeline, to_grayscale

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "forensics"))
import encoding as E  # noqa: E402
import ratios as R  # noqa: E402


def shannon_entropy(values: np.ndarray, bins: int = 16) -> float:
    hist, _ = np.histogram(values, bins=bins, density=True)
    hist = hist[hist > 0]
    return float(-(hist * np.log2(hist)).sum()) if len(hist) else 0.0


def radius_sequence_stats(radii: list[float]) -> dict:
    r = np.asarray(radii, dtype=float)
    r = r[r > 0]
    if len(r) < 3:
        return {"n": int(len(r)), "error": "too_few"}
    ratios = r[1:] / r[:-1]
    return {
        "n": int(len(r)),
        "radius_entropy_bits": round(shannon_entropy(r), 4),
        "ratio_mean": round(float(ratios.mean()), 5),
        "ratio_std": round(float(ratios.std()), 5),
        "ratio_cv": round(float(ratios.std() / ratios.mean()), 5) if ratios.mean() else None,
        "log_spiral_like": bool(ratios.std() / ratios.mean() < 0.15 and ratios.mean() < 1.0)
        if ratios.mean()
        else False,
        "nearest_diatonic_first_ratio": str(R.nearest_diatonic(float(ratios[0])).note)
        if len(ratios)
        else None,
    }


def circles_from_image(path: Path, use_mask: bool = True) -> list[tuple[float, float, float]]:
    bgr = load_bgr(path)
    if use_mask:
        mask = pipeline(bgr)["mask"]
        # feed masked gray to Hough: standing crop suppressed
        gray = to_grayscale(bgr)
        masked = gray.copy()
        masked[~mask] = 0
        circs, _ = detect_circles(masked, return_array=True)
    else:
        gray = to_grayscale(bgr)
        circs, _ = detect_circles(gray, return_array=True)
    if circs is None:
        return []
    return [(float(x), float(y), float(r)) for x, y, r in circs[0]]


def analyze(path: Path | None = None, synthetic_julia: bool = False) -> dict:
    if synthetic_julia:
        circles = E.generate_log_spiral_circles(n=150)
        src = "synthetic_log_spiral"
    else:
        assert path is not None
        circles = circles_from_image(path)
        src = str(path)
    radii = [c[2] for c in circles]
    # sort by distance from centroid for a crude spiral order
    if circles:
        cx = sum(c[0] for c in circles) / len(circles)
        cy = sum(c[1] for c in circles) / len(circles)
        ordered = sorted(circles, key=lambda c: math.hypot(c[0] - cx, c[1] - cy))
        radii_radial = [c[2] for c in ordered]
    else:
        radii_radial = radii

    julia_class = E.is_true_julia_set(circles) if len(circles) >= 10 else None
    return {
        "source": src,
        "n_circles": len(circles),
        "stats_detection_order": radius_sequence_stats(radii),
        "stats_radial_order": radius_sequence_stats(radii_radial),
        "julia_classification": julia_class,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", nargs="?")
    ap.add_argument("--synthetic-julia", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    result = analyze(Path(args.image) if args.image else None, synthetic_julia=args.synthetic_julia)
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)


if __name__ == "__main__":
    main()
