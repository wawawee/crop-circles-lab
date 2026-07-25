"""Synthetic Julia-set generator + optional fit helpers for crop-circle comparison."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def julia_set(
    c: complex = -0.8 + 0.156j,
    width: int = 800,
    height: int = 600,
    x_range: tuple[float, float] = (-1.6, 1.6),
    y_range: tuple[float, float] = (-1.2, 1.2),
    max_iter: int = 256,
) -> np.ndarray:
    """Return uint8 grayscale Julia set image (escape-time)."""
    xs = np.linspace(x_range[0], x_range[1], width)
    ys = np.linspace(y_range[0], y_range[1], height)
    X, Y = np.meshgrid(xs, ys)
    Z = X + 1j * Y
    img = np.zeros(Z.shape, dtype=np.float32)
    mask = np.ones(Z.shape, dtype=bool)
    for i in range(max_iter):
        Z[mask] = Z[mask] ** 2 + c
        escaped = np.abs(Z) > 2
        newly = escaped & mask
        img[newly] = i
        mask &= ~escaped
        if not mask.any():
            break
    img[mask] = max_iter
    img = 255 * (1 - img / max_iter)
    return img.astype(np.uint8)


# Classic "dragon" / spiral-ish parameters often compared to crop Julias
PRESETS = {
    "classic": -0.8 + 0.156j,
    "spiral": -0.74543 + 0.11301j,
    "rabbit": -0.123 + 0.745j,
    "dendrite": -0.75 + 0.11j,
    "san_marco": -0.75 + 0j,
}


def save_preset(name: str, out: Path, **kwargs) -> Path:
    c = PRESETS[name]
    arr = julia_set(c=c, **kwargs)
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr, mode="L").save(out)
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--preset", choices=list(PRESETS), default="spiral")
    p.add_argument("--out", type=Path, default=Path("data/images/synthetic_julia_spiral.png"))
    p.add_argument("--width", type=int, default=900)
    p.add_argument("--height", type=int, default=600)
    args = p.parse_args()
    path = save_preset(args.preset, args.out, width=args.width, height=args.height)
    print(f"Wrote {path} (c={PRESETS[args.preset]})")


if __name__ == "__main__":
    main()
