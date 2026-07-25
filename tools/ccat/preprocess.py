"""Image conditioning BEFORE geometry / fractal / bit reading.

Order: load → (optional) perspective_correct → grayscale → binarize → morph cleanup.
Never run Hough / ratio math on a raw aerial without a mask.

B3 additions (2026-07-25): crop_stubble_mask (excess-green separation of laid vs
standing crop) and a --corners-json CLI hook for perspective_correct. Edmonton
ortho is intentionally left to local (needs hand-picked corner JSON).
"""

from __future__ import annotations

import argparse
import json
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


def crop_stubble_mask(img: np.ndarray, blur: int = 3) -> np.ndarray:
    """Separate flattened/laid crop from standing crop by the excess-green index.

    ExG = 2*G - R - B is high for green standing crop and low for tan/golden laid
    stubble. We Otsu-threshold ExG and return a boolean mask True = laid/flattened.
    Works on colour aerials; on a grayscale image it degenerates to an intensity
    split (documented limitation).
    """
    bgr = img if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    b, g, r = cv2.split(bgr.astype(np.float32))
    exg = 2.0 * g - r - b
    exg_n = cv2.normalize(exg, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    if blur and blur > 1:
        exg_n = cv2.GaussianBlur(exg_n, (blur | 1, blur | 1), 0)
    _, bw = cv2.threshold(exg_n, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    standing = bw > 0          # high ExG = green standing crop
    return ~standing           # laid / flattened = low ExG


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


def load_corners_json(path):
    """Load a 4-corner quad from JSON. Accepts {'corners': [[x,y]*4]} or a bare
    [[x,y]*4] list. Order must be TL, TR, BR, BL."""
    data = json.loads(Path(path).read_text())
    quad = data["corners"] if isinstance(data, dict) else data
    quad = np.asarray(quad, dtype=np.float32).reshape(4, 2)
    return quad


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
    ap.add_argument("--corners-json", type=Path, default=None,
                    help="JSON with 4 corners (TL,TR,BR,BL) for perspective rectification")
    ap.add_argument("--stubble", action="store_true",
                    help="also write the excess-green laid-crop mask")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    bgr = cv2.imread(args.image, cv2.IMREAD_COLOR)
    if bgr is None:
        raise SystemExit(f"cannot read {args.image}")

    src_quad = load_corners_json(args.corners_json) if args.corners_json else None
    result = pipeline(bgr, method=args.method, src_quad=src_quad)
    out = args.out or Path("outputs") / f"{Path(args.image).stem}_mask.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), (result["mask"].astype(np.uint8) * 255))
    msg = f"Wrote {out} ink_fraction={result['ink_fraction']:.4f}"

    if args.stubble:
        laid = crop_stubble_mask(result["image"])
        s_out = out.with_name(f"{out.stem}_stubble.png")
        cv2.imwrite(str(s_out), (laid.astype(np.uint8) * 255))
        msg += f"; stubble mask {s_out} laid_fraction={laid.mean():.4f}"
    print(msg)


if __name__ == "__main__":
    main()
