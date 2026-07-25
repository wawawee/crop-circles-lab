"""Crabwood / Sparsholt 2002 — spiral disc ASCII bit reader.

Published decode (Red Collie / Paul Vigay) is in forensics.encoding.
Sampling: Archimedean spiral, default **center → outward, CCW** (CD-like),
matching the published read direction.

Web-resolution Temporary Temples discs are marginal; treat BER as a resolution
floor probe, not a fresh independent decrypt.
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
    c = max(circles[0], key=lambda x: x[2])
    return int(c[0]), int(c[1]), int(c[2])


def sample_spiral_bits(
    gray: np.ndarray,
    cx: int,
    cy: int,
    r_outer: float,
    r_inner: float | None = None,
    n_bits: int = 1208,
    turns: float = 12.0,
    ccw: bool = True,
    outward: bool = True,
    theta0: float = 0.0,
) -> np.ndarray:
    """Sample n_bits along an Archimedean spiral.

    outward=True: center → rim (published Crabwood direction).
    """
    if r_inner is None:
        r_inner = r_outer * 0.12
    bits: list[float] = []
    sign = 1.0 if ccw else -1.0
    for i in range(n_bits):
        t = i / max(n_bits - 1, 1)
        if outward:
            r = r_inner * (1 - t) + r_outer * t
        else:
            r = r_outer * (1 - t) + r_inner * t
        theta = theta0 + sign * (t * turns * 2 * np.pi)
        x = int(round(cx + r * np.cos(theta)))
        y = int(round(cy + r * np.sin(theta)))
        if 0 <= x < gray.shape[1] and 0 <= y < gray.shape[0]:
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


def score_config(
    gray: np.ndarray,
    cx: int,
    cy: int,
    r: float,
    n_bits: int,
    known_rc: str,
    known_vg: str,
    turns: float,
    r_inner_frac: float,
    ccw: bool,
    outward: bool,
    theta0: float,
    invert: bool,
    msb: bool,
) -> dict:
    samples = sample_spiral_bits(
        gray,
        cx,
        cy,
        r,
        r_inner=r * r_inner_frac,
        n_bits=n_bits,
        turns=turns,
        ccw=ccw,
        outward=outward,
        theta0=theta0,
    )
    bitstr = bits_to_bool(samples)
    if invert:
        bitstr = "".join("1" if b == "0" else "0" for b in bitstr)
    text = E.bits_to_text(bitstr, msb_first=msb)
    _, ber_rc = hamming(bitstr, known_rc)
    _, ber_vg = hamming(bitstr, known_vg)
    return {
        "turns": turns,
        "r_inner_frac": r_inner_frac,
        "ccw": ccw,
        "outward": outward,
        "theta0_deg": round(np.degrees(theta0), 1),
        "invert": invert,
        "msb": msb,
        "ber_red_collie": round(ber_rc, 4),
        "ber_vigay": round(ber_vg, 4),
        "ber_best": round(min(ber_rc, ber_vg), 4),
        "text_preview": "".join(ch if 32 <= ord(ch) < 127 else "." for ch in text[:80]),
        "bits": bitstr,
    }


def analyze_disc(
    path: Path,
    n_chars: int | None = None,
    cx: int | None = None,
    cy: int | None = None,
    r: float | None = None,
    turns: float = 12.0,
    r_inner_frac: float = 0.12,
    theta0_deg: float = 0.0,
    outward: bool = True,
    ccw: bool = True,
) -> dict:
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(path)
    gray = to_grayscale(bgr)
    prep = pipeline(bgr, method="otsu", open_px=1, close_px=1)

    if cx is None or cy is None or r is None:
        circ = find_disc_circle(gray)
        if circ is None:
            h, w = gray.shape
            circ = (w // 2, h // 2, min(h, w) // 3)
            note = "hough_failed_using_center_fallback"
        else:
            note = "hough_disc"
        cx, cy, r = circ
    else:
        note = "manual_params"

    rc = E.CRABWOOD_REDCOLLIE
    vg = E.CRABWOOD_VIGAY
    if n_chars is None:
        n_chars = max(len(rc), len(vg))
    n_bits = n_chars * 8
    known_rc = E.text_to_bits(rc)[:n_bits]
    known_vg = E.text_to_bits(vg)[:n_bits]

    results = {}
    for invert in (False, True):
        for msb in (True, False):
            key = f"{'inv' if invert else 'raw'}_msb{int(msb)}"
            results[key] = score_config(
                gray,
                int(cx),
                int(cy),
                float(r),
                n_bits,
                known_rc,
                known_vg,
                turns=turns,
                r_inner_frac=r_inner_frac,
                ccw=ccw,
                outward=outward,
                theta0=np.radians(theta0_deg),
                invert=invert,
                msb=msb,
            )

    best = min(results.items(), key=lambda kv: kv[1]["ber_best"])
    # Keep full bitstring only on best (all[] would 4× bloat JSON)
    all_slim = {
        k: {kk: vv for kk, vv in v.items() if kk != "bits"} for k, v in results.items()
    }
    return {
        "path": str(path),
        "disc": {"cx": int(cx), "cy": int(cy), "r": float(r), "note": note},
        "ink_fraction": prep["ink_fraction"],
        "n_bits": n_bits,
        "spiral": {
            "turns": turns,
            "r_inner_frac": r_inner_frac,
            "theta0_deg": theta0_deg,
            "outward": outward,
            "ccw": ccw,
        },
        "best_key": best[0],
        "best": best[1],
        "all": all_slim,
        "known_rc_preview": rc[:60],
        "caveat": "Web-res discs rarely yield BER<<0.4; use as framework + high-res crop later.",
    }


def sweep_disc(
    path: Path,
    cx: int | None = None,
    cy: int | None = None,
    r: float | None = None,
    turns_range: range | None = None,
    theta_steps: int = 8,
) -> dict:
    """Parameter sweep over turns, polarity, MSB, direction, start angle."""
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(path)
    gray = to_grayscale(bgr)
    if cx is None or cy is None or r is None:
        circ = find_disc_circle(gray)
        if circ is None:
            h, w = gray.shape
            circ = (w // 2, h // 2, min(h, w) // 3)
        cx, cy, r = circ

    rc, vg = E.CRABWOOD_REDCOLLIE, E.CRABWOOD_VIGAY
    n_bits = max(len(rc), len(vg)) * 8
    known_rc = E.text_to_bits(rc)[:n_bits]
    known_vg = E.text_to_bits(vg)[:n_bits]
    if turns_range is None:
        turns_range = range(8, 21)

    trials: list[dict] = []
    for turns in turns_range:
        for r_inner_frac in (0.08, 0.12, 0.18):
            for outward in (True, False):
                for ccw in (True, False):
                    for ti in range(theta_steps):
                        theta0 = 2 * np.pi * ti / theta_steps
                        for invert in (False, True):
                            for msb in (True, False):
                                trials.append(
                                    score_config(
                                        gray,
                                        int(cx),
                                        int(cy),
                                        float(r),
                                        n_bits,
                                        known_rc,
                                        known_vg,
                                        turns=float(turns),
                                        r_inner_frac=r_inner_frac,
                                        ccw=ccw,
                                        outward=outward,
                                        theta0=theta0,
                                        invert=invert,
                                        msb=msb,
                                    )
                                )

    trials.sort(key=lambda d: d["ber_best"])
    top = trials[:25]
    best = trials[0]
    return {
        "path": str(path),
        "disc": {"cx": int(cx), "cy": int(cy), "r": float(r)},
        "n_trials": len(trials),
        "best": best,
        "top25": top,
        "ber_floor": best["ber_best"],
        "interesting": best["ber_best"] < 0.40,
        "caveat": (
            "If ber_floor ≥ 0.4 across the sweep, web-res is below the sampling Nyquist "
            "for ~1200 spiral bits — need C1 high-res disc master."
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--cx", type=int, default=None)
    ap.add_argument("--cy", type=int, default=None)
    ap.add_argument("--r", type=float, default=None)
    ap.add_argument("--turns", type=float, default=12.0)
    ap.add_argument("--r-inner", type=float, default=0.12, dest="r_inner")
    ap.add_argument("--theta0", type=float, default=0.0, help="start angle degrees")
    ap.add_argument("--inward", action="store_true", help="sample outer→center (non-default)")
    ap.add_argument("--cw", action="store_true", help="clockwise (default CCW)")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--turns-min", type=int, default=8)
    ap.add_argument("--turns-max", type=int, default=20)
    args = ap.parse_args()

    path = Path(args.image)
    if args.sweep:
        result = sweep_disc(
            path,
            cx=args.cx,
            cy=args.cy,
            r=args.r,
            turns_range=range(args.turns_min, args.turns_max + 1),
        )
    else:
        result = analyze_disc(
            path,
            cx=args.cx,
            cy=args.cy,
            r=args.r,
            turns=args.turns,
            r_inner_frac=args.r_inner,
            theta0_deg=args.theta0,
            outward=not args.inward,
            ccw=not args.cw,
        )
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)


if __name__ == "__main__":
    main()
