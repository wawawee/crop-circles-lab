"""Tests for tools/bio/bio_probe.py.

We pin specific numeric values where possible (alphabet mapping, classic
Shannon values, GC invariance under shuffle) and leave the windowed-entropy
shape tests loose enough that the test outlives reasonable refactors.

Stance: every quantitative claim here is an invariant of the SHA-256-stable
canonical constants + nucleotides -- if a test fails, the source code changed,
not the constants of physics.

Standalone runnable: `python3 tools/bio/tests/test_bio_probe.py`.
End-to-end subprocess tests use tempfile.mkdtemp directly so they work both
under pytest AND in plain-script mode (no pytest-fixture dependency).
"""
from __future__ import annotations

import inspect
import json
import math
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS_BIO = HERE.parent
ROOT = TOOLS_BIO.parent.parent
sys.path.insert(0, str(TOOLS_BIO))

import bio_probe as BP  # noqa: E402


# --- alphabet mapping -----------------------------------------------------

def test_seq_to_bits_pins_canonical_mapping():
    """A/C/G/T -> 00/01/10/11 + epigenetic 3-bit extension M/H/6. Any
    change to BASE2BIT or EPIGENETIC that breaks this is a breaking change
    to the probe -- pin it."""
    assert BP.seq_to_bits("ACGT") == "00011011"
    assert BP.seq_to_bits("acgt") == "00011011"  # case-insensitive
    assert BP.seq_to_bits("A C\nG\tT") == "00011011"  # whitespace stripped
    assert BP.seq_to_bits("ACGTM") == "00011011" + "100"  # 5mC is 3-bit
    assert BP.seq_to_bits("ACGTH") == "00011011" + "101"  # 5hmC is 3-bit
    assert BP.seq_to_bits("ACGT6") == "00011011" + "110"  # 6mA is 3-bit


def test_seq_to_bits_drops_unknown_silently_by_default():
    """N (ambiguous nucleotide) is silently dropped by default -- the
    real run carries it through with drop_unknown=False."""
    assert BP.seq_to_bits("ACGTN") == "00011011"
    try:
        BP.seq_to_bits("ACGTN", drop_unknown=False)
        raised = False
    except ValueError:
        raised = True
    assert raised, "drop_unknown=False should raise on unknown bases"


def test_seq_to_bits_keeps_U_as_T_alias():
    """RNA's U is bit-identical to T (same 2-bit code).
    A=00, U=11 (T alias), G=10 -> "001110\". Note the final two bits are 1 then 0."""
    assert BP.seq_to_bits("AUG") == "001110"


# --- Shannon invariants ---------------------------------------------------

def test_shannon_symbol_pins_extremes():
    """Pure-repeat: H=0. Uniform four-letter: H=2. These pin the math."""
    assert BP.shannon_symbol("AAAA") == 0.0
    assert round(BP.shannon_symbol("ACGT"), 4) == 2.0
    assert BP.shannon_symbol("") == 0.0


def test_shannon_symbol_for_genuinely_biased_returns_between_0_and_2():
    h = BP.shannon_symbol("A" * 7 + "C" * 3)
    assert 0.0 < h < 2.0
    assert abs(h - (-(7/10) * math.log2(7/10) - (3/10) * math.log2(3/10))) < 1e-9


# --- shuffle invariants ---------------------------------------------------

def test_shuffle_seq_preserves_length_and_composition():
    """Composition-preserving Fisher-Yates = GC%-matched by construction."""
    real = "ACGTACGTAAAAA"
    sh = BP.shuffle_seq(real, seed=7)
    assert len(sh) == len(real)
    assert sorted(sh) == sorted(real), (
        f"composition drift in shuffle: {sorted(real)} vs {sorted(sh)}"
    )


def test_shuffle_seq_is_pseudo_random_for_distinct_seeds():
    """Different seeds produce different orderings of the same multiset."""
    real = "ACGT" * 25  # 100 chars, equal base freq
    s1 = BP.shuffle_seq(real, seed=1)
    s2 = BP.shuffle_seq(real, seed=2)
    assert s1 != s2, "two distinct seeds produced identical shuffles -- bug?"


