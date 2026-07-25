"""Chilbolton 2001 'Arecibo reply' — sample a 23×73 bit grid from the aerial.

Compares recovered bitmap structure to the known Arecibo layout (semiprime 23×73)
and reports per-block differences documented in forensics.encoding (Si, helix, height).
Full independent re-decode needs a clean orthorectified crop of the message panel.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

try:
    from .preprocess import to_grayscale, pipeline
except ImportError:
    from preprocess import to_grayscale, pipeline

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "forensics"))
import encoding as E  # noqa: E402


ROWS, COLS = E.ARECIBO_ROWS, E.ARECIBO_COLS  # 73, 23


def auto_message_bbox(gray: np.ndarray) -> tuple[int, int, int, int]:
    """Heuristic: tall bright rectangle = message panel (works on TT overheads)."""
    h, w = gray.shape
    # focus on lower/central bright structures via Otsu mask
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # message is often darker cells on lighter — try both
    for invert in (False, True):
        m = (bw == 0) if invert else (bw > 0)
        ys, xs = np.where(m)
        if len(xs) < 100:
            continue
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        # prefer portrait-ish boxes (height > width) matching 73:23 ≈ 3.17
        bh, bw_ = y1 - y0, x1 - x0
        if bh > bw_ * 1.5 and bh > h * 0.25:
            return x0, y0, x1, y1
    # fallback: central portrait crop
    return w // 3, h // 10, 2 * w // 3, 9 * h // 10


def sample_grid(gray: np.ndarray, bbox: tuple[int, int, int, int], rows: int = ROWS, cols: int = COLS) -> np.ndarray:
    x0, y0, x1, y1 = bbox
    crop = gray[y0:y1, x0:x1]
    ch, cw = crop.shape
    grid = np.zeros((rows, cols), dtype=np.float32)
    for r in range(rows):
        for c in range(cols):
            # cell centers
            cy = int((r + 0.5) * ch / rows)
            cx = int((c + 0.5) * cw / cols)
            y_a, y_b = max(0, cy - 1), min(ch, cy + 2)
            x_a, x_b = max(0, cx - 1), min(cw, cx + 2)
            grid[r, c] = float(crop[y_a:y_b, x_a:x_b].mean()) / 255.0
    return grid


def binarize_grid(grid: np.ndarray) -> np.ndarray:
    thr = float(np.median(grid))
    return (grid >= thr).astype(np.uint8)


def row_occupancy(bits: np.ndarray) -> list[float]:
    return [float(row.mean()) for row in bits]


def load_bbox(path: Path | None) -> tuple[int, int, int, int] | None:
    """Load {x0,y0,x1,y1} or {bbox:[x0,y0,x1,y1]} from JSON."""
    if path is None or not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if "bbox" in data:
        x0, y0, x1, y1 = data["bbox"]
    else:
        x0, y0, x1, y1 = data["x0"], data["y0"], data["x1"], data["y1"]
    return int(x0), int(y0), int(x1), int(y1)


def bits_to_image(bits: np.ndarray, scale: int = 8) -> np.ndarray:
    """Render 73×23 bitmap as a readable PNG (white=1)."""
    img = (bits.astype(np.uint8) * 255)
    return cv2.resize(img, (bits.shape[1] * scale, bits.shape[0] * scale), interpolation=cv2.INTER_NEAREST)


def analyze(path: Path, bbox: tuple[int, int, int, int] | None = None) -> dict:
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(path)
    gray = to_grayscale(bgr)
    bbox_src = "manual" if bbox is not None else "auto"
    if bbox is None:
        bbox = auto_message_bbox(gray)
    grid = sample_grid(gray, bbox)
    bits = binarize_grid(grid)
    bits_inv = 1 - bits

    # Structural checks (independent of content)
    checks = {
        "shape": list(bits.shape),
        "expected": [ROWS, COLS],
        "semiprime_ok": ROWS * COLS == E.ARECIBO_BITS,
        "fill_fraction": float(bits.mean()),
        "fill_fraction_inv": float(bits_inv.mean()),
        "row_occupancy_std": float(np.std(row_occupancy(bits))),
    }

    # Encode known Chilbolton diffs as metadata (content-level, not from pixels)
    ch = E.verify_chilbolton_reply()
    return {
        "path": str(path),
        "bbox_xyxy": list(bbox),
        "bbox_source": bbox_src,
        "grid_checks": checks,
        "bits": bits.tolist(),
        "bits_inv": bits_inv.tolist(),
        "published_reply_diff": {
            "silicon": ch["silicon_atomic_number"],
            "helix": ch["helix_change"],
            "height_cm_original": round(ch["height_original"]["cm"], 1),
            "height_cm_reply": round(ch["height_reply"]["cm"], 1),
        },
        "caveat": "Low-res TT panel; cell sampling is nearest-neighbor — treat as structural probe vs published diffs.",
        "bits_preview_top5_rows": bits[:5].tolist(),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--bbox-json", type=Path, default=None, help="manual {x0,y0,x1,y1}")
    ap.add_argument("--save-overlay", type=Path, default=None)
    ap.add_argument("--save-bits-png", type=Path, default=None)
    args = ap.parse_args()
    path = Path(args.image)
    bbox = load_bbox(args.bbox_json)
    result = analyze(path, bbox=bbox)
    print(json.dumps({k: v for k, v in result.items() if k not in ("bits", "bits_inv")}, indent=2))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2))
    if args.save_overlay:
        bgr = cv2.imread(str(path))
        x0, y0, x1, y1 = result["bbox_xyxy"]
        cv2.rectangle(bgr, (x0, y0), (x1, y1), (0, 255, 0), 2)
        args.save_overlay.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(args.save_overlay), bgr)
    if args.save_bits_png:
        bits = np.asarray(result["bits"], dtype=np.uint8)
        args.save_bits_png.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(args.save_bits_png), bits_to_image(bits))
        inv_path = args.save_bits_png.with_name(args.save_bits_png.stem + "_inv" + args.save_bits_png.suffix)
        cv2.imwrite(str(inv_path), bits_to_image(1 - bits))


if __name__ == "__main__":
    main()
