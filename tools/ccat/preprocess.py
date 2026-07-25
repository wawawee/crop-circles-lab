"""Image conditioning BEFORE geometry / fractal / bit reading.

Order: load → (optional) perspective_correct → grayscale → binarize → morph cleanup.
Never run Hough / ratio math on a raw aerial without a mask.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def to_grayscale(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def binarize(img: np.ndarray, method: str = "otsu", block_size: int = 51, C: int = 5) -> np.ndarray:
    """Return boolean mask True = flattened / 'ink' (minority class preference)."""
    gray = to_grayscale(img)
    if method == "otsu":
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif method == "adaptive":
        bw = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size | 1, C
        )
    else:
        raise ValueError(f"unknown method: {method}")

    fg = bw > 0
    # Prefer minority as feature (works for light stubble on dark crop and reverse)
    if fg.mean() > 0.5:
        fg = ~fg
    return fg


def morphological_cleanup(mask: np.ndarray, open_px: int = 2, close_px: int = 2) -> np.ndarray:
    out = mask.astype(np.uint8) * 255
    if open_px > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_px * 2 + 1, open_px * 2 + 1))
        out = cv2.morphologyEx(out, cv2.MORPH_OPEN, k)
    if close_px > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_px * 2 + 1, close_px * 2 + 1))
        out = cv2.morphologyEx(out, cv2.MORPH_CLOSE, k)
    return out > 0


def perspective_correct(
    img: np.ndarray,
    src_quad: np.ndarray,
    out_size: tuple[int, int] = (1024, 1024),
) -> np.ndarray:
    """Rectify oblique aerial via homography. src_quad: 4x2 float points (TL,TR,BR,BL)."""
    src = np.asarray(src_quad, dtype=np.float32).reshape(4, 2)
    w, h = out_size
    dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, M, (w, h), flags=cv2.INTER_LINEAR)


def pipeline(
    img: np.ndarray,
    method: str = "otsu",
    open_px: int = 2,
    close_px: int = 2,
    src_quad: np.ndarray | None = None,
    out_size: tuple[int, int] = (1024, 1024),
) -> dict:
    work = img
    if src_quad is not None:
        work = perspective_correct(work, src_quad, out_size=out_size)
    gray = to_grayscale(work)
    raw_mask = binarize(gray, method=method)
    mask = morphological_cleanup(raw_mask, open_px=open_px, close_px=close_px)
    return {
        "image": work,
        "gray": gray,
        "mask_raw": raw_mask,
        "mask": mask,
        "ink_fraction": float(mask.mean()),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Preprocess aerial → binary mask")
    ap.add_argument("image")
    ap.add_argument("--method", choices=["otsu", "adaptive"], default="otsu")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    bgr = cv2.imread(args.image, cv2.IMREAD_COLOR)
    if bgr is None:
        raise SystemExit(f"cannot read {args.image}")
    result = pipeline(bgr, method=args.method)
    out = args.out or Path("outputs") / f"{Path(args.image).stem}_mask.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), (result["mask"].astype(np.uint8) * 255))
    print(f"Wrote {out} ink_fraction={result['ink_fraction']:.4f}")


if __name__ == "__main__":
    main()
