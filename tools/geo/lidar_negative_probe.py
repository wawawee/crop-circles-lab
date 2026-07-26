#!/usr/bin/env python3
"""
lidar_negative_probe.py -- Amazon LiDAR negative / control hardening (Mode A-NEG)

G-Amazon Mode A already showed STRUCTURE_ONLY for *earthwork coordinate*
clustering. This probe is a deliberately harder negative-control layer:
it asks whether a simple spectral/periodicity detector can hallucinate
"geoglyph-like" structure when it is only fed

  * random CSR tiles,
  * smoothed forest-like texture tiles (mimicking canopy/terrain roughness), and
  * pixel-scrambled versions of planted geoglyphs.

Because no public dense LiDAR/DEM tile for a named Amazon geoglyph was
located, the experiment is run on synthetic tiles. The deliverable is an
FPR calibration, not a claim about real Amazonia.

Verdict vocabulary:
    NO_SIGNAL      -- detector fires too often on negatives (high FPR)
    FPR_CALIBRATED -- detector is validated on planted geoglyphs and has
                      a calibrated, low false-positive rate on CSR/scramble
    UNDERDETERMINED-- ambiguous calibration, or real LiDAR data absent

Stance: structure != meaning. A low FPR on synthetic negatives does not
imply that any real LiDAR tile contains a geoglyph.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from typing import Any

import numpy as np

# Reuse the existing grid structure analyzer (there is no spatial_pattern.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ccat"))
import grid_analyze  # noqa: E402

# ----------------------------------------------------------------------------
# constants
# ----------------------------------------------------------------------------

DEFAULT_SHAPE = (128, 128)
DEFAULT_DENSITY = 0.08
DEFAULT_N_TILES = 40
DEFAULT_SEED = 1337

FORBIDDEN_PHRASES = [
    "lost cities proven",
    "aliens",
    "fake lidar hits",
    "fake LiDAR hits",
    "aliens built",
    "decoded message",
]


# ----------------------------------------------------------------------------
# tile generators
# ----------------------------------------------------------------------------

def make_tile(
    kind: str,
    shape: tuple[int, int] = DEFAULT_SHAPE,
    density: float = DEFAULT_DENSITY,
    rng: np.random.Generator | None = None,
    reference: np.ndarray | None = None,
) -> np.ndarray:
    """Return a synthetic binary tile mask.

    Kinds:
      csr      -- independent Bernoulli (Complete Spatial Randomness)
      forest   -- smoothed perlin-like texture, thresholded to ``density``
      planted  -- a synthetic straight-line geoglyph (known-answer)
      scramble -- pixel-wise shuffle of a planted reference
      stripes  -- simple periodic stripes (diagnostic/known-answer)
    """
    rng = rng if rng is not None else np.random.default_rng()
    if kind == "csr":
        return rng.random(shape) < density
    if kind == "forest":
        return _make_forest(shape, density, rng)
    if kind == "planted":
        return _make_planted(shape, density, rng)
    if kind == "scramble":
        ref = reference if reference is not None else _make_planted(shape, density, rng)
        flat = ref.ravel()
        return flat[rng.permutation(flat.size)].reshape(ref.shape)
    if kind == "stripes":
        return _make_stripes(shape)
    raise ValueError(f"unknown tile kind: {kind!r}")


def _make_forest(shape, density, rng):
    """Smooth random field -> contiguous canopy-like patches."""
    g = rng.random(shape)
    for _ in range(10):
        # box smoothing using only numpy (no scipy)
        g = (
            g
            + np.roll(g, 1, axis=0)
            + np.roll(g, -1, axis=0)
            + np.roll(g, 1, axis=1)
            + np.roll(g, -1, axis=1)
        ) / 5.0
    thr = np.quantile(g, 1.0 - density)
    return g > thr


def _make_planted(shape, density, rng):
    """Synthetic geoglyph: a square enclosure plus diagonal cross.

    Additional random points are sprinkled to bring the overall density close
    to ``density`` while keeping the dominant straight-line structure.
    """
    h, w = shape
    mask = np.zeros(shape, dtype=bool)

    # square enclosure
    y1, x1 = h // 4, w // 4
    y2, x2 = 3 * h // 4, 3 * w // 4
    mask[y1 : y2 + 1, x1] = True
    mask[y1 : y2 + 1, x2] = True
    mask[y1, x1 : x2 + 1] = True
    mask[y2, x1 : x2 + 1] = True

    # diagonal cross
    for i in range(min(h, w)):
        y = i
        x = int(i * w / h)
        mask[y, x] = True
        mask[y, w - 1 - x] = True

    # fill to target density with random noise
    target = int(np.prod(shape) * density)
    current = int(mask.sum())
    if current < target:
        free = np.argwhere(~mask)
        n_add = min(target - current, free.shape[0])
        chosen = free[rng.choice(free.shape[0], n_add, replace=False)]
        mask[chosen[:, 0], chosen[:, 1]] = True
    return mask


def _make_stripes(shape):
    """Vertical stripes -- strongest possible known-answer for the detector."""
    mask = np.zeros(shape, dtype=bool)
    period = max(2, shape[1] // 8)
    for i in range(0, shape[1], period * 2):
        mask[:, i : min(i + period, shape[1])] = True
    return mask


# ----------------------------------------------------------------------------
# detector / score
# ----------------------------------------------------------------------------

def _fft_peakiness_highpass(grid: np.ndarray, hp_radius: int | None = None) -> float:
    """FFT peak-to-mean magnitude after masking the central low-frequency square.

    Removing the low-frequency blob suppresses false peaks from smooth forest
    texture, while keeping the sharp spectral peaks produced by straight-line
    geoglyphs.
    """
    g = np.asarray(grid, dtype=float)
    g = g - g.mean()
    if np.allclose(g, 0):
        return 0.0
    mag = np.abs(np.fft.fftshift(np.fft.fft2(g)))
    cy, cx = (s // 2 for s in mag.shape)
    if hp_radius is None:
        hp_radius = max(1, min(cy, cx) // 4)
    y, x = np.ogrid[: mag.shape[0], : mag.shape[1]]
    central = (np.abs(y - cy) <= hp_radius) & (np.abs(x - cx) <= hp_radius)
    mag[central] = 0.0
    m = mag.mean()
    return float(mag.max() / m) if m > 0 else 0.0


def _elongation_score(mask: np.ndarray, min_area: int = 10) -> float:
    """Geometric score based on the most elongated 8-connected component.

    Geoglyph lines are long and thin (high aspect ratio, large max-dimension
    relative to sqrt(area)). Forest texture produces compact, blob-like
    components. The score is the maximum over components of
        max_dim / sqrt(area)
    which is high for thin lines and low for blobs.
    """
    g = np.asarray(mask, dtype=bool)
    labeled = np.zeros(g.shape, dtype=int)
    label_id = 0
    h, w = g.shape
    best = 0.0
    for r0 in range(h):
        for c0 in range(w):
            if not g[r0, c0] or labeled[r0, c0]:
                continue
            label_id += 1
            # DFS with a Python list as a stack
            stack = [(r0, c0)]
            labeled[r0, c0] = label_id
            min_r, max_r = r0, r0
            min_c, max_c = c0, c0
            count = 0
            while stack:
                r, c = stack.pop()
                count += 1
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < h and 0 <= nc < w and g[nr, nc] and not labeled[nr, nc]:
                            labeled[nr, nc] = label_id
                            stack.append((nr, nc))
                            min_r = min(min_r, nr)
                            max_r = max(max_r, nr)
                            min_c = min(min_c, nc)
                            max_c = max(max_c, nc)
            if count >= min_area:
                dim_r = max_r - min_r + 1
                dim_c = max_c - min_c + 1
                max_dim = max(dim_r, dim_c)
                best = max(best, float(max_dim / math.sqrt(count)))
    return best


def geoglyph_score(mask: np.ndarray) -> float:
    """Scalar false-geoglyph score.

    Combines an elongation-based line score with high-pass 2D-FFT spectral
    peakiness and the strength of the dominant periodicity. High values flag
    grids that contain straight, repeated, or axis-aligned structure; low values
    indicate random or texture-like masks.
    """
    g = np.asarray(mask, dtype=bool)
    if g.size < 100:
        return 0.0
    elong = _elongation_score(g)
    fftp = _fft_peakiness_highpass(g)
    period_corr = grid_analyze.dominant_period(g)["corr"]
    return float(5.0 * elong + 0.1 * fftp + 2.0 * max(0.0, period_corr))


# ----------------------------------------------------------------------------
# FPR calibration
# ----------------------------------------------------------------------------

def run_calibration(
    n_tiles: int = DEFAULT_N_TILES,
    shape: tuple[int, int] = DEFAULT_SHAPE,
    density: float = DEFAULT_DENSITY,
    seed: int = DEFAULT_SEED,
    null_quantile: float = 0.99,
) -> dict[str, Any]:
    """Generate synthetic tiles and calibrate detector FPR vs CSR & scramble.

    Returns a dict with scores, thresholds, FPRs, and a verdict.
    """
    rng = np.random.default_rng(seed)

    kinds = ["csr", "forest", "scramble", "planted"]
    scores: dict[str, list[float]] = {kind: [] for kind in kinds}

    for kind in kinds:
        for i in range(n_tiles):
            ref = None
            if kind == "scramble":
                # scramble a freshly generated planted tile so density matches
                ref = _make_planted(shape, density, np.random.default_rng(seed + i + 1))
            tile = make_tile(kind, shape, density, rng, reference=ref)
            scores[kind].append(geoglyph_score(tile))

    null_scores = np.array(scores["csr"] + scores["scramble"] + scores["forest"])
    threshold = float(np.quantile(null_scores, null_quantile))

    def fpr(arr):
        arr = np.asarray(arr)
        if len(arr) == 0 or threshold == 0:
            return 0.0
        return float(np.mean(arr >= threshold))

    fpr_csr = fpr(scores["csr"])
    fpr_scramble = fpr(scores["scramble"])
    fpr_forest = fpr(scores["forest"])
    fpr_combined = fpr(null_scores)
    power_planted = float(np.mean(np.array(scores["planted"]) >= threshold))

    # verdict logic ----------------------------------------------------------
    real_data_verdict = "UNDERDETERMINED"
    if power_planted < 0.5:
        verdict = "NO_SIGNAL"
        reason = (
            "Detector fails on planted geoglyphs; cannot trust any future LiDAR claim."
        )
    elif fpr_combined > 0.05 or fpr_csr > 0.10 or fpr_scramble > 0.10 or fpr_forest > 0.10:
        verdict = "NO_SIGNAL"
        reason = (
            "Detector fires too readily on one or more negative controls; FPR is not calibrated."
        )
    elif power_planted >= 0.8 and fpr_combined <= 0.05:
        verdict = "FPR_CALIBRATED"
        reason = (
            "Detector separates planted geoglyphs from CSR/forest/scramble nulls at a "
            f"{null_quantile:.0%} threshold, with power={power_planted:.2%} and "
            f"FPR_combined={fpr_combined:.2%}."
        )
        real_data_verdict = "UNDERDETERMINED"
    else:
        verdict = "UNDERDETERMINED"
        reason = (
            "Calibration is intermediate: detector shows some discrimination, "
            "but not enough to claim a reliable FPR for real LiDAR tiles."
        )

    return {
        "verdict": verdict,
        "real_data_verdict": real_data_verdict,
        "reason": reason,
        "domain": "amazon_lidar_neg",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "n_tiles": n_tiles,
            "shape": list(shape),
            "density": density,
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
            "csr": round(fpr_csr, 4),
            "scramble": round(fpr_scramble, 4),
            "forest": round(fpr_forest, 4),
            "combined": round(fpr_combined, 4),
        },
        "power_planted": round(power_planted, 4),
        "caveats": [
            "Tiles are synthetic; no public dense LiDAR/DEM tile for a named Amazon geoglyph was located.",
            "Forest texture is a smoothed random field, not a canopy-LiDAR DEM.",
            "A calibrated FPR on synthetic negatives does not imply any real geoglyph signal.",
            "Structure detection is not a message or civilisation claim.",
        ],
    }


# ----------------------------------------------------------------------------
# IO / packaging
# ----------------------------------------------------------------------------

def _tile_to_json(mask: np.ndarray, kind: str, seed: int, density: float) -> dict:
    return {
        "kind": kind,
        "shape": list(mask.shape),
        "density": density,
        "seed": seed,
        "mask": ["".join("1" if v else "0" for v in row) for row in mask.tolist()],
    }


def _tile_from_json(data: dict) -> np.ndarray:
    rows = data["mask"]
    return np.array([[int(ch) for ch in row] for row in rows], dtype=bool)


def write_sample_tiles(
    data_dir: str,
    n_per_kind: int = 3,
    shape: tuple[int, int] = (64, 64),
    density: float = DEFAULT_DENSITY,
    seed: int = 42,
) -> list[str]:
    """Write a small deterministic archive of negative/control tiles."""
    os.makedirs(data_dir, exist_ok=True)
    rng = np.random.default_rng(seed)
    paths: list[str] = []
    archive: list[dict] = []
    for kind in ["csr", "forest", "planted", "scramble"]:
        for i in range(n_per_kind):
            ref = None
            if kind == "scramble":
                ref = _make_planted(shape, density, np.random.default_rng(seed + i + 100))
            tile = make_tile(kind, shape, density, rng, reference=ref)
            archive.append(_tile_to_json(tile, kind, seed + i, density))
    out_path = os.path.join(data_dir, "tiles.json")
    with open(out_path, "w") as fh:
        json.dump(archive, fh, indent=2)
    paths.append(out_path)
    return paths


def write_notes(result: dict[str, Any], path: str) -> None:
    lines = [
        "# Amazon LiDAR Negative / Control Probe (Mode A-NEG) -- NOTES",
        "",
        "**Verdict:** `" + result["verdict"] + "`  ",
        "**Real-data verdict:** `" + result["real_data_verdict"] + "`  ",
        "",
        result["reason"],
        "",
        "## What this is",
        "",
        "This is a *negative-control hardening* experiment for the Amazon ",
        "geoglyph/earthwork detection pipeline. It does **not** claim to have ",
        "found anything in real Amazon LiDAR. Instead, it calibrates how often a ",
        "simple spectral detector will falsely flag random or texture-like tiles ",
        "as 'geoglyph-like'.",
        "",
        "## Method",
        "",
        "- Synthetic tiles: " + " × ".join(str(s) for s in result["parameters"]["shape"]) + ", "
        "density=" + str(result["parameters"]["density"]) + ".",
        "- Negative tiles: `csr` (independent random) and `scramble` (pixel-shuffled planted).",
        "- Texture tiles: `forest` (smoothed random field, a canopy/terrain surrogate).",
        "- Known-answer tiles: `planted` (synthetic straight-line geoglyph).",
        "- Detector: 2D-FFT peakiness + dominant-period correlation.",
        "- Calibration: threshold = " + f"{result['parameters']['null_quantile']:.0%} "
        "quantile of the combined CSR+forest+scramble null distribution.",
        "",
        "## Results",
        "",
        "| metric | value |",
        "|---|---|",
        f"| threshold | {result['threshold']:.3f} |",
        f"| power_planted | {result['power_planted']:.2%} |",
        f"| FPR (csr) | {result['fpr']['csr']:.2%} |",
        f"| FPR (scramble) | {result['fpr']['scramble']:.2%} |",
        f"| FPR (forest) | {result['fpr']['forest']:.2%} |",
        f"| FPR (combined null) | {result['fpr']['combined']:.2%} |",
        "",
        "## Caveats",
        "",
    ] + ["- " + c for c in result["caveats"]] + [
        "",
        "## Honest bottom line",
        "",
        "The detector's false-positive rate is calibrated on synthetic negatives. ",
        "Real Amazon LiDAR/DEM tiles were not available for this probe, so any ",
        "claim about real geoglyphs remains **underdetermined**.",
        "",
    ]
    with open(path, "w") as fh:
        fh.write("\n".join(lines))


def _check_forbidden(text: str, phrases: list[str]) -> list[str]:
    lowered = text.lower()
    return [p for p in phrases if p.lower() in lowered]


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", default="outputs/amazon_lidar_neg",
                    help="where to write run.json + NOTES.md")
    ap.add_argument("--data-dir", default="data/geo/amazon_lidar_neg",
                    help="where to write sample control tiles")
    ap.add_argument("--n-tiles", type=int, default=DEFAULT_N_TILES)
    ap.add_argument("--shape", type=int, nargs=2, default=DEFAULT_SHAPE,
                    help="tile height width")
    ap.add_argument("--density", type=float, default=DEFAULT_DENSITY)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--null-quantile", type=float, default=0.99)
    ap.add_argument("--no-tiles", action="store_true",
                    help="skip writing sample control tiles")
    args = ap.parse_args()

    shape = tuple(args.shape)
    result = run_calibration(
        n_tiles=args.n_tiles,
        shape=shape,
        density=args.density,
        seed=args.seed,
        null_quantile=args.null_quantile,
    )

    os.makedirs(args.out_dir, exist_ok=True)
    run_path = os.path.join(args.out_dir, "run.json")
    notes_path = os.path.join(args.out_dir, "NOTES.md")

    with open(run_path, "w") as fh:
        json.dump(result, fh, indent=2)

    write_notes(result, notes_path)

    # forbidden-phrase guard on generated docs and data files
    _guard_paths = [
        notes_path,
        run_path,
        os.path.join(args.data_dir, "README.md"),
        os.path.join(args.data_dir, "tiles.json"),
    ]
    for _gp in _guard_paths:
        if os.path.exists(_gp):
            with open(_gp) as fh:
                forbidden = _check_forbidden(fh.read(), FORBIDDEN_PHRASES)
            if forbidden:
                raise RuntimeError(f"forbidden phrases in {_gp}: " + ", ".join(forbidden))

    if not args.no_tiles:
        write_sample_tiles(args.data_dir, n_per_kind=3, shape=(64, 64),
                           density=args.density, seed=args.seed)

    print(json.dumps({
        "verdict": result["verdict"],
        "real_data_verdict": result["real_data_verdict"],
        "threshold": result["threshold"],
        "power_planted": result["power_planted"],
        "fpr": result["fpr"],
    }, indent=2))
    print("wrote", run_path, "and", notes_path)


if __name__ == "__main__":
    main()