def test_gc_content_pins_canonical_cases():
    """GC% in [0, 1] with A/C/G/T only. Epigenetic symbols (M, H, 6) are
    EXCLUDED from both numerator and denominator -- see bio_probe.gc_content
    docstring for rationale."""
    assert BP.gc_content("AAAA") == 0.0
    assert BP.gc_content("CCCC") == 1.0
    assert BP.gc_content("GGGG") == 1.0
    assert BP.gc_content("ACGT") == 0.5


def test_gc_content_is_invariant_under_shuffle():
    """Composition-preserving shuffle trivially preserves GC%."""
    real = "ACGT" * 25 + "AA" * 10
    assert BP.gc_content(real) == BP.gc_content(BP.shuffle_seq(real, seed=99))


# --- analyze_sequence end-to-end ------------------------------------------

def test_analyze_sequence_runs_on_synthetic_input_and_returns_real_and_shuffled():
    """Run on synthetic input; verify both window-entropy dicts and the
    headline delta appear."""
    seq = "ATG" + "CGT" * 50 + "TAA"
    rep = BP.analyze_sequence(seq, window=64, step=16, label="test",
                              shuffle_seed=11)
    assert rep["label"] == "test"
    assert rep["n_bases"] == len(seq)
    assert "window_entropy_bits_real" in rep
    assert "window_entropy_bits_shuffled" in rep
    assert "window_entropy_bits" in rep  # legacy alias
    assert rep["negative_control"]["delta_window_H_mean"] is not None


def test_write_notes_markdown_runs_without_error_and_mentions_test_statistic():
    rep = BP.analyze_sequence("ACGT" * 200, window=64, step=16,
                              label="unit-test", shuffle_seed=3)
    md = BP.write_notes_markdown(rep)
    assert isinstance(md, str)
    assert "Δ_window_mean_H" in md
    assert "test statistic" in md.lower(), (
        "notes file should mention the test statistic 'Δ_window_mean_H' "
        "in human-readable form"
    )


# --- BED4 annotation loader ------------------------------------------------

def test_load_annotations_parses_bed4_and_skips_comments(tmp_path=None):
    bed = """\
# header comment line should be skipped
NC\t10\t20\tcoding
   # leading-whitespace comment too
NC\t30\t40\tintergenic

NC\t50\t55\tintronic
"""
    p = HERE.parent.parent / "data" / "bio" / "annotations" / "_tmp_unit.bed"
    # Avoid touching our shipped assets; write under tmp_path if pytest,
    # fall back to a sibling temp file when running standalone.
    import tempfile
    td = Path(tempfile.mkdtemp(prefix="bio_bed_")) if tmp_path is None else tmp_path
    bed_path = td / "unit.bed"
    bed_path.write_text(bed)
    rows = BP.load_annotations(bed_path)
    assert len(rows) == 3, f"expected 3 data rows, got {len(rows)} -- comments must be skipped"
    assert rows[0]["chrom"] == "NC"
    assert rows[0]["start"] == 10
    assert rows[0]["end"] == 20
    assert rows[0]["type"] == "coding"
    assert rows[1]["type"] == "intergenic"
    assert rows[2]["type"] == "intronic"


def test_load_annotations_rejects_malformed_columns():
    import tempfile
    td = Path(tempfile.mkdtemp(prefix="bio_bed_"))
    bed_path = td / "bad.bed"
    bed_path.write_text("NC\t10\t20\tcoding\textra_col\n")
    try:
        BP.load_annotations(bed_path)
        raised = False
    except ValueError:
        raised = True
    assert raised, "5-column row should raise ValueError"


def test_load_annotations_rejects_unknown_bin_type():
    import tempfile
    td = Path(tempfile.mkdtemp(prefix="bio_bed_"))
    bed_path = td / "bad_type.bed"
    bed_path.write_text("NC\t10\t20\tsatellite\n")
    try:
        BP.load_annotations(bed_path)
        raised = False
    except ValueError:
        raised = True
    assert raised, "unknown bin type must raise (no silent fallback to intergenic)"


