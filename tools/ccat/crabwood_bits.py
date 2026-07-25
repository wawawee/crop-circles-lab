"""Crabwood / Sparsholt 2002 — spiral disc ASCII bit reader.

Published decode (Red Collie / Paul Vigay) is reproduced in forensics.encoding.
This module attempts to *sample* bits from an aerial of the disc:
  polar unwrap → ring × angle bins → threshold → 8-bit ASCII.

Web-resolution Temporary Temples discs (~600px) are marginal; treat output as
hypothesis + bit-error vs known plaintext, not as a fresh independent decrypt.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

try:
    from .preprocess import pipeline, to_grayscale
except ImportError:
    from preprocess import pipeline, to_grayscale

# Import known plaintexts from forensics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "forensics"))
import encoding as E  # noqa: E402


def find_disc_circle(gray: np.ndarray) -> tuple[int, int, int] | None:
    """Largest strong circle ≈ the data disc (heuristic)."""
    blur = cv2.GaussianBlur(gray, (9, 9), 2)
    h, w = gray.shape
    circles = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min(h, w) // 4,
        param1=100,
        param2=40,
        minRadius=min(h, w) // 8,
        maxRadius=min(h, w) // 2,
    )
    if circles is None:
        return None
    # pick largest
    c = max(circles[0], key=lambda x: x[2])
    return int(c[0]), int(c[1]), int(c[2])


def sample_spiral_bits(
    gray: np.ndarray,
    cx: int,
    cy: int,
    r_outer: int,
    r_inner: float | None = None,
    n_bits: int = 1208,  # ~151 chars * 8
    ccw: bool = True,
) -> np.ndarray:
    """Sample n_bits along a log-ish spiral from outer toward center (CD-like).

    Returns float samples in [0,1] (1 = bright/flattened).
    """
    if r_inner is None:
        r_inner = r_outer * 0.15
    # Archimedean-ish: constant dθ, r decreases linearly with bit index
    bits = []
    for i in range(n_bits):
        t = i / max(n_bits - 1, 1)
        r = r_outer * (1 - t) + r_inner * t
        # several turns: ~n_bits / samples_per_turn
        turns = 12.0  # heuristic for Crabwood disc density
        theta = (1 if ccw else -1) * (t * turns * 2 * np.pi)
        x = int(round(cx + r * np.cos(theta)))
        y = int(round(cy + r * np.sin(theta)))
        if 0 <= x < gray.shape[1] and 0 <= y < gray.shape[0]:
            # local average
            y0, y1 = max(0, y - 1), min(gray.shape[0], y + 2)
            x0, x1 = max(0, x - 1), min(gray.shape[1], x + 2)
            bits.append(float(gray[y0:y1, x0:x1].mean()) / 255.0)
        else:
            bits.append(0.0)
    return np.asarray(bits, dtype=np.float32)


def bits_to_bool(samples: np.ndarray, thresh: float | None = None) -> str:
    if thresh is None:
        thresh = float(np.median(samples))
    return "".join("1" if s >= thresh else "0" for s in samples)


def hamming(a: str, b: str) -> tuple[int, float]:
    n = min(len(a), len(b))
    if n == 0:
        return 0, 1.0
    err = sum(ch1 != ch2 for ch1, ch2 in zip(a[:n], b[:n]))
    return err, err / n


def analyze_disc(path: Path, n_chars: int = 151) -> dict:
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(path)
    gray = to_grayscale(bgr)
    prep = pipeline(bgr, method="otsu", open_px=1, close_px=1)
    # use gray for sampling (more dynamic range than binary)
    circ = find_disc_circle(gray)
    if circ is None:
        h, w = gray.shape
        circ = (w // 2, h // 2, min(h, w) // 3)
        note = "hough_failed_using_center_fallback"
    else:
        note = "hough_disc"

    cx, cy, r = circ
    n_bits = n_chars * 8
    samples = sample_spiral_bits(gray, cx, cy, r, n_bits=n_bits, ccw=True)
    bitstr = bits_to_bool(samples)
    # also inverted polarity
    bitstr_inv = "".join("1" if b == "0" else "0" for b in bitstr)

    known = E.text_to_bits(E.CRABWOOD_REDCOLLIE[:n_chars])
    known_v = E.text_to_bits(E.CRABWOOD_VIGAY[:n_chars] if False else E.CRABWOOD_REDCOLLIE[:n_chars])
    # Vigay text differs — encode both full known strings truncated to n_bits
    known_rc = E.text_to_bits(E.CRABWOOD_REDCOLLIE)[:n_bits]
    known_vg = E.text_to_bits(E.CRABWOOD_VIGAY)[:n_bits]

    results = {}
    for label, bits in [("raw", bitstr), ("inv", bitstr_inv)]:
        for msb in (True, False):
            text = E.bits_to_text(bits, msb_first=msb)
            err_rc, ber_rc = hamming(bits, known_rc)
            err_vg, ber_vg = hamming(bits, known_vg)
            results[f"{label}_msb{int(msb)}"] = {
                "text_preview": "".join(ch if 32 <= ord(ch) < 127 else "." for ch in text[:80]),
                "ber_red_collie": round(ber_rc, 4),
                "ber_vigay": round(ber_vg, 4),
                "hamming_rc": err_rc,
            }

    best = min(results.items(), key=lambda kv: min(kv[1]["ber_red_collie"], kv[1]["ber_vigay"]))
    return {
        "path": str(path),
        "disc": {"cx": cx, "cy": cy, "r": r, "note": note},
        "ink_fraction": prep["ink_fraction"],
        "n_bits": n_bits,
        "best_key": best[0],
        "best": best[1],
        "all": results,
        "known_rc_preview": E.CRABWOOD_REDCOLLIE[:60],
        "caveat": "Web-res discs rarely yield BER<<0.4; use as framework + high-res crop later.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    result = analyze_disc(Path(args.image))
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)


if __name__ == "__main__":
    main()
