"""bio_probe — DNA/RNA as bitstream (+ optional epigenetic symbols) +
optional annotation-aware per-bin shuffle control.

N1 mission (Minimax/Lab local — Hermes handed off). Landed state:
  * standard 2-bit map A/C/G/T
  * extended alphabet hook for 5mC / 5hmC / 6mA (as distinct symbols, not forced 2-bit)
  * Shannon windows (real AND shuffled) + handoff to tools/signal/bitstream_probe
  * composition-preserving shuffle (preserves GC% trivially) as the headline
    negative control -- documented in NOTES.md as the test statistic
  * small-sample assets in `data/bio/`:
      SARS_COV_2_NC_045512.2_head.fasta (4 kb head of NC_045512.2)
      HUMAN_chr22_3kb.fasta (3 kb slice of NT_187395.1)
    Both real NCBI slices, fetched on 2026-07-25; see data/bio/README.md.

N1+ mission (this extension):
  * load BED4 annotations from `data/bio/annotations/<chr>_regions.bed`
  * tag each window with a bin (coding / untranslated / intronic / intergenic)
    using the max-overlap-wins rule (max intersecting bp count)
  * mark `straddles_boundary=True` when the max-overlap feature covers
    < 90% of the window (so the analyst can filter or downweight it)
  * run the composition-preserving shuffle control WITHIN each bin:
    pool real bases from the bin -> Fisher-Yates shuffle same multiset -> compute
    windowed Shannon entropy on the shuffled pool -> delta per bin

Stance: 'structure != message'. A NEGATIVE per-bin Δ is the expected biology;
a clearly POSITIVE per-bin Δ (real packing lower entropy than the bin-matched
shuffle) would be the 'surprise' to follow up. NEVER framed as 'hidden message'.

CLI:
  python tools/bio/bio_probe.py --demo
  python tools/bio/bio_probe.py data/bio/SARS_COV_2_NC_045512.2_head.fasta \\
      --annotations data/bio/annotations/NC_045512.2_regions.bed \\
      --out outputs/bio/sars_run.json --out-md outputs/bio/sars_notes.md
  python tools/bio/bio_probe.py path/to/genome.fa \\
      --window 200 --step 50 --shuffle-seed 42 \\
      --annotations path/to/regions.bed \\
      --out ...
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter
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

# Bins used by the annotation-aware per-bin classifier.
# A BED4 row's 'type' column MUST be one of these OR fall back to 'intergenic'.
BIN_TYPES = ("coding", "untranslated", "intronic", "intergenic")

# Minimum number of windows a bin needs for a defensible Δ.
# Below this, the bin's shuffled-pool entropy has too few windows and we
# report status="too_few_windows" with a null delta.
MIN_WINDOWS_FOR_BIN_DELTA = 5

# Straddle boundary fraction: a window is flagged `straddles_boundary`
# when its max-overlap feature covers less than this fraction of the window.
STRADDLE_THRESHOLD = 0.9


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


def gc_content(seq: str) -> float:
    """GC fraction in [0, 1]. Counts only canonical A/C/G/T/U letters.
    Epigenetic symbols like 5mC, 5hmC, 6mA are EXCLUDED from BOTH the
    numerator and the denominator so this statistic isolates base
    frequency rather than methylation state. (Rationale: we test
    against a composition-preserving Fisher-Yates shuffle that holds
    letter counts fixed, so counting methylation here would silently
    couple the GC statistic to the epigenetic channel and inflate the
    negative-control delta in unexpected ways.)
    """
    seq_u = seq.upper()
    n_acgt = sum(1 for c in seq_u if c in BASE2BIT)
    if n_acgt == 0:
        return 0.0
    g_or_c = sum(1 for c in seq_u if c in BASE2BIT and c in ("G", "C"))
    return round(g_or_c / n_acgt, 4)


# --- BED4 annotation loader --------------------------------------------------

def load_annotations(path: Path) -> list[dict]:
    """Load a BED4 file. Returns list of dicts {chrom, start, end, type}.

    Lines starting with '#' and blank lines are skipped.
    Rows with the wrong column count raise ValueError with line number.
    'type' must be one of BIN_TYPES -- if not, raised here so corrupted
    annotations fail loud rather than silently falling back to 'intergenic'.

    Coordinates are 0-based, half-open (standard BED convention).
    """
    rows: list[dict] = []
    with Path(path).open() as f:
        for ln, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) != 4:
                raise ValueError(
                    f"{path}:{ln}: BED4 wants 4 tab-separated columns "
                    f"(chrom, start, end, type), got {len(cols)}: {raw!r}"
                )
            chrom, s, e, typ = cols[0], cols[1], cols[2], cols[3]
            try:
                start_i = int(s)
                end_i = int(e)
            except ValueError as exc:
                raise ValueError(
                    f"{path}:{ln}: bed coords must be integers, got {s!r}, {e!r}"
                ) from exc
            if start_i < 0 or end_i < 0:
                raise ValueError(
                    f"{path}:{ln}: bed coords must be non-negative, "
                    f"got start={start_i}, end={end_i}"
                )
            if end_i <= start_i:
                raise ValueError(
                    f"{path}:{ln}: bed row has end <= start ({start_i}, {end_i})"
                )
            if typ not in BIN_TYPES:
                raise ValueError(
                    f"{path}:{ln}: type {typ!r} not in {BIN_TYPES}"
                )
            rows.append({
                "chrom": chrom,
                "start": start_i,
                "end": end_i,
                "type": typ,
            })
    return rows


def _classify_window_bin(window_start: int, window_end: int,
                         annotations: list[dict]) -> tuple[str, int, bool]:
    """Return (bin, intersect_len, straddles_boundary) for a window.

    Rule:
      * If annotations is empty -> ('intergenic', 0, False).
      * Else, count intersecting bp with each BED row that lies on the
        SAME chromosome-strata (we treat chrom as opaque; bad chrom binned
        as intergenic with intersect_len=0 to be safe -- but for matched
        chromosomes we take max-overlap-wins).
      * The BED row with the LARGEST intersecting-base count dictates the bin.
      * If multiple rows tie on intersect_len, the row whose 'start' is
        CLOSEST to window_start wins (deterministic tiebreak).
      * straddles_boundary = (max_intersect / window_size) < STRADDLE_THRESHOLD
        when the window does intersect something; False otherwise.
    """
    wlen = max(1, window_end - window_start)
    if not annotations:
        return ("intergenic", 0, False)
    best_type = "intergenic"
    best_len = 0
    best_dist = None
    for row in annotations:
        ov_lo = max(window_start, row["start"])
        ov_hi = min(window_end, row["end"])
        if ov_hi <= ov_lo:
            continue
        ov_len = ov_hi - ov_lo
        dist = abs(row["start"] - window_start)
        if (ov_len > best_len) or (ov_len == best_len and
                                   (best_dist is None or dist < best_dist)):
            best_type = row["type"]
            best_len = ov_len
            best_dist = dist
    if best_len == 0:
        # No BED row intersected this window at all.
        return ("intergenic", 0, False)
    straddles = (best_len / wlen) < STRADDLE_THRESHOLD
    return (best_type, best_len, straddles)


# --- per-bin shuffle control ------------------------------------------------

def _window_entropy_mean_of(seq_text: str, char_window: int, step: int) -> float | None:
    """Helper that computes the same windowed-Shannon mean H that
    `analyze_sequence` uses for the whole-genome control, but applied to
    an arbitrary chunk of text. Returns None if the chunk is too short.
    """
    bits = seq_to_bits(seq_text)
    if not bits:
        return None
    bw = min(char_window * 2, max(32, len(bits) // 4))
    sw_step = max(8, step)
    res = window_entropy_bits(bits, window=bw, step=sw_step)
    return res.get("entropy_mean")


def _per_bin_analysis(seq: str, window: int, step: int,
                      annotations: list[dict] | None,
                      annotation_file: str | None,
                      shuffle_seed: int = 42) -> dict | None:
    """Run the per-bin shuffle control.

    Returns None when no annotations were provided (caller decides whether
    to include `bins` in the report).
    """
    if annotations is None:
        return None

    n_total = len(seq)
    windows_meta: list[dict] = []
    real_texts_by_bin: dict[str, list[str]] = {b: [] for b in BIN_TYPES}
    if n_total < window:
        return _wrap_bin_result({}, annotations, annotation_file)

    for w_start in range(0, n_total - window + 1, step):
        w_end = w_start + window
        bin_type, ov_len, straddles = _classify_window_bin(
            w_start, w_end, annotations
        )
        window_text = seq[w_start:w_end]
        windows_meta.append({
            "window_start": w_start,
            "window_end": w_end,
            "bin": bin_type,
            "intersect_len": ov_len,
            "straddles_boundary": straddles,
        })
        real_texts_by_bin[bin_type].append(window_text)

    per_bin: dict[str, dict] = {}
    for b in BIN_TYPES:
        texts = real_texts_by_bin[b]
        n_windows = len(texts)
        if n_windows == 0:
            continue  # bin absent from this region -- OMIT from dict
        pool = "".join(texts)
        # Real windowed entropy on the un-shuffled bin pool.
        real_mean = _window_entropy_mean_of(pool, char_window=window, step=step)
        # Shuffled pool = Fisher-Yates of the same pool (composition-preserving
        # within the bin, so the bin's letter-count pool is held fixed).
        shuf_pool = shuffle_seq(pool, seed=shuffle_seed)
        shuffled_mean = _window_entropy_mean_of(
            shuf_pool, char_window=window, step=step
        )
        status = (
            "ok" if n_windows >= MIN_WINDOWS_FOR_BIN_DELTA else "too_few_windows"
        )
        # Contract: when status == "too_few_windows", all H-related fields
        # are set to None -- we don't compute any Δ on a sub-minimum sample.
        if status == "too_few_windows":
            real_h_out: float | None = None
            shuf_h_out: float | None = None
            delta: float | None = None
        else:
            real_h_out = round(real_mean, 4) if real_mean is not None else None
            shuf_h_out = (
                round(shuffled_mean, 4) if shuffled_mean is not None else None
            )
            if real_h_out is not None and shuf_h_out is not None:
                delta = round(real_h_out - shuf_h_out, 4)
            else:
                delta = None
        per_bin[b] = {
            "n_windows": n_windows,
            "n_bases": len(pool),
            "gc_real": gc_content(pool),
            "real_window_H_mean": real_h_out,
            "shuffled_window_H_mean": shuf_h_out,
            "delta_window_H_mean": delta,
            "status": status,
            "min_windows_for_delta": MIN_WINDOWS_FOR_BIN_DELTA,
        }
    return _wrap_bin_result(per_bin, annotations, annotation_file, windows_meta)


def _wrap_bin_result(per_bin: dict[str, dict], annotations: list[dict],
                     annotation_file: str | None,
                     windows_meta: list[dict] | None = None) -> dict:
    """Format the per-bin + annotation_summary block."""
    regions_by_type: dict[str, int] = {}
    chroms: set[str] = set()
    for r in annotations:
        regions_by_type[r["type"]] = regions_by_type.get(r["type"], 0) + 1
        chroms.add(r["chrom"])
    out = {
        "annotation_summary": {
            "annotation_file": annotation_file,
            "features_parsed": len(annotations),
            "chromosomes_seen": sorted(chroms),
            "regions_by_type": regions_by_type,
        },
        "bins": per_bin,
        "bin_types": list(BIN_TYPES),
        "min_windows_for_delta": MIN_WINDOWS_FOR_BIN_DELTA,
        "rule": (
            "max-overlap-wins classifier on BED4 (0-based half-open). "
            "Per-bin shuffle control: Fisher-Yates of pooled bases within the bin, "
            "preserves the bin's composition (incl. GC%) by construction. "
            "straddles_boundary := max_intersect_len / window_size < "
            f"{STRADDLE_THRESHOLD:.2f}."
        ),
    }
    if windows_meta is not None:
        out["window_count"] = len(windows_meta)
    return out


# --- public analyze_sequence -----------------------------------------------

def analyze_sequence(seq: str, window: int = 1000, step: int = 250,
                     label: str = "", shuffle_seed: int = 42,
                     annotations: list[dict] | None = None,
                     annotation_file: str | None = None) -> dict:
    """Run the probe on `seq` and on a composition-preserving shuffle.

    The headline test statistic is
        Δ_window_mean_H = window_H_mean(REAL) - window_H_mean(SHUFFLED).

    If `annotations` is provided, the same Δ is also computed WITHIN each
    genome bin (coding / untranslated / intronic / intergenic) using the
    per-bin shuffle control. Each window is tagged with its bin via
    max-overlap on BED4.

    Returned dict has BOTH 'window_entropy_bits' (legacy, real-only) and
    'window_entropy_bits_real' + 'window_entropy_bits_shuffled' as the
    split fields the negative control compares. When annotations are
    provided, two ADDITIVE keys appear:
        * `annotation_summary` -- {annotation_file, features_parsed, ...}
        * `bins`               -- {bin_type: {n_windows, ..., delta_window_H_mean}}
    """
    bits = seq_to_bits(seq)
    shuf = shuffle_seq(seq, seed=shuffle_seed)
    shuf_bits = seq_to_bits(shuf)

    bw = min(window * 2, max(32, len(bits) // 4))
    sw = min(window * 2, max(32, len(shuf_bits) // 4))
    sw_step = max(8, step)

    win_real = window_entropy_bits(bits, window=bw, step=sw_step)
    win_shuf = window_entropy_bits(shuf_bits, window=sw, step=sw_step)

    real_mean = win_real.get("entropy_mean")
    shuf_mean = win_shuf.get("entropy_mean")
    delta_mean = (
        round(real_mean - shuf_mean, 4)
        if (real_mean is not None and shuf_mean is not None) else None
    )

    report: dict = {
        "label": label,
        "n_bases": len(seq),
        "n_bits": len(bits),
        "gc_content": gc_content(seq),
        "symbol_entropy": round(shannon_symbol(seq), 4),
        "symbol_entropy_shuffled": round(shannon_symbol(shuf), 4),
        "bitstream": analyze_bits(bits) if bits else None,
        "window_entropy_bits": win_real,
        "window_entropy_bits_real": win_real,
        "window_entropy_bits_shuffled": win_shuf,
        "epigenetic_symbols_seen": sorted({c for c in seq.upper() if c in EPIGENETIC}),
        "negative_control": {
            "rule": (
                "WHOLE-GENOME composition-preserving Fisher-Yates shuffle "
                "(preserves GC% by construction). For per-bin version, see "
                "`bins` key when annotations are supplied."
            ),
            "shuffle_seed": shuffle_seed,
            "delta_symbol_H": round(shannon_symbol(seq) - shannon_symbol(shuf), 4),
            "delta_window_H_mean": delta_mean,
            "real_window_H_mean": real_mean,
            "shuffled_window_H_mean": shuf_mean,
            "test_statistic": (
                "Δ_window_mean_H (whole-genome): negative = real < shuffled. "
                "Per-bin version uses the same statistic on pooled bin bases; "
                "biology-not-aliens framing always applies."
            ),
        },
    }

    if annotations is not None:
        report["annotation_summary"] = {
            "annotation_file": annotation_file,
            "features_parsed": len(annotations),
        }
        report["bins"] = _per_bin_analysis(
            seq, window=window, step=step,
            annotations=annotations, annotation_file=annotation_file,
            shuffle_seed=shuffle_seed,
        ).get("bins", {})
        # and keep the rule + window counts in a flat spot too
        report["per_bin_rule"] = (
            "Fisher-Yates of WHOLE-BIN pool with same (window, step); "
            "composition-preserving per bin (incl. GC%). "
            f"Bins with fewer than {MIN_WINDOWS_FOR_BIN_DELTA} windows are "
            "flagged status=too_few_windows with delta=null."
        )

    return report


# --- markdown notes ---------------------------------------------------------

def write_notes_markdown(report: dict) -> str:
    """Honest summary one-pager for the run. NO 'hidden message' framing."""
    nc = report.get("negative_control", {}) or {}
    real = report.get("window_entropy_bits_real", {}) or {}
    shuf = report.get("window_entropy_bits_shuffled", {}) or {}
    bits = report.get("bitstream", {}) or {}
    annotation = report.get("annotation_summary")
    bins = report.get("bins") or {}
    lines = [
        f"# bio_probe N1+ -- `{report.get('label', '<no-label>')}`",
        "",
        f"- n_bases: **{report.get('n_bases', '?')}**  "
        f"n_bits: **{report.get('n_bits', '?')}**  "
        f"GC%: **{report.get('gc_content', '?') * 100 if isinstance(report.get('gc_content'), (int, float)) else '?'}%**",
        f"- symbol entropy: **{report.get('symbol_entropy', '?')}**  "
        f"  (shuffled: {report.get('symbol_entropy_shuffled', '?')})",
        f"- epigenetic symbols seen: "
        f"{', '.join(report.get('epigenetic_symbols_seen', [])) or 'none'}",
        "",
        "## Windowed Shannon entropy (whole genome)",
        "",
        f"- real mean H: {real.get('entropy_mean', '?')}  "
        f"min {real.get('entropy_min', '?')}  max {real.get('entropy_max', '?')}  "
        f"n_windows={real.get('n_windows', '?')}",
        f"- shuffled mean H: "
        f"{shuf.get('entropy_mean', '?')} (composition-preserving, "
        f"seed {nc.get('shuffle_seed', '?')})",
        f"- Δ_window_mean_H (whole-genome): **{nc.get('delta_window_H_mean', '?')}**",
        "",
    ]
    if annotation:
        lines += [
            "## Annotation (BED4, max-overlap-wins classifier)",
            "",
            f"- annotation file: `{annotation.get('annotation_file', '?')}`  "
            f"features parsed: **{annotation.get('features_parsed', '?')}**",
            "",
        ]
    if bins:
        lines += ["## Per-bin shuffle control (Fisher-Yates within each bin)",
                  "",
                  f"(min windows for defensible Δ: "
                  f"{report.get('min_windows_for_delta', MIN_WINDOWS_FOR_BIN_DELTA)}; "
                  f"binned pool composition = same letter counts as real bin)",
                  "",
                  "| bin | n_windows | GC_real | real_H | shuffled_H | Δ | status |",
                  "|---|---:|---:|---:|---:|---:|---|"]
        for b in BIN_TYPES:
            row = bins.get(b)
            if row is None:
                continue
            lines.append(
                f"| {b} | {row['n_windows']} | "
                f"{row['gc_real']:.4f} | "
                f"{row['real_window_H_mean']} | "
                f"{row['shuffled_window_H_mean']} | "
                f"**{row['delta_window_H_mean']}** | {row['status']} |"
            )
        lines.append("")

    lines += [
        "## Bitstream probe (tools/signal/bitstream_probe.py)",
        "",
    ]
    if bits:
        for k in ("k_most_common_bytes", "bigram_bits_per_base",
                  "long_run_max_bits", "n_bits"):
            if k in bits:
                lines.append(f"- `{k}`: {bits[k]}")

    interpretation = [
        "",
        "## Interpretation",
        "",
        "* `Δ_window_mean_H` is the headline test statistic of this probe:",
        "  (mean window entropy of real) minus (mean window entropy of composition-preserving shuffle).",
        "* A NEGATIVE whole-genome `Δ_window_mean_H` is the expected biological signature",
        "  of real genomes: coding regions + repeat families compress regularities",
        "  that a shuffle has to invent by construction. This is biology, not a cipher.",
        "* The per-bin version splits this by coding / untranslated / intronic / intergenic",
        "  and recomputes the shuffle control WITHIN each bin (so the null respects the",
        "  bin's own letter-count pool, not the whole-genome pool). The same biology-not-aliens",
        "  framing applies: a positive per-bin Δ would be the surprise, a negative one is expected.",
        "* Bins with fewer than the configured minimum ("
        f"{MIN_WINDOWS_FOR_BIN_DELTA}) windows are reported as status=too_few_windows",
        "  rather than over-claiming on tiny samples.",
        "",
        "---",
        "",
        "*Generated by `tools/bio/bio_probe.py`. Stance: structure != signal.*",
    ]
    return "\n".join(lines + interpretation)


def demo() -> dict:
    # planted low-entropy "junk-like" run + high-entropy mix
    coding = ("ATG" + "CGT" * 40 + "TAA")
    junk = "A" * 80 + "T" * 40  # low entropy stretch
    mixed = coding + junk + "ACGT" * 30
    return {
        "demo_mixed": analyze_sequence(mixed, window=32, step=8, label="synthetic_mixed"),
        "demo_junk_only": analyze_sequence(junk, window=16, step=4, label="synthetic_low_H"),
        "stance": (
            "Scaffold only — replace with SARS-CoV-2 + human contig FASTA for N1. "
            "Pass --annotations to enable the per-bin classifier."
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="DNA/RNA bitstream probe (N1+) with optional per-bin annotation-aware shuffle control")
    ap.add_argument("fasta", nargs="?", type=Path,
                    help="path to FASTA; or pass --demo for synthetic known-answer")
    ap.add_argument("--demo", action="store_true",
                    help="synthetic known-answer only -- no FASTA needed")
    ap.add_argument("--window", type=int, default=200,
                    help="char window size; bits window is computed as 2× this (default 200 chars / 400 bits)")
    ap.add_argument("--step", type=int, default=50,
                    help="stride between windows (chars)")
    ap.add_argument("--max-bases", type=int, default=80_000,
                    help="cap input bases (avoid loading chr1 in CI)")
    ap.add_argument("--shuffle-seed", type=int, default=42,
                    help="seed for the composition-preserving (GC-percent-matched) shuffle control")
    ap.add_argument("--annotations", type=Path, default=None,
                    help="optional BED4 (0-based half-open) annotation file -- enables per-bin analysis")
    ap.add_argument("--out", type=Path, default=None, help="write JSON report here")
    ap.add_argument("--out-md", type=Path, default=None,
                    help="write a one-pager markdown notes file here")
    args = ap.parse_args()

    annotations: list[dict] | None = None
    if args.annotations is not None:
        if not args.annotations.exists():
            print(f"WARN: annotation file {args.annotations} not found -- running without per-bin",
                  file=sys.stderr)
        else:
            annotations = load_annotations(args.annotations)

    if args.demo or args.fasta is None:
        result = demo()
    else:
        seq = read_fasta(args.fasta, max_bases=args.max_bases)
        result = analyze_sequence(
            seq, window=args.window, step=args.step,
            label=str(args.fasta), shuffle_seed=args.shuffle_seed,
            annotations=annotations,
            annotation_file=str(args.annotations) if args.annotations else None,
        )

    text = json.dumps(result, indent=2)
    print(text[:2000] + ("…" if len(text) > 2000 else ""))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
        print(f"wrote {args.out}")
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(result, dict) and "demo_mixed" not in result:
            md_text = write_notes_markdown(result)
        else:
            md_text = ("# bio_probe -- DEMO MODE\n\n"
                       "The --demo output is a known-answer synthetic exercise, not a "
                       "real-sequence run. For a real run, pass a FASTA path: "
                       "`python tools/bio/bio_probe.py data/bio/<file>.fa ...`. "
                       "Add `--annotations data/bio/annotations/<file>.bed` to enable "
                       "the per-bin classifier.\n")
        args.out_md.write_text(md_text)
        print(f"wrote {args.out_md}")


if __name__ == "__main__":
    main()