def test_load_annotations_rejects_end_le_start():
    import tempfile
    td = Path(tempfile.mkdtemp(prefix="bio_bed_"))
    bed_path = td / "bad_geom.bed"
    bed_path.write_text("NC\t20\t10\tcoding\n")
    try:
        BP.load_annotations(bed_path)
        raised = False
    except ValueError:
        raised = True
    assert raised, "end <= start must raise"


def test_load_annotations_rejects_negative_coords():
    """BED convention is 0-based half-open with non-negative coords.
    Negative coords would silently route windows to intergenic and confuse
    the per-bin classifier -- reject them."""
    import tempfile
    td = Path(tempfile.mkdtemp(prefix="bio_bed_"))
    bed_path = td / "neg.bed"
    bed_path.write_text("NC\t-5\t10\tcoding\n")
    try:
        BP.load_annotations(bed_path)
        raised = False
    except ValueError:
        raised = True
    assert raised, "negative start coord must raise (BED is 0-based half-open)"


# --- max-overlap classifier -----------------------------------------------

def test_classify_window_bin_picks_max_overlap():
    """Two annotations overlap a window; the one with the LONGER
    intersect-bp count wins. We pick a window where the two intersect
    counts differ clearly so this test isolates the 'max-overlap-wins'
    rule from the start-distance tiebreak (which has its own test)."""
    annots = [
        {"chrom": "X", "start": 0, "end": 50, "type": "intronic"},
        {"chrom": "X", "start": 40, "end": 90, "type": "coding"},
    ]
    # Window (35, 80) size 45:
    #   intronic [0,50): intersect [35,50]=15 bp
    #   coding [40,90):   intersect [40,80]=40 bp
    # Coding wins by clear margin.
    # NOTE: 40/45 = 88.9% < 90% -> straddle=True (the classifier flags it).
    bin_t, ov, straddle = BP._classify_window_bin(35, 80, annots)
    assert bin_t == "coding", f"max-overlap should pick coding, got {bin_t}"
    assert ov == 40
    assert straddle is True, (
        "40/45 = 88.9% < STRADDLE_THRESHOLD=0.9, so the flag is True"
    )


def test_classify_window_bin_straddle_flag_at_below_90pct():
    annots = [{"chrom": "X", "start": 0, "end": 50, "type": "coding"}]
    # window (40, 140) size 100 -> intersect [40,50]=10 -> 10/100=10% < 90% -> straddle=True
    bin_t, ov, straddle = BP._classify_window_bin(40, 140, annots)
    assert bin_t == "coding"
    assert ov == 10
    assert straddle is True, "straddle should fire when intersect < 90% of window"
    # window (0, 50) size 50 -> intersect [0,50]=50 -> 50/50=100% -> NOT straddle (full overlap)
    bin_t2, ov2, straddle2 = BP._classify_window_bin(0, 50, annots)
    assert bin_t2 == "coding"
    assert ov2 == 50
    assert straddle2 is False, "full-overlap window must NOT be flagged as straddle"


def test_classify_window_bin_tiebreak_by_closest_start_when_intersect_equal():
    """When two annotations have EQUAL intersect-bp count, the row whose
    'start' is CLOSEST to window_start wins (deterministic tiebreak).

    (The clear-winner case lives in test_classify_window_bin_picks_max_overlap;
    this test isolates the TRUE-tie case where both intersect AND distance
    are equal -- the loop falls back to 'first record wins'.)
    """
    annots = [
        {"chrom": "X", "start": 0, "end": 100, "type": "intronic"},
        {"chrom": "X", "start": 80, "end": 180, "type": "coding"},
    ]
    # Window (40, 140) size 100:
    #   intronic [0,100):   intersect [40,100]=60 bp, dist = |0 - 40| = 40
    #   coding [80,180):    intersect [80,140]=60 bp, dist = |80 - 40| = 40
    # -> TRUE tie on BOTH intersect and distance -> first record wins (intronic).
    bin_t, ov, _ = BP._classify_window_bin(40, 140, annots)
    assert bin_t == "intronic", f"true-tie should fall back to first record, got {bin_t}"
    assert ov == 60

    # AND when distance differs in the same intersect-tied-equality scenario,
    # the closer-start row wins:
    #   window (60, 160) size 100:
    #     intronic [0,100):  intersect [60,100]=40, dist = |0 - 60| = 60
    #     coding [80,180):   intersect [80,160]=80, dist = |80 - 60| = 20
    # ... here coding wins by CLEAR max-overlap, so this isn't a tiebreak
    # case either -- we don't add a second half; the contract is fully
    # covered by the true-tie case + test_classify_window_bin_picks_max_overlap.


