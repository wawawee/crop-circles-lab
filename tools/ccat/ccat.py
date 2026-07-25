"""Crop Circle Analysis Toolkit (CCAT)

Local-first geometry / fractal / metadata probes for aerial crop-circle photos.
Designed for the TIN-STUDY foil-hat lab — not for claiming aliens (Hecklefish sighs).
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image
from PIL.ExifTags import TAGS


@dataclass
class AnalysisResult:
    path: str
    width: int
    height: int
    edge_pixel_ratio: float
    circles_detected: int
    lines_detected: int
    mean_intensity: float
    intensity_std: float
    fractal_dimension: float | None
    symmetry: dict[str, float] = field(default_factory=dict)
    exif: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_bgr(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return img


def extract_exif(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        with Image.open(path) as im:
            raw = im._getexif() or {}
            for tag_id, value in raw.items():
                name = TAGS.get(tag_id, str(tag_id))
                if isinstance(value, bytes):
                    continue
                out[name] = str(value)[:200]
    except Exception as exc:  # noqa: BLE001 — keep batch resilient
        out["error"] = str(exc)
    return out


def edge_ratio(gray: np.ndarray) -> tuple[float, np.ndarray]:
    edges = cv2.Canny(gray, 80, 180)
    ratio = float(np.count_nonzero(edges)) / float(edges.size)
    return ratio, edges


def detect_circles(gray: np.ndarray, return_array: bool = False):
    """Conservative Hough circle count — tuned to avoid wheat-texture false positives.

    Still approximate: verify against claimed circle counts (e.g. Julia Set = 151).
    """
    blur = cv2.GaussianBlur(gray, (9, 9), 2.0)
    h, w = gray.shape
    min_r = max(6, min(h, w) // 60)
    max_r = max(min_r + 1, min(h, w) // 6)
    circles = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(min_r * 1.5, 10),
        param1=120,
        param2=40,
        minRadius=min_r,
        maxRadius=max_r,
    )
    if circles is None:
        return (None, 0) if return_array else 0
    count = int(circles.shape[1])
    return (circles, count) if return_array else count


def detect_lines(edges: np.ndarray) -> int:
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=60,
        minLineLength=max(20, edges.shape[1] // 40),
        maxLineGap=8,
    )
    return 0 if lines is None else int(len(lines))


def box_counting_dimension(edges: np.ndarray, scales: int = 8) -> float | None:
    """Estimate fractal dimension of a binary edge image via box-counting."""
    binary = (edges > 0).astype(np.uint8)
    h, w = binary.shape
    size = min(h, w)
    if size < 32:
        return None

    # Crop to square for cleaner scaling
    binary = binary[:size, :size]
    ns: list[float] = []
    ss: list[float] = []
    for i in range(scales):
        s = size // (2 ** (i + 1))
        if s < 2:
            break
        # Downsample by block max
        cropped = binary[: (size // s) * s, : (size // s) * s]
        reshaped = cropped.reshape(size // s, s, size // s, s)
        boxes = reshaped.max(axis=(1, 3))
        count = int(np.count_nonzero(boxes))
        if count == 0:
            continue
        ns.append(math.log(count))
        ss.append(math.log(1.0 / s))

    if len(ns) < 3:
        return None
    coeffs = np.polyfit(ss, ns, 1)
    return float(coeffs[0])


def rotational_symmetry_score(gray: np.ndarray, folds: int) -> float:
    """0–1 score: how similar image is to itself after 360/folds rotation."""
    h, w = gray.shape
    side = min(h, w)
    crop = gray[(h - side) // 2 : (h + side) // 2, (w - side) // 2 : (w + side) // 2]
    crop = cv2.resize(crop, (256, 256), interpolation=cv2.INTER_AREA)
    angle = 360.0 / folds
    M = cv2.getRotationMatrix2D((128, 128), angle, 1.0)
    rotated = cv2.warpAffine(crop, M, (256, 256), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    # Mask out corners that rotate out of frame
    mask = np.ones_like(crop, dtype=np.uint8) * 255
    mask_r = cv2.warpAffine(mask, M, (256, 256), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT)
    valid = mask_r > 0
    if not np.any(valid):
        return 0.0
    a = crop[valid].astype(np.float32)
    b = rotated[valid].astype(np.float32)
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8
    cos = float(np.dot(a, b) / denom)
    return max(0.0, min(1.0, (cos + 1.0) / 2.0))


def mirror_symmetry_score(gray: np.ndarray) -> float:
    h, w = gray.shape
    side = min(h, w)
    crop = gray[(h - side) // 2 : (h + side) // 2, (w - side) // 2 : (w + side) // 2]
    crop = cv2.resize(crop, (256, 256), interpolation=cv2.INTER_AREA)
    flipped = cv2.flip(crop, 1)
    a = crop.astype(np.float32).ravel()
    b = flipped.astype(np.float32).ravel()
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8
    cos = float(np.dot(a, b) / denom)
    return max(0.0, min(1.0, (cos + 1.0) / 2.0))


def analyze_image(path: Path, save_debug: Path | None = None) -> AnalysisResult:
    bgr = load_bgr(path)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    ratio, edges = edge_ratio(gray)
    circles = detect_circles(gray)
    lines = detect_lines(edges)
    fractal = box_counting_dimension(edges)
    symmetry = {
        f"rot_{k}": rotational_symmetry_score(gray, k) for k in (2, 3, 4, 5, 6, 8)
    }
    symmetry["mirror"] = mirror_symmetry_score(gray)

    notes: list[str] = []
    if circles > 80:
        notes.append("very_high_circle_count")
    if fractal is not None and fractal > 1.55:
        notes.append("high_fractal_dimension")
    if max(symmetry[f"rot_{k}"] for k in (2, 3, 4, 5, 6, 8)) > 0.85:
        notes.append("strong_rotational_symmetry")

    if save_debug is not None:
        save_debug.mkdir(parents=True, exist_ok=True)
        overlay = bgr.copy()
        circs, _ = detect_circles(gray, return_array=True)
        if circs is not None:
            for c in np.round(circs[0]).astype(int):
                cv2.circle(overlay, (c[0], c[1]), c[2], (0, 255, 0), 1)
        cv2.imwrite(str(save_debug / f"{path.stem}_edges.png"), edges)
        cv2.imwrite(str(save_debug / f"{path.stem}_circles.png"), overlay)

    return AnalysisResult(
        path=str(path),
        width=w,
        height=h,
        edge_pixel_ratio=round(ratio, 5),
        circles_detected=circles,
        lines_detected=lines,
        mean_intensity=round(float(np.mean(gray)), 2),
        intensity_std=round(float(np.std(gray)), 2),
        fractal_dimension=None if fractal is None else round(fractal, 4),
        symmetry={k: round(v, 4) for k, v in symmetry.items()},
        exif=extract_exif(path),
        notes=notes,
    )


def batch_analyze(image_dir: Path, pattern: str = "*", out_json: Path | None = None, debug_dir: Path | None = None) -> list[dict]:
    exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}
    paths = sorted(p for p in image_dir.glob(pattern) if p.suffix.lower() in exts)
    results = []
    for path in paths:
        try:
            res = analyze_image(path, save_debug=debug_dir)
            results.append(res.to_dict())
            print(f"✓ {path.name}: circles={res.circles_detected} fractal={res.fractal_dimension} edge={res.edge_pixel_ratio}")
        except Exception as exc:  # noqa: BLE001
            print(f"✗ {path.name}: {exc}")
            results.append({"path": str(path), "error": str(exc)})
    if out_json:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(results, indent=2))
        print(f"Wrote {out_json}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Crop Circle Analysis Toolkit")
    parser.add_argument("image", nargs="?", help="Single image path")
    parser.add_argument("--batch", type=Path, help="Directory of images")
    parser.add_argument("--out", type=Path, default=Path("outputs/analysis.json"))
    parser.add_argument("--debug", type=Path, default=None, help="Write edge/circle overlays")
    args = parser.parse_args()

    if args.batch:
        batch_analyze(args.batch, out_json=args.out, debug_dir=args.debug)
    elif args.image:
        res = analyze_image(Path(args.image), save_debug=args.debug)
        print(json.dumps(res.to_dict(), indent=2))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(res.to_dict(), indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
