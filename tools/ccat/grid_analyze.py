"""grid_analyze.py — GLYPH-style "is this binary grid encoding information, and
what kind?" — made scriptable and testable for our formations.

Operates on a 2D binary grid (numpy bool / 0-1 array), e.g. the Chilbolton 73x23
"Arecibo reply" bitmap from chilbolton_grid.py, or any binarized formation panel.
It reports structure metrics and compares against a density-matched random
shuffle so we can say, with a number, whether a grid is more ordered than chance:

  * shannon_entropy   -- cell-value entropy in bits (1.0 = maximally balanced 0/1)
  * bit_balance       -- fraction of 1s
  * dominant_period   -- strongest repeat period in row / column profiles (autocorr)
  * fft_peakiness     -- 2D-FFT peak-to-mean (spectral structure vs flat noise)
  * symmetry          -- horizontal / vertical / 180-degree overlap fractions
  * structuredness_z  -- z-score of neighbour-agreement vs shuffled grids
                         (the "absence signal": order that random cells lack)

Stance: this DETECTS structure; it does not "decode messages." A high score means
"non-random / worth a closer look," never "aliens." Depends only on numpy.
Validated in tools/ccat/tests/test_grid_analyze.py.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np


def _as_binary(grid) -> np.ndarray:
    g = np.asarray(grid)
    if g.dtype != bool:
        g = g > (0.5 if g.max() <= 1 else 127)
    return g.astype(np.int8)


def shannon_entropy(grid) -> float:
    g = _as_binary(grid)
    p1 = g.mean()
    if p1 in (0.0, 1.0):
        return 0.0
    p0 = 1 - p1
    return float(-(p1 * np.log2(p1) + p0 * np.log2(p0)))


def bit_balance(grid) -> float:
    return float(_as_binary(grid).mean())


def _dominant_period_1d(vec):
    v = np.asarray(vec, dtype=float)
    v = v - v.mean()
    if np.allclose(v, 0):
        return 0, 0.0
    ac = np.correlate(v, v, mode="full")[len(v) - 1:]
    ac = ac / (ac[0] + 1e-12)
    lags = range(2, len(v) // 2 + 1)
    if not lags:
        return 0, 0.0
    best = max(lags, key=lambda L: ac[L])
    return int(best), float(ac[best])


def dominant_period(grid) -> dict:
    """Strongest repeat period along columns (from column means) and rows."""
    g = _as_binary(grid).astype(float)
    col_period, col_corr = _dominant_period_1d(g.mean(axis=0))  # across x
    row_period, row_corr = _dominant_period_1d(g.mean(axis=1))  # across y
    axis = "col" if col_corr >= row_corr else "row"
    period, corr = (col_period, col_corr) if axis == "col" else (row_period, row_corr)
    return {"axis": axis, "period": period, "corr": round(corr, 3),
            "col": (col_period, round(col_corr, 3)),
            "row": (row_period, round(row_corr, 3))}


def fft_peakiness(grid) -> float:
    """2D-FFT peak-to-mean magnitude (DC removed). ~flat noise -> low; periodic -> high."""
    g = _as_binary(grid).astype(float)
    g = g - g.mean()
    if np.allclose(g, 0):
        return 0.0
    mag = np.abs(np.fft.fftshift(np.fft.fft2(g)))
    cy, cx = (s // 2 for s in mag.shape)
    mag[cy, cx] = 0.0  # kill residual DC
    m = mag.mean()
    return float(mag.max() / m) if m > 0 else 0.0


def symmetry(grid) -> dict:
    g = _as_binary(grid)
    return {
        "horizontal": float((g == g[:, ::-1]).mean()),
        "vertical": float((g == g[::-1, :]).mean()),
        "rot180": float((g == g[::-1, ::-1]).mean()),
    }


def _neighbour_agreement(g):
    """Fraction of horizontally+vertically adjacent cell pairs that are equal."""
    h = (g[:, 1:] == g[:, :-1]).sum()
    v = (g[1:, :] == g[:-1, :]).sum()
    n = g.shape[0] * (g.shape[1] - 1) + (g.shape[0] - 1) * g.shape[1]
    return float((h + v) / n) if n else 0.0


def structuredness_z(grid, n: int = 200, seed: int = 0) -> float:
    """Z-score of neighbour-agreement vs density-matched shuffles.

    High positive z = smoother/more-ordered than chance; high negative z =
    more anti-correlated (checkerboard-like) than chance; |z| ~ 0 = random-like.
    """
    g = _as_binary(grid)
    stat = _neighbour_agreement(g)
    rng = np.random.default_rng(seed)
    flat = g.ravel().copy()
    samples = np.empty(n)
    for i in range(n):
        rng.shuffle(flat)
        samples[i] = _neighbour_agreement(flat.reshape(g.shape))
    mu, sd = samples.mean(), samples.std()
    return float((stat - mu) / sd) if sd > 1e-12 else 0.0


@dataclass
class GridReport:
    shape: tuple
    entropy_bits: float
    bit_balance: float
    dominant_period: dict
    fft_peakiness: float
    symmetry: dict
    structuredness_z: float
    verdict: str


def analyze(grid, n_shuffles: int = 200, seed: int = 0) -> GridReport:
    g = _as_binary(grid)
    ent = shannon_entropy(g)
    per = dominant_period(g)
    fftp = fft_peakiness(g)
    sym = symmetry(g)
    z = structuredness_z(g, n=n_shuffles, seed=seed)

    ordered = abs(z) >= 3.0 or fftp >= 20.0 or per["corr"] >= 0.5
    strong_sym = max(sym.values()) >= 0.9
    if not ordered and not strong_sym:
        verdict = "random-like (no structure beyond chance)"
    else:
        bits = []
        if per["corr"] >= 0.5:
            bits.append(f"periodic (~{per['period']} along {per['axis']})")
        if fftp >= 20.0:
            bits.append("spectral peak")
        if strong_sym:
            axis = max(sym, key=sym.get)
            bits.append(f"{axis} symmetry")
        if abs(z) >= 3.0:
            bits.append(f"non-random neighbours (z={z:.1f})")
        verdict = "structured: " + ", ".join(bits)
    return GridReport(tuple(g.shape), round(ent, 4), round(float(g.mean()), 4),
                      per, round(fftp, 2), {k: round(v, 3) for k, v in sym.items()},
                      round(z, 2), verdict)


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Structure analysis of a binary grid")
    ap.add_argument("grid_json", nargs="?",
                    help="JSON file: a 2D 0/1 array, or {'grid': [[...]]}. Omit for demo.")
    args = ap.parse_args()

    if args.grid_json:
        data = json.loads(open(args.grid_json).read())
        grid = data["grid"] if isinstance(data, dict) else data
        print(json.dumps(asdict(analyze(np.array(grid))), indent=2, default=list))
    else:
        rng = np.random.default_rng(1)
        rand = rng.integers(0, 2, (73, 23))
        stripes = np.tile(np.array([1, 0, 0, 0]), (40, 20))[:73, :23]
        print("RANDOM  :", analyze(rand).verdict)
        print("STRIPES :", analyze(stripes).verdict)