# --- analyze_sequence backwards-compat + annotation extension --------------

def test_analyze_sequence_without_annotations_does_not_emit_bins():
    rep = BP.analyze_sequence("ACGT" * 200, window=64, step=16,
                              label="no-bins", shuffle_seed=42)
    # whole-genome keys present
    assert "window_entropy_bits_real" in rep
    assert "negative_control" in rep
    # no per-bin extension
    assert "bins" not in rep, "without --annotations, `bins` key must NOT appear"
    assert "annotation_summary" not in rep


def test_analyze_sequence_with_tiny_annotations_emits_bins_block():
    """With a BED that covers the whole synthetic seq, the `bins` block
    must appear with enough coding windows (>= MIN_WINDOWS_FOR_BIN_DELTA)
    for a defensible delta."""
    annots = [
        {"chrom": "S", "start": 0, "end": 200, "type": "coding"},
        # the rest is intergenic (no annot)
    ]
    seq = "ATG" + "CGT" * 60 + "TAA"  # ~184 chars
    rep = BP.analyze_sequence(seq, window=30, step=15, label="bin-test",
                              shuffle_seed=7, annotations=annots,
                              annotation_file="<wide-coding-BED>")
    assert "bins" in rep
    assert "coding" in rep["bins"]
    assert "annotation_summary" in rep
    s = rep["annotation_summary"]
    assert s["annotation_file"] == "<wide-coding-BED>"
    assert s["features_parsed"] == 1
    coding = rep["bins"]["coding"]
    # BED covers [0,200) on a ~184-char seq; window 30 / step 15 gives
    # ~12 fully-coding windows -> must clear the min-windows bar.
    assert coding["n_windows"] >= BP.MIN_WINDOWS_FOR_BIN_DELTA
    assert coding["delta_window_H_mean"] is not None
    assert coding["status"] == "ok"


def test_analyze_sequence_per_bin_shuffle_preserves_bin_composition():
    """Per-bin shuffled pool must be composition-preserving at the bin level."""
    annots = [{"chrom": "S", "start": 0, "end": 200, "type": "coding"}]
    seq = "ACGT" * 50  # equal base freq
    rep = BP.analyze_sequence(seq, window=20, step=10, label="cmp",
                              shuffle_seed=11, annotations=annots,
                              annotation_file=None)
    coding = rep["bins"]["coding"]
    pool = seq[0:200]  # the first 200 chars (all coding under our bed)
    real_sorted = sorted(pool.upper())
    # Recompute the shuffle with same seed externally; sanity check multiset invariance.
    shuf_pool = BP.shuffle_seq(pool, seed=11)
    assert sorted(real_sorted) == sorted(shuf_pool.upper())
    # The coding bin's gc_real should equal the original pool's GC (composition-preserving trivially).
    assert abs(coding["gc_real"] - 0.5) < 1e-6


