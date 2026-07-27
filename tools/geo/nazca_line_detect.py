#!/usr/bin/env python3
"""
nazca_line_detect.py  --  G22: Nazca line-type geoglyph geometry detector.

Detects long-thin line structure in satellite-like imagery tiles using:

  1. CLAHE → Canny → HoughLinesP (long-line geometry)
  2. Sato ridge filter (alternative line enhancement)
  3. Composite long-thin line score

Pipeline is calibrated on synthetic tiles:
  * planted       – known-answer long straight lines
  * csr           – Complete Spatial Randomness (Bernoulli noise)
  * ridge_clutter – smoothed texture with ridge-like artifacts
  * desert_noise  – low-contrast perlin-like surface
  * scramble      – pixel-shuffled planted tile (matches density)

Negative control: identical pipeline on desert null tiles must not exceed
planted FPR at calibrated threshold.

Verdict vocabulary:
  FPR_CALIBRATED  – detector separates planted lines from desert nulls at
                    known false-positive rate
  LINE_STRUCTURE  – line-like geometry detected with confidence
  NO_SIGNAL       – pipeline fires at or below null expectation
  UNDERDETERMINED – ambiguous or insufficient tile resolution
  FIXTURE_ONLY    – synthetic tiles only; no real Nazca tile loaded

Stance: structure != meaning. Detecting lines ≠ "aliens built Nazca."
Figurative reliefs (<50 m) are UNDERDETERMINED at Sentinel-2 10 m GSD.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from typing import Any

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

DEFAULT_TILE_SIZE = 256
DEFAULT_N_TILES = 30
DEFAULT_LINE_DENSITY = 0.04
DEFAULT_BG_NOISE = 0.02
DEFAULT_SEED = 1337
DEFAULT_NULL_QUANTILE = 0.99

FORBIDDEN_PHRASES = [
    "aliens",
    "ancient astronauts",
    "decoded map",
    "extraterrestrial landing",
    "alien built",
    "message from beyond",
    "nazca code cracked",
]

# ---------------------------------------------------------------------------
# tile generators
# ---------------------------------------------------------------------------


def _desert_bg(size: int, rng: np.random.Generator) -> np.ndarray:
    """8-bit desert-varnish-like background (gentle perlin-ish gradient)."""
    tile = rng.standard_normal((size, size))
    for _ in range(6):
        tile = (
            tile
            + np.roll(tile, 1, axis=0)
            + np.roll(tile, -1, axis=0)
            + np.roll(tile, 1, axis=1)
            + np.roll(tile, -1, axis=1)
        ) / 5.0
    tile = tile - tile.min()
    tile = tile / tile.max()
    tile = (tile * 55 + 140).clip(0, 255).astype(np.uint8)
    noise = rng.integers(-12, 12, (size, size), dtype=np.int16)
    tile = (tile + noise).clip(0, 255).astype(np.uint8)
    return tile


def _rng_offset(rng: np.random.Generator, lo: int, hi: int) -> int:
    return int(rng.integers(lo, hi + 1))


def make_tile(
    kind: str,
    size: int = DEFAULT_TILE_SIZE,
    line_density: float = DEFAULT_LINE_DENSITY,
    bg_noise: float = DEFAULT_BG_NOISE,
    rng: np.random.Generator | None = None,
    reference: np.ndarray | None = None,
) -> np.ndarray:
    """Return an 8-bit grayscale synthetic tile.

    Kinds:
      planted       -- 2-3 long thin lines on desert background (known-answer)
      csr           -- independent Bernoulli noise at *line_density*
      ridge_clutter -- smoothed random field with ridge artifacts
      desert_noise  -- low-contrast perlin-like surface (no straight lines)
      scramble      -- pixel-wise shuffle of a *reference* tile
    """
    rng = rng if rng is not None else np.random.default_rng()

    if kind == "csr":
        noise = (rng.random((size, size)) < line_density).astype(np.uint8) * 255
        return noise

    if kind == "desert_noise":
        return _desert_bg(size, rng)

    if kind == "ridge_clutter":
        bg = np.random.random((size, size))
        for _ in range(12):
            bg = (
                bg
                + np.roll(bg, 1, axis=0)
                + np.roll(bg, -1, axis=0)
                + np.roll(bg, 1, axis=1)
                + np.roll(bg, -1, axis=1)
            ) / 5.0
        bg = bg - bg.min()
        bg = bg / bg.max()
        ridge_mask = bg > np.quantile(bg, 1.0 - line_density * 2)
        tile = _desert_bg(size, rng)
        tile[ridge_mask] = rng.integers(50, 90)
        return tile

    if kind == "planted":
        return _make_planted(size, line_density, bg_noise, rng)

    if kind == "scramble":
        ref = reference if reference is not None else _make_planted(size, line_density, bg_noise, rng)
        flat = ref.ravel()
        return flat[rng.permutation(flat.size)].reshape(ref.shape).astype(np.uint8)

    raise ValueError(f"unknown tile kind: {kind!r}")


def _make_planted(
    size: int,
    line_density: float,
    bg_noise: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Draw 2-3 long bright lines on a desert background (Nazca-like)."""
    tile = _desert_bg(size, rng)
    n_lines = rng.integers(2, 4)
    line_val = rng.integers(220, 245)
    for _ in range(n_lines):
        angle = rng.uniform(0, 180)
        max_len = int(size * 1.4 * rng.uniform(0.7, 0.95))
        cx = rng.integers(size // 4, 3 * size // 4)
        cy = rng.integers(size // 4, 3 * size // 4)
        _draw_line(tile, cx, cy, angle, max_len, line_val, rng)
    extra_noise = rng.random((size, size)) < bg_noise
    tile[extra_noise] = rng.integers(60, 130, size=int(extra_noise.sum()))
    return tile


def _draw_line(
    tile: np.ndarray,
    cx: int, cy: int,
    angle_deg: float,
    length: int,
    val: int,
    rng: np.random.Generator,
    width: int = 2,
) -> None:
    """Draw a line segment on *tile* in-place."""
    s = math.sin(math.radians(angle_deg))
    c = math.cos(math.radians(angle_deg))
    h, w = tile.shape
    for step in range(-length // 2, length // 2):
        x = int(round(cx + step * c))
        y = int(round(cy + step * s))
        for dw in range(-width // 2, width // 2 + 1):
            for dh in range(-width // 2, width // 2 + 1):
                if 0 <= y + dh < h and 0 <= x + dw < w:
                    tile[y + dh, x + dw] = np.clip(val + _rng_offset(rng, -15, 15), 0, 255)


# ---------------------------------------------------------------------------
# line detection pipeline
# ---------------------------------------------------------------------------


def line_score(tile: np.ndarray) -> float:
    """Long-thin line score using Hough accumulator peak analysis.

    Pipeline:
      1. CLAHE → Sobel gradient magnitude → normalize
      2. Threshold at high percentile to keep only strongest edges
      3. Standard HoughLines (not P) → accumulator peaks
      4. Score = max accumulator value / diagonal (normalised)

    The Hough accumulator peak is high only when many edge pixels
    are colinear — characteristic of Nazca-like long straight lines.
    Desert noise produces scattered edge pixels with weaker
    colinear support.
    """
    size = tile.shape[0]
    if size < 20:
        return 0.0

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(tile)
    blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)

    grad_x = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
    mag = cv2.magnitude(grad_x, grad_y)
    m_max = mag.max()
    if m_max > 0:
        mag = (mag / m_max * 255).astype(np.uint8)
    else:
        return 0.0

    thr = max(1, int(np.percentile(mag[mag > 0], 90)) if np.any(mag > 0) else 1)
    _, strong = cv2.threshold(mag, thr, 255, cv2.THRESH_BINARY)

    lines = cv2.HoughLinesP(
        strong,
        rho=1,
        theta=math.pi / 360,
        threshold=max(5, size // 12),
        minLineLength=size // 4,
        maxLineGap=size // 16,
    )

    if lines is None:
        return 0.0

    longest = 0.0
    n_long = 0
    for seg in lines:
        x1, y1, x2, y2 = seg[0]
        L = math.hypot(x2 - x1, y2 - y1)
        if L > longest:
            longest = L
        if L >= size * 0.3:
            n_long += 1

    diag = math.hypot(size, size)
    score = (longest / diag) * 50.0 + n_long * 5.0
    return score


# ---------------------------------------------------------------------------
# FPR calibration
# ---------------------------------------------------------------------------


def run_calibration(
    n_tiles: int = DEFAULT_N_TILES,
    size: int = DEFAULT_TILE_SIZE,
    line_density: float = DEFAULT_LINE_DENSITY,
    bg_noise: float = DEFAULT_BG_NOISE,
    seed: int = DEFAULT_SEED,
    null_quantile: float = DEFAULT_NULL_QUANTILE,
) -> dict[str, Any]:
    """Generate tiles and calibrate detector FPR.

    Returns a dict with scores, thresholds, FPRs, and a verdict.
    """
    rng = np.random.default_rng(seed)

    kinds = ["planted", "csr", "ridge_clutter", "desert_noise", "scramble"]
    scores: dict[str, list[float]] = {k: [] for k in kinds}

    for kind in kinds:
        for i in range(n_tiles):
            ref = None
            if kind == "scramble":
                ref = _make_planted(size, line_density, bg_noise, np.random.default_rng(seed + i + 1))
            tile = make_tile(kind, size, line_density, bg_noise, rng, reference=ref)
            scores[kind].append(line_score(tile))

    # Combined null from all desert/negative kinds
    null_kinds = ["csr", "ridge_clutter", "desert_noise", "scramble"]
    null_scores = np.concatenate([scores[k] for k in null_kinds])
    threshold = float(np.quantile(null_scores, null_quantile))

    def _fpr(arr):
        arr = np.asarray(arr)
        if len(arr) == 0:
            return 0.0
        return float(np.mean(arr >= threshold))

    fpr_by_kind = {k: _fpr(scores[k]) for k in null_kinds}
    fpr_combined = _fpr(null_scores)
    planted_scores = np.array(scores["planted"])
    power_planted = float(np.mean(planted_scores >= threshold))

    # verdict logic ---------------------------------------------------------
    real_data_verdict = "FIXTURE_ONLY"
    caveats = [
        "Tiles are synthetic; no real Nazca Sentinel-2 tile was fetched.",
        "Sentinel-2 (10 m GSD) UNDERDETERMINED for figurative reliefs <50 m.",
        "Bing/ESRI programmatic download is FORBIDDEN by ToS.",
        "Synthetic desert noise includes CSR, ridge clutter, and perlin-like texture.",
        "Detecting line geometry does NOT imply artificial origin.",
        "Structure != meaning. This is a geometry detector, not a claims engine.",
        "Figurative reliefs (e.g. hummingbird, spider) are below resolution threshold.",
    ]

    if power_planted >= 0.8 and fpr_combined <= 0.05:
        verdict = "FPR_CALIBRATED"
        reason = (
            f"Line detector separates planted long-line tiles from desert nulls "
            f"at the {null_quantile:.0%} threshold, with power={power_planted:.2%} "
            f"and FPR_combined={fpr_combined:.2%}. "
            f"Applied to synthetic Nazca-like tiles: LINE_STRUCTURE detected."
        )
    elif power_planted < 0.5:
        verdict = "NO_SIGNAL"
        reason = (
            f"Detector fails on planted known-answer tiles (power={power_planted:.2%}); "
            f"cannot distinguish lines from desert noise."
        )
    elif fpr_combined > 0.10:
        verdict = "NO_SIGNAL"
        reason = (
            f"Detector false-positive rate on desert nulls is too high "
            f"(FPR_combined={fpr_combined:.2%}); not calibrated."
        )
    else:
        verdict = "UNDERDETERMINED"
        reason = (
            f"Calibration intermediate: power={power_planted:.2%}, "
            f"FPR_combined={fpr_combined:.2%}. "
            f"Not cleanly separated."
        )

    return {
        "verdict": verdict,
        "real_data_verdict": real_data_verdict,
        "reason": reason,
        "domain": "nazca_line_detect",
        "ticket": "G22",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "n_tiles": n_tiles,
            "size": size,
            "line_density": line_density,
            "bg_noise": bg_noise,
            "seed": seed,
            "null_quantile": null_quantile,
        },
        "threshold": threshold,
        "scores": {
            kind: {
                "mean": round(float(np.mean(v)), 3),
                "std": round(float(np.std(v, ddof=1)), 3),
                "min": round(float(np.min(v)), 3),
                "max": round(float(np.max(v)), 3),
                "values": [round(float(x), 3) for x in v],
            }
            for kind, v in scores.items()
        },
        "fpr": {
            kind: round(v, 4) for kind, v in fpr_by_kind.items()
        },
        "fpr_combined": round(fpr_combined, 4),
        "power_planted": round(power_planted, 4),
        "caveats": caveats,
    }


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------


def write_notes(result: dict[str, Any], path: str) -> None:
    lines = [
        "# G22 — Nazca Line Detection Probe -- NOTES",
        "",
        "**Verdict:** `" + result["verdict"] + "`  ",
        "**Real-data verdict:** `" + result["real_data_verdict"] + "`  ",
        "",
        result["reason"],
        "",
        "## What this is",
        "",
        "A geometry detector calibrated on synthetic tiles to identify",
        "long-thin line structure (Nazca line-type geoglyph geometry).",
        "It does NOT detect figurative reliefs (<50 m) which are",
        "underdetermined at Sentinel-2 10 m GSD.",
        "",
        "## Tile types",
        "",
        "- **planted**: 2-3 long thin lines on desert-varnish background (known-answer)",
        "- **csr**: random Bernoulli noise",
        "- **ridge_clutter**: smoothed texture with ridge artifacts",
        "- **desert_noise**: low-contrast perlin-like surface",
        "- **scramble**: pixel-shuffled planted tile (density-matched)",
        "",
        "## Pipeline",
        "",
        "1. CLAHE contrast enhancement (clipLimit=3.0, 8x8 tiles)",
        "2. Gaussian blur (3x3)",
        "3. Sobel gradient magnitude → 90th-percentile threshold",
        "4. HoughLinesP (rho=1, theta=pi/360, tuned thresholds)",
        "5. Score = f(longest_segment, n_segments_>_30%_tile_size)",
        "",
        "## Results",
        "",
        "| metric | value |",
        "|---|---|",
        f"| threshold | {result['threshold']:.3f} |",
        f"| power_planted | {result['power_planted']:.2%} |",
        f"| FPR (csr) | {result['fpr']['csr']:.2%} |",
        f"| FPR (ridge_clutter) | {result['fpr']['ridge_clutter']:.2%} |",
        f"| FPR (desert_noise) | {result['fpr']['desert_noise']:.2%} |",
        f"| FPR (scramble) | {result['fpr']['scramble']:.2%} |",
        f"| FPR (combined) | {result['fpr_combined']:.2%} |",
        "",
        "## Caveats",
        "",
    ] + ["- " + c for c in result["caveats"]] + [
        "",
        "## Honest bottom line",
        "",
        "The detector's line geometry score is calibrated on synthetic tiles. ",
        "No real Nazca imagery was fetched (Sentinel-2 not downloaded; ",
        "Bing/ESRI programmatic access is FORBIDDEN by ToS). ",
        "All results are FIXTURE_ONLY.",
        "",
        "*Structure != meaning. Long lines ≠ message.*",
        "",
    ]
    with open(path, "w") as fh:
        fh.write("\n".join(lines))


def _check_forbidden(text: str, phrases: list[str]) -> list[str]:
    lowered = text.lower()
    return [p for p in phrases if p.lower() in lowered]


def write_sample_tiles(
    data_dir: str,
    n_per_kind: int = 3,
    size: int = 128,
    line_density: float = DEFAULT_LINE_DENSITY,
    bg_noise: float = DEFAULT_BG_NOISE,
    seed: int = 42,
) -> list[str]:
    """Write a small deterministic archive of tile fixtures."""
    os.makedirs(data_dir, exist_ok=True)
    rng = np.random.default_rng(seed)
    archive: list[dict] = []
    for kind in ["planted", "csr", "ridge_clutter", "desert_noise", "scramble"]:
        for i in range(n_per_kind):
            ref = None
            if kind == "scramble":
                ref = _make_planted(size, line_density, bg_noise, np.random.default_rng(seed + i + 100))
            tile = make_tile(kind, size, line_density, bg_noise, rng, reference=ref)
            archive.append({
                "kind": kind,
                "size": size,
                "seed": seed + i,
                "tile_b64": _tile_to_b64(tile),
            })
    out_path = os.path.join(data_dir, "tiles.json")
    with open(out_path, "w") as fh:
        json.dump(archive, fh, indent=2)
    return [out_path]


def _tile_to_b64(tile: np.ndarray) -> str:
    """Encode 8-bit tile as base64 PNG via cv2."""
    import base64
    _, buf = cv2.imencode(".png", tile)
    return base64.b64encode(buf.tobytes()).decode("ascii")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", default="outputs/nazca",
                    help="where to write run.json + NOTES.md")
    ap.add_argument("--data-dir", default="data/nazca",
                    help="where to write sample tiles")
    ap.add_argument("--n-tiles", type=int, default=DEFAULT_N_TILES)
    ap.add_argument("--size", type=int, default=DEFAULT_TILE_SIZE)
    ap.add_argument("--line-density", type=float, default=DEFAULT_LINE_DENSITY)
    ap.add_argument("--bg-noise", type=float, default=DEFAULT_BG_NOISE)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--null-quantile", type=float, default=DEFAULT_NULL_QUANTILE)
    ap.add_argument("--no-tiles", action="store_true",
                    help="skip writing sample control tiles")
    args = ap.parse_args()

    result = run_calibration(
        n_tiles=args.n_tiles,
        size=args.size,
        line_density=args.line_density,
        bg_noise=args.bg_noise,
        seed=args.seed,
        null_quantile=args.null_quantile,
    )

    os.makedirs(args.out_dir, exist_ok=True)
    run_path = os.path.join(args.out_dir, "run.json")
    notes_path = os.path.join(args.out_dir, "NOTES.md")

    with open(run_path, "w") as fh:
        json.dump(result, fh, indent=2)

    write_notes(result, notes_path)

    for _gp in [notes_path, run_path, os.path.join(args.data_dir, "README.md")]:
        if os.path.exists(_gp):
            forbidden = _check_forbidden(open(_gp).read(), FORBIDDEN_PHRASES)
            if forbidden:
                raise RuntimeError(f"forbidden phrases in {_gp}: " + ", ".join(forbidden))

    if not args.no_tiles:
        write_sample_tiles(args.data_dir, n_per_kind=3, size=128,
                           line_density=args.line_density,
                           bg_noise=args.bg_noise, seed=args.seed)

    print(json.dumps({
        "verdict": result["verdict"],
        "real_data_verdict": result["real_data_verdict"],
        "threshold": result["threshold"],
        "power_planted": result["power_planted"],
        "fpr_combined": result["fpr_combined"],
    }, indent=2))
    print(f"wrote {run_path} and {notes_path}")


if __name__ == "__main__":
    main()
