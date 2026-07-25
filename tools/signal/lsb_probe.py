"""LSB / bitplane probe — hunt for hidden payloads in images (TRUsteg-inspired).

Pure NumPy/Pillow — no stegano GUI dependency. Optional extract via `stegano`
if installed.

CLI:
  python tools/signal/lsb_probe.py data/images/chualar_2013_nvidia_hoax.png
  python tools/signal/lsb_probe.py path.png --extract-stegano
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bitstream_probe import analyze as analyze_bits  # noqa: E402


def _shannon01(bits: np.ndarray) -> float:
    n = bits.size
    if n == 0:
        return 0.0
    p1 = float(bits.mean())
    p0 = 1.0 - p1
    h = 0.0
    for p in (p0, p1):
        if p > 0:
            h -= p * math.log2(p)
    return h


def bitplane(channel: np.ndarray, plane: int) -> np.ndarray:
    return ((channel.astype(np.uint16) >> plane) & 1).astype(np.uint8)


def chi_square_lsb(channel: np.ndarray) -> float:
    """Simple χ²-ish score on LSB pairs (PoVs-inspired, lightweight).

    Lower ≈ more 'natural'; higher ≈ LSB looks manipulated / random-payload-like.
    Returns a normalized score in [0, ~1+] for ranking, not a p-value.
    """
    lsb = channel.ravel() & 1
    # pair adjacent pixels
    if lsb.size % 2:
        lsb = lsb[:-1]
    pairs = lsb.reshape(-1, 2)
    # count 00,01,10,11
    codes = pairs[:, 0] * 2 + pairs[:, 1]
    counts = np.bincount(codes, minlength=4).astype(float)
    expected = counts.sum() / 4.0
    if expected <= 0:
        return 0.0
    chi = float(((counts - expected) ** 2 / expected).sum())
    # 3 dof; normalize roughly by dividing by a soft scale
    return round(chi / (counts.sum() + 1e-9) * 10, 4)


def analyze_image(path: Path) -> dict:
    im = Image.open(path).convert("RGB")
    arr = np.asarray(im, dtype=np.uint8)
    h, w, _ = arr.shape
    planes = {}
    for name, ch in zip("RGB", (arr[:, :, 0], arr[:, :, 1], arr[:, :, 2])):
        bp0 = bitplane(ch, 0)
        planes[name] = {
            "lsb_entropy": round(_shannon01(bp0), 4),
            "lsb_mean": round(float(bp0.mean()), 4),
            "chi_lsb": chi_square_lsb(ch),
            "plane7_entropy": round(_shannon01(bitplane(ch, 7)), 4),
        }
    # Concatenate RGB LSBs as a bitstring sample (first 64k bits for speed)
    rgb_lsb = np.stack([bitplane(arr[:, :, i], 0) for i in range(3)], axis=-1).ravel()
    sample = "".join("1" if b else "0" for b in rgb_lsb[:65536])
    bit_metrics = analyze_bits(sample)
    # Suspicion heuristic
    mean_lsb_h = float(np.mean([planes[c]["lsb_entropy"] for c in "RGB"]))
    mean_msb_h = float(np.mean([planes[c]["plane7_entropy"] for c in "RGB"]))
    flags = []
    if mean_lsb_h > 0.99 and mean_msb_h < 0.95:
        flags.append("LSB near-max entropy while MSB quieter — classic stego/noise fingerprint.")
    if any(planes[c]["chi_lsb"] > 0.15 for c in "RGB"):
        flags.append("Elevated LSB pair χ² score on at least one channel.")
    if not flags:
        flags.append("No strong LSB flags on this sample (doesn't prove absence).")

    return {
        "path": str(path),
        "size": [w, h],
        "channels": planes,
        "rgb_lsb_bitstream_sample": {
            "n_bits_sampled": len(sample),
            "shannon_entropy": bit_metrics["shannon_entropy"],
            "bit_balance_abs": bit_metrics["bit_balance_abs"],
            "interpretation": bit_metrics["interpretation"],
        },
        "flags": flags,
        "stance": "Message-hunting heuristic only — high LSB entropy is common in compressed photos too.",
    }


def try_stegano_extract(path: Path) -> dict:
    try:
        from stegano import lsb
    except ImportError:
        return {"available": False, "error": "pip install stegano for optional extract"}
    try:
        msg = lsb.reveal(str(path))
        return {"available": True, "revealed": msg, "found": msg is not None}
    except Exception as e:  # noqa: BLE001
        return {"available": True, "found": False, "error": str(e)[:200]}


def main() -> None:
    ap = argparse.ArgumentParser(description="LSB / bitplane message probe")
    ap.add_argument("image")
    ap.add_argument("--extract-stegano", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    path = Path(args.image)
    result = analyze_image(path)
    if args.extract_stegano:
        result["stegano"] = try_stegano_extract(path)
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)


if __name__ == "__main__":
    main()