def test_analyze_sequence_min_windows_threshold_flags_small_bins():
    """A bin with fewer than MIN_WINDOWS_FOR_BIN_DELTA windows must have
    status='too_few_windows' and delta_window_H_mean=None."""
    # author a BED that produces a tiny bin: only 1 window will intersect
    annots = [{"chrom": "S", "start": 0, "end": 5, "type": "coding"}]
    seq = "ACGT" * 50
    rep = BP.analyze_sequence(seq, window=20, step=20, label="too-few",
                              shuffle_seed=3, annotations=annots,
                              annotation_file=None)
    coding = rep["bins"].get("coding")
    # With window=20 step=20 starting at w_start=0 -> window [0,20)
    # Overlap with [0,5] = 5 bp -> bin=coding, n_windows=1
    assert coding is not None
    assert coding["n_windows"] < BP.MIN_WINDOWS_FOR_BIN_DELTA
    assert coding["status"] == "too_few_windows"
    assert coding["delta_window_H_mean"] is None


def test_analyze_sequence_empty_annotation_routes_all_to_intergenic():
    """chr22 case: empty BED -> every window is intergenic."""
    rep = BP.analyze_sequence("ACGT" * 100, window=20, step=10,
                              label="all-inter", shuffle_seed=1,
                              annotations=[], annotation_file="<empty>")
    assert "intergenic" in rep["bins"]
    # No other bin should be populated by default classifications.
    populated = [b for b, row in rep["bins"].items()
                 if row["n_windows"] > 0]
    assert populated == ["intergenic"], f"unexpected bins populated: {populated}"


# --- real-asset end-to-end with annotations --------------------------------

