"""Sliding-window Shannon entropy — ported from covid19-genomic-dsp.

Works on bitstrings or grayscale image rows. Useful for spotting
low-entropy 'message' bands vs high-entropy filler.

CLI:
  python tools/signal/window_entropy.py --bits 0101... --window 32 --step 8
  python tools/signal/window_entropy.py data/images/foo.png --axis rows
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image


def shannon(seq) -> float:
    """Shannon entropy of a sequence of hashable symbols (bits or bytes)."""
    if len(seq) == 0:
        return 0.0
    # numpy path for 0/1
    if isinstance(seq, np.ndarray):
        vals, counts = np.unique(seq, return_counts=True)
        p = counts / counts.sum()
        return float(-(p * np.log2(p + 1e-15)).sum())
    counts: dict = {}
    for s in seq:
        counts[s] = counts.get(s, 0) + 1
    n = len(seq)
    h = 0.0
    for c in counts.values():
        p = c / n
        h -= p * math.log2(p)
    return h


def window_entropy_bits(bits: str, window: int = 32, step: int = 8) -> dict:
    if window < 2:
        raise ValueError("window must be >= 2")
    profiles = []
    for i in range(0, max(0, len(bits) - window + 1), step):
        chunk = bits[i : i + window]
        profiles.append({"offset": i, "entropy": round(shannon(chunk), 4)})
    ents = [p["entropy"] for p in profiles]
    return {
        "kind": "bits",
        "n_bits": len(bits),
        "window": window,
        "step": step,
        "n_windows": len(profiles),
        "entropy_mean": round(float(np.mean(ents)), 4) if ents else None,
        "entropy_min": round(float(np.min(ents)), 4) if ents else None,
        "entropy_max": round(float(np.max(ents)), 4) if ents else None,
        "low_entropy_windows": [p for p in profiles if p["entropy"] < 0.7][:20],
        "profile_sample": profiles[:: max(1, len(profiles) // 40)][:40],
    }


def window_entropy_image(path: Path, axis: str = "rows", window: int = 16, step: int = 4) -> dict:
    gray = np.asarray(Image.open(path).convert("L"), dtype=np.uint8)
    h, w = gray.shape
    profiles = []
    if axis == "rows":
        for y in range(0, max(0, h - window + 1), step):
            band = gray[y : y + window, :]
            profiles.append({"offset": y, "entropy": round(shannon(band.ravel()), 4)})
    else:
        for x in range(0, max(0, w - window + 1), step):
            band = gray[:, x : x + window]
            profiles.append({"offset": x, "entropy": round(shannon(band.ravel()), 4)})
    ents = [p["entropy"] for p in profiles]
    return {
        "kind": "image",
        "path": str(path),
        "axis": axis,
        "size": [w, h],
        "window": window,
        "step": step,
        "entropy_mean": round(float(np.mean(ents)), 4) if ents else None,
        "entropy_min": round(float(np.min(ents)), 4) if ents else None,
        "entropy_max": round(float(np.max(ents)), 4) if ents else None,
        "low_entropy_bands": sorted(profiles, key=lambda p: p["entropy"])[:10],
        "profile_sample": profiles[:: max(1, len(profiles) // 40)][:40],
        "note": "Low-entropy bands can be flat sky, captions, OR structured message panels.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", nargs="?", default=None)
    ap.add_argument("--bits", type=str, default=None)
    ap.add_argument("--window", type=int, default=32)
    ap.add_argument("--step", type=int, default=8)
    ap.add_argument("--axis", choices=["rows", "cols"], default="rows")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.bits:
        result = window_entropy_bits(args.bits.replace(" ", ""), args.window, args.step)
    elif args.image:
        result = window_entropy_image(
            Path(args.image), axis=args.axis, window=args.window, step=args.step
        )
    else:
        raise SystemExit("provide an image path or --bits")

    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)


if __name__ == "__main__":
    main()
