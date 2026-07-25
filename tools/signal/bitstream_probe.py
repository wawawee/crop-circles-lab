"""Bitstream forensics — Shannon, balance, runs, LZ, autocorr, reshape, ASCII.

CLI:
  python tools/signal/bitstream_probe.py --bits 11011010...
  python tools/signal/bitstream_probe.py --file path.txt
  python tools/signal/bitstream_probe.py --demo-multiplex
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import numpy as np

# Jeremy Weeks L20–L24 (identical) — from multiplex_final_report.txt, Dec 2025
MULTIPLEX_L20 = (
    "110110100011010101100110100101101001010110100101100101100101101001100110001101011011010"
)


def parse_bits(text: str) -> str:
    t = text.strip().replace(" ", "").replace("\n", "").replace("\t", "")
    if t.lower().startswith("0b"):
        t = t[2:]
    if re.fullmatch(r"[01]+", t):
        return t
    raise ValueError("expected a bitstring of 0/1 characters")


def shannon_entropy_bits(bits: str) -> float:
    if not bits:
        return 0.0
    n = len(bits)
    h = 0.0
    for c in (bits.count("0"), bits.count("1")):
        if c:
            p = c / n
            h -= p * math.log2(p)
    return h


def bit_balance(bits: str) -> float:
    """|p1 - 0.5| — 0 ≈ perfect 50/50."""
    if not bits:
        return 1.0
    return abs(bits.count("1") / len(bits) - 0.5)


def run_density(bits: str) -> float:
    if len(bits) < 2:
        return 0.0
    return sum(a != b for a, b in zip(bits, bits[1:])) / (len(bits) - 1)


def lz76_count(s: str) -> int:
    """LZ76 phrase count (Kaspar & Schuster style)."""
    i, c, n = 0, 0, len(s)
    while i < n:
        c += 1
        max_l = 0
        for j in range(i):
            l = 0
            while i + l < n and s[j + l] == s[i + l]:
                l += 1
            if l > max_l:
                max_l = l
        i += max_l + 1
    return c


def autocorrelation(bits: str, max_lag: int = 32) -> dict:
    x = np.array([1.0 if b == "1" else -1.0 for b in bits], dtype=float)
    x = x - x.mean()
    n = len(x)
    if n < 4:
        return {"lags": [], "note": "too_short"}
    denom = float(np.dot(x, x)) or 1.0
    lags = []
    peak_lag, peak_val = 0, 0.0
    for lag in range(1, min(max_lag, n - 1) + 1):
        v = float(np.dot(x[:-lag], x[lag:])) / denom
        lags.append({"lag": lag, "corr": round(v, 4)})
        if abs(v) > abs(peak_val):
            peak_lag, peak_val = lag, v
    return {
        "peak_lag": peak_lag,
        "peak_corr": round(peak_val, 4),
        "strong_peak": abs(peak_val) > 0.3,
        "lags_top": sorted(lags, key=lambda d: abs(d["corr"]), reverse=True)[:5],
    }


def reshape_candidates(bits: str) -> list[dict]:
    n = len(bits)
    out = []
    for cols in range(2, min(64, n // 2) + 1):
        if n % cols:
            continue
        rows = n // cols
        if rows < 2:
            continue
        grid = np.array([int(b) for b in bits], dtype=float).reshape(rows, cols)
        col_h = [
            shannon_entropy_bits("".join(str(int(x)) for x in grid[:, c])) for c in range(cols)
        ]
        row_h = [
            shannon_entropy_bits("".join(str(int(x)) for x in grid[r, :])) for r in range(rows)
        ]
        out.append(
            {
                "shape": f"{rows}x{cols}",
                "rows": rows,
                "cols": cols,
                "col_entropy_std": round(float(np.std(col_h)), 4),
                "row_entropy_std": round(float(np.std(row_h)), 4),
                "mean_fill": round(float(grid.mean()), 4),
            }
        )
    out.sort(key=lambda d: d["col_entropy_std"] + d["row_entropy_std"], reverse=True)
    return out[:8]


def ascii_candidates(bits: str, msb_first: bool = True) -> dict:
    n = (len(bits) // 8) * 8
    chars = []
    for i in range(0, n, 8):
        byte = bits[i : i + 8]
        if not msb_first:
            byte = byte[::-1]
        chars.append(chr(int(byte, 2)))
    text = "".join(chars)
    printable = sum(32 <= ord(c) < 127 for c in text) / max(len(text), 1)
    preview = "".join(c if 32 <= ord(c) < 127 else "." for c in text[:80])
    return {
        "n_bytes": len(text),
        "printable_fraction": round(printable, 4),
        "looks_like_text": printable > 0.75,
        "preview": preview,
    }


def fib_primes_hits(bits: str) -> dict:
    primes = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61}
    fibs = {1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987}
    p_hits = f_hits = trials = 0
    for w in range(4, 11):
        for i in range(0, len(bits) - w + 1):
            trials += 1
            v = int(bits[i : i + w], 2)
            if v in primes:
                p_hits += 1
            if v in fibs:
                f_hits += 1
    return {
        "window_trials": trials,
        "prime_hits": p_hits,
        "fib_hits": f_hits,
        "prime_hit_rate": round(p_hits / max(trials, 1), 4),
        "note": "Anecdotal — random bits also hit small primes.",
    }


def interpret(metrics: dict) -> list[str]:
    notes = []
    h = metrics["shannon_entropy"]
    bal = metrics["bit_balance_abs"]
    if h > 0.98 and bal < 0.05:
        notes.append(
            "Near-max entropy + near-perfect balance → crypto, compression, or balanced "
            "synthetic bits (human/algorithm). Unlikely natural language."
        )
    elif h < 0.5:
        notes.append("Low entropy → bias/repetition; possible structured plaintext or bad sample.")
    if metrics.get("ascii_msb", {}).get("looks_like_text"):
        notes.append("8-bit MSB chunking looks printable — try as ASCII/UTF-8.")
    if metrics.get("autocorr", {}).get("strong_peak"):
        notes.append(
            f"Autocorr peak at lag {metrics['autocorr']['peak_lag']} → periodic/framed structure."
        )
    shapes = metrics.get("reshape_top") or []
    if shapes and shapes[0]["col_entropy_std"] > 0.15:
        notes.append(f"Best 2D reshape {shapes[0]['shape']} shows column structure — try as bitmap.")
    if not notes:
        notes.append("No strong flags; compare against a shuffled control of same length.")
    return notes


def analyze(bits: str) -> dict:
    bits = parse_bits(bits)
    lz = lz76_count(bits)
    metrics = {
        "n_bits": len(bits),
        "shannon_entropy": round(shannon_entropy_bits(bits), 4),
        "p1": round(bits.count("1") / len(bits), 4) if bits else None,
        "bit_balance_abs": round(bit_balance(bits), 4),
        "run_density": round(run_density(bits), 4),
        "lz76_phrases": lz,
        "lz76_normalized": round(lz / max(len(bits), 1), 4),
        "autocorr": autocorrelation(bits),
        "reshape_top": reshape_candidates(bits),
        "ascii_msb": ascii_candidates(bits, msb_first=True),
        "ascii_lsb": ascii_candidates(bits, msb_first=False),
        "math_curiosity": fib_primes_hits(bits),
    }
    metrics["interpretation"] = interpret(metrics)
    return metrics


def main() -> None:
    ap = argparse.ArgumentParser(description="Bitstream message-hunting probe")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--bits", type=str)
    g.add_argument("--file", type=Path)
    g.add_argument("--demo-multiplex", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.demo_multiplex:
        bits, label = MULTIPLEX_L20, "multiplex_L20_weeks"
    elif args.file:
        bits = parse_bits(args.file.read_text(encoding="utf-8", errors="replace"))
        label = str(args.file)
    else:
        bits, label = parse_bits(args.bits), "cli"

    result = {"source": label, **analyze(bits)}
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)


if __name__ == "__main__":
    main()