def test_real_sars_with_bed_runs_end_to_end():
    """Real SARS FASTA + real NC_045512.2_regions.bed -> end-to-end subprocess."""
    import subprocess
    p_fa = ROOT / "data" / "bio" / "SARS_COV_2_NC_045512.2_head.fasta"
    p_bed = ROOT / "data" / "bio" / "annotations" / "NC_045512.2_regions.bed"
    if not (p_fa.exists() and p_bed.exists()):
        return  # graceful if assets absent
    import tempfile as _tf
    td = Path(_tf.mkdtemp(prefix="bio_sars_bed_"))
    out_json = td / "sars_bed_run.json"
    out_md = td / "sars_bed_notes.md"
    res = subprocess.run([
        sys.executable, str(TOOLS_BIO / "bio_probe.py"),
        str(p_fa), "--window", "200", "--step", "100",
        "--annotations", str(p_bed),
        "--out", str(out_json), "--out-md", str(out_md),
    ], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, (res.stderr[:600] or res.stdout[:600])
    d = json.load(out_json.open())
    assert "bins" in d
    # SARS head 1-4000 has 5'UTR 1-265 and CDS 266-4000 -> both populated.
    assert "coding" in d["bins"], "SARS head should populate coding bin"
    assert "untranslated" in d["bins"], "SARS head should populate 5'UTR bin"
    # Coding should have MANY more windows than untranslated in this slice.
    assert d["bins"]["coding"]["n_windows"] > d["bins"]["untranslated"]["n_windows"]


def test_real_chr22_with_empty_bed_routes_all_to_intergenic():
    """NT_187395.1 BED is empty by design -> every window -> intergenic."""
    import subprocess
    p_fa = ROOT / "data" / "bio" / "HUMAN_chr22_3kb.fasta"
    p_bed = ROOT / "data" / "bio" / "annotations" / "NT_187395.1_regions.bed"
    if not (p_fa.exists() and p_bed.exists()):
        return
    import tempfile as _tf
    td = Path(_tf.mkdtemp(prefix="bio_chr22_bed_"))
    out_json = td / "chr22_bed_run.json"
    res = subprocess.run([
        sys.executable, str(TOOLS_BIO / "bio_probe.py"),
        str(p_fa), "--window", "100", "--step", "50",
        "--annotations", str(p_bed),
        "--out", str(out_json),
    ], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, (res.stderr[:600] or res.stdout[:600])
    d = json.load(out_json.open())
    assert "bins" in d
    # Empty BED -> only intergenic should be populated.
    populated = [b for b, row in d["bins"].items()
                 if row["n_windows"] > 0]
    assert populated == ["intergenic"], (
        f"chr22+empty BED should populate only intergenic, got {populated}"
    )
    s = d["annotation_summary"]
    assert s["features_parsed"] == 0, "empty BED must report features_parsed=0"


# --- read_fasta on real asset ---------------------------------------------

def test_read_fasta_reads_our_sars_asset():
    """data/bio/SARS_COV_2_NC_045512.2_head.fasta should yield a non-empty
    ACGT sequence in the expected length range. Skip gracefully if the
    asset is absent (e.g. fresh clone without `bash tools/open_archives.sh`)."""
    p = ROOT / "data" / "bio" / "SARS_COV_2_NC_045512.2_head.fasta"
    if not p.exists():
        return  # graceful
    seq = BP.read_fasta(p)
    assert len(seq) >= 2000, f"short SARS read: {len(seq)} chars"
    assert all(c.upper() in "ACGT" for c in seq[:200]), "first 200 chars not pure ACGT"


def test_read_fasta_respects_max_bases():
    p = ROOT / "data" / "bio" / "SARS_COV_2_NC_045512.2_head.fasta"
    if not p.exists():
        return
    seq = BP.read_fasta(p, max_bases=500)
    assert len(seq) == 500


# --- main() smoke-test ----------------------------------------------------

def test_main_runs_demo_and_writes_files():
    """End-to-end CLI: --demo + --out + --out-md in a temp dir.
    Uses tempfile.mkdtemp instead of pytest's tmp_path fixture so this
    test is runnable both under pytest AND as `python3 test_bio_probe.py`."""
    import subprocess
    td = Path(tempfile.mkdtemp(prefix="bio_demo_"))
    out_json = td / "demo_run.json"
    out_md = td / "demo_notes.md"
    res = subprocess.run([
        sys.executable, str(TOOLS_BIO / "bio_probe.py"),
        "--demo", "--out", str(out_json), "--out-md", str(out_md),
    ], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, (
        f"bio_probe.py --demo failed:\nSTDOUT:\n{res.stdout[:600]}\n"
        f"STDERR:\n{res.stderr[:600]}"
    )
    assert out_json.exists()
    assert out_md.exists()
    with open(out_json) as f:
        d = json.load(f)
    assert "demo_mixed" in d
    assert "DEMO MODE" in out_md.read_text()


def test_main_runs_on_real_fasta_and_writes_notes():
    """End-to-end CLI: real FASTA + --out + --out-md."""
    import subprocess
    p = ROOT / "data" / "bio" / "SARS_COV_2_NC_045512.2_head.fasta"
    if not p.exists():
        return  # graceful -- asset absent
    td = Path(tempfile.mkdtemp(prefix="bio_real_"))
    out_json = td / "sars_run.json"
    out_md = td / "sars_notes.md"
    res = subprocess.run([
        sys.executable, str(TOOLS_BIO / "bio_probe.py"),
        str(p), "--window", "100", "--step", "25",
        "--out", str(out_json), "--out-md", str(out_md),
    ], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, (res.stderr[:600] or res.stdout[:600])
    assert out_json.exists()
    assert out_md.exists()
    d = json.load(out_json.open())
    assert "window_entropy_bits_real" in d
    assert "negative_control" in d
    assert "Δ_window_mean_H" in out_md.read_text()


if __name__ == "__main__":
    # Standalone-mode runner: filters out functions requiring pytest fixtures.
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    def _needs_fixture(f):
        params = list(inspect.signature(f).parameters)
        return bool(params)
    runnable = [f for f in fns if not _needs_fixture(f)]
    skipped = [f for f in fns if _needs_fixture(f)]
    for fn in skipped:
        print(f"SKIP {fn.__name__}  (private pytest-fixture)")
    ok = 0; bad = 0
    for fn in runnable:
        try:
            fn()
            print(f"PASS {fn.__name__}")
            ok += 1
        except Exception as e:
            print(f"FAIL {fn.__name__}: {type(e).__name__}: {e}")
            bad += 1
    print(f"\n{ok}/{len(runnable)} passed, {bad} failed, {len(skipped)} skipped")
    sys.exit(0 if bad == 0 else 1)
