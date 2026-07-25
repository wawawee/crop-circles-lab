"""bio_probe — DNA/RNA as bitstream (+ optional epigenetic symbols).

N1 mission (Hyper owns full FASTA runs). This scaffold:
  * standard 2-bit map A/C/G/T
  * extended alphabet hook for 5mC / 5hmC / 6mA (as distinct symbols, not forced 2-bit)
  * Shannon windows + handoff to tools/signal/bitstream_probe
  * known-answer + shuffle negative control on a tiny synthetic sequence

CLI:
  python tools/bio/bio_probe.py --demo
  python tools/bio/bio_probe.py path/to/genome.fa --window 1000 --out outputs/bio/run.json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "signal"))

from bitstream_probe import analyze as analyze_bits  # noqa: E402
from window_entropy import window_entropy_bits  # noqa: E402

# IUPAC-ish + epigenetic extensions used as *symbols* (not all 2-bit packable)
BASE2BIT = {"A": "00", "C": "01", "G": "10", "T": "11", "U": "11"}
EPIGENETIC = {
    "M": "5mC",   # 5-methylcytosine
    "H": "5hmC",  # 5-hydroxymethylcytosine
    "6": "6mA",   # N6-methyladenine (symbol '6' in our toy alphabet)
}


def seq_to_bits(seq: str, drop_unknown: bool = True) -> str:
    bits = []
    for ch in seq.upper():
        if ch in " \n\r\t":
            continue
        if ch in BASE2BIT:
            bits.append(BASE2BIT[ch])
        elif ch in EPIGENETIC:
            # epigenetic marks: keep as separate 3-bit tags so they aren't collapsed into C/A
            bits.append({"M": "100", "H": "101", "6": "110"}[ch])
        elif not drop_unknown:
            raise ValueError(f"unknown base {ch}")
    return "".join(bits)


def shannon_symbol(seq: str) -> float:
    seq = "".join(c for c in seq.upper() if c.isalpha() or c in EPIGENETIC)
    if not seq:
        return 0.0
    from collections import Counter
    c = Counter(seq)
    n = len(seq)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def shuffle_seq(seq: str, seed: int = 0) -> str:
    chars = list(seq.upper())
    rng = random.Random(seed)
    rng.shuffle(chars)
    return "".join(chars)


def read_fasta(path: Path, max_bases: int | None = None) -> str:
    seq = []
    n = 0
    with path.open() as f:
        for line in f:
            if line.startswith(">"):
                continue
            chunk = "".join(ch for ch in line.strip() if ch.isalpha())
            seq.append(chunk)
            n += len(chunk)
            if max_bases and n >= max_bases:
                break
    s = "".join(seq)
    return s[:max_bases] if max_bases else s


def analyze_sequence(seq: str, window: int = 1000, step: int = 250, label: str = "") -> dict:
    bits = seq_to_bits(seq)
    win = window_entropy_bits(bits, window=min(window * 2, max(32, len(bits) // 4)), step=max(8, step))
    # window_entropy_bits uses bit windows; also report base-symbol entropy
    shuf = shuffle_seq(seq, seed=42)
    return {
        "label": label,
        "n_bases": len(seq),
        "n_bits": len(bits),
        "symbol_entropy": round(shannon_symbol(seq), 4),
        "symbol_entropy_shuffled": round(shannon_symbol(shuf), 4),
        "bitstream": analyze_bits(bits) if bits else None,
        "window_entropy_bits": win,
        "epigenetic_symbols_seen": sorted({c for c in seq.upper() if c in EPIGENETIC}),
        "negative_control": {
            "rule": "shuffled same composition must not look more structured than real seq",
            "delta_symbol_H": round(shannon_symbol(seq) - shannon_symbol(shuf), 4),
            "note": "For real genomes, compare coding vs intergenic windows vs shuffle (Hyper).",
        },
    }


def demo() -> dict:
    # planted low-entropy "junk-like" run + high-entropy mix
    coding = ("ATG" + "CGT" * 40 + "TAA")
    junk = "A" * 80 + "T" * 40  # low entropy stretch
    mixed = coding + junk + "ACGT" * 30
    return {
        "demo_mixed": analyze_sequence(mixed, window=32, step=8, label="synthetic_mixed"),
        "demo_junk_only": analyze_sequence(junk, window=16, step=4, label="synthetic_low_H"),
        "stance": "Scaffold only — replace with SARS-CoV-2 + human contig FASTA for N1.",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="DNA/RNA bitstream probe (N1 scaffold)")
    ap.add_argument("fasta", nargs="?", type=Path)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--window", type=int, default=1000)
    ap.add_argument("--step", type=int, default=250)
    ap.add_argument("--max-bases", type=int, default=500_000)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.demo or args.fasta is None:
        result = demo()
    else:
        seq = read_fasta(args.fasta, max_bases=args.max_bases)
        result = analyze_sequence(seq, window=args.window, step=args.step, label=str(args.fasta))

    text = json.dumps(result, indent=2)
    print(text[:2000] + ("…" if len(text) > 2000 else ""))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
