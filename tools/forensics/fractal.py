"""
fractal.py -- Box-counting (Minkowski-Bouligand) fractal dimension, lacunarity,
and self-validating fractal generators for crop-formation analysis.

The fractal formations (Julia Set 1996, Milk Hill Koch 1997, West Kennet 1999,
Milk Hill Galaxy 2001) are the natural targets. We measure the box-counting
dimension of a *clean binary mask* and compare it against known fractals.

Estimator note: a naive log-log fit over ALL box sizes underestimates D for a
thin rasterised curve, because the finest boxes just measure a 1-px-wide line
(slope -> 1) and the coarsest boxes saturate (whole figure in a few boxes). We
therefore fit over the most-linear contiguous window of scales (auto-selected by
best R^2), which is standard practice and recovers the true scaling regime.

Only depends on numpy (+ Pillow for the demo rasteriser). Validated in
tests/test_fractal.py against a solid square (D=2), a line (D=1), a Koch curve
(D=log4/log3=1.2619) and a Sierpinski carpet (D=log8/log3=1.8928).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

THEORETICAL = {
    "line": 1.0,
    "koch_curve": np.log(4) / np.log(3),           # 1.26186
    "sierpinski_triangle": np.log(3) / np.log(2),  # 1.58496
    "sierpinski_carpet": np.log(8) / np.log(3),    # 1.89279
    "filled_plane": 2.0,
}


@dataclass
class FractalResult:
    dimension: float
    r_squared: float
    stderr: float
    sizes: np.ndarray       # all box sizes probed (pixels)
    counts: np.ndarray      # occupied-box counts at each size
    fit_slice: tuple        # (i, j) indices of the scaling window actually fitted


def to_binary(img, invert: bool | None = None) -> np.ndarray:
    """Convert an image / array to a boolean feature mask (True = pattern 'ink').

    Thresholds at the midpoint and takes the *minority* class as the feature, so
    it works whether the pattern is dark-on-light or light-on-dark. For real
    analysis, prefer an explicit mask from preprocess.py.
    """
    a = np.asarray(img, dtype=float)
    if a.ndim == 3:
        a = a.mean(axis=2)
    thr = (a.max() + a.min()) / 2.0
    fg = a > thr
    if invert is None:
        if fg.mean() > 0.5:
            fg = ~fg
    elif invert:
        fg = ~fg
    return fg


def box_count(binary: np.ndarray):
    """Return (sizes, counts): occupied boxes at each power-of-two box size,
    from n/2 down to 2 (n = next power of two >= max image dim)."""
    b = np.asarray(binary, dtype=bool)
    n = 2 ** int(np.ceil(np.log2(max(b.shape))))
    padded = np.zeros((n, n), dtype=bool)
    padded[:b.shape[0], :b.shape[1]] = b

    sizes, counts = [], []
    size = n // 2
    while size >= 2:
        k = n // size
        blocks = padded[:k * size, :k * size].reshape(k, size, k, size)
        occupied = int(blocks.any(axis=(1, 3)).sum())
        if occupied > 0:
            sizes.append(size)
            counts.append(occupied)
        size //= 2
    return np.array(sizes, dtype=float), np.array(counts, dtype=float)


def _linfit(x, y):
    A = np.vstack([x, np.ones_like(x)]).T
    (slope, intercept), *_ = np.linalg.lstsq(A, y, rcond=None)
    yhat = slope * x + intercept
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return float(slope), float(intercept), r2, ss_res


def fractal_dimension(binary: np.ndarray, min_window: int = 4) -> FractalResult:
    """Box-counting dimension = slope of log N(eps) vs log(1/eps), fitted over the
    most-linear contiguous window of scales (best R^2, ties broken by width)."""
    sizes, counts = box_count(binary)
    if len(sizes) < min_window:
        raise ValueError("need at least %d usable scales; pattern too small/empty"
                         % min_window)
    x = np.log(1.0 / sizes)   # log(1/eps)
    y = np.log(counts)        # log N(eps)
    n = len(x)

    best = None  # ((r2_rounded, width), slope, r2, i, j, ss_res)
    for i in range(n):
        for j in range(i + min_window, n + 1):
            slope, _, r2, ssr = _linfit(x[i:j], y[i:j])
            key = (round(r2, 6), j - i)
            if best is None or key > best[0]:
                best = (key, slope, r2, i, j, ssr)
    _, slope, r2, i, j, ssr = best

    m = j - i
    denom = float(np.sqrt(np.sum((x[i:j] - x[i:j].mean()) ** 2)))
    stderr = float(np.sqrt(ssr / (m - 2)) / denom) if m > 2 and denom > 0 else float("nan")
    return FractalResult(float(slope), float(r2), stderr, sizes, counts, (i, j))


def lacunarity(binary: np.ndarray, box: int = 8) -> float:
    """Gliding-box lacunarity L = var(mass)/mean(mass)^2 + 1 (heterogeneity)."""
    from numpy.lib.stride_tricks import sliding_window_view
    b = np.asarray(binary, dtype=float)
    if box > min(b.shape):
        raise ValueError("box larger than image")
    w = sliding_window_view(b, (box, box))
    masses = w.sum(axis=(-1, -2)).ravel()
    m = masses.mean()
    return float(masses.var() / (m * m) + 1.0) if m > 0 else float("nan")


# --- Validation generators ------------------------------------------------------

def koch_points(order: int = 6) -> np.ndarray:
    """Vertices of a Koch curve (theoretical D = log4/log3 = 1.2619)."""
    pts = np.array([[0.0, 0.0], [1.0, 0.0]])
    ang = -np.pi / 3.0
    rot = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    for _ in range(order):
        new = [pts[0]]
        for i in range(len(pts) - 1):
            p0, p1 = pts[i], pts[i + 1]
            d = (p1 - p0) / 3.0
            a = p0 + d
            b = p0 + 2 * d
            peak = a + rot.dot(d)
            new.extend([a, peak, b, p1])
        pts = np.array(new)
    return pts


def rasterize_polyline(pts, size: int = 2048, pad: float = 0.05) -> np.ndarray:
    """Draw a polyline into a size x size boolean grid (aspect preserved)."""
    from PIL import Image, ImageDraw
    p = np.asarray(pts, dtype=float)
    mn, mx = p.min(axis=0), p.max(axis=0)
    span = (mx - mn).max()
    q = (p - mn) / span
    w = size * (1 - 2 * pad)
    xy = q * w + size * pad
    img = Image.new("L", (size, size), 0)
    ImageDraw.Draw(img).line([tuple(v) for v in xy], fill=255, width=1)
    return np.asarray(img) > 0


def sierpinski_carpet(order: int = 5) -> np.ndarray:
    """Sierpinski carpet (theoretical D = log8/log3 = 1.8928)."""
    block = np.ones((3, 3), bool)
    block[1, 1] = False
    c = np.ones((1, 1), bool)
    for _ in range(order):
        c = np.kron(c, block)
    return c


if __name__ == "__main__":
    print("Fractal-dimension self-check (box-counting, auto linear region):\n")
    sq = np.zeros((512, 512), bool); sq[64:448, 64:448] = True
    r = fractal_dimension(sq)
    print(f"  solid square     : D={r.dimension:.3f}  (expect ~2.000)  R2={r.r_squared:.4f}")
    ln = np.zeros((512, 512), bool); ln[256, 32:480] = True
    r = fractal_dimension(ln)
    print(f"  straight line    : D={r.dimension:.3f}  (expect ~1.000)  R2={r.r_squared:.4f}")
    kb = rasterize_polyline(koch_points(6), size=2048)
    r = fractal_dimension(kb)
    print(f"  Koch curve       : D={r.dimension:.3f}  (expect  1.262)  R2={r.r_squared:.4f}")
    sc = sierpinski_carpet(5)
    r = fractal_dimension(sc)
    print(f"  Sierpinski carpet: D={r.dimension:.3f}  (expect  1.893)  R2={r.r_squared:.4f}")
