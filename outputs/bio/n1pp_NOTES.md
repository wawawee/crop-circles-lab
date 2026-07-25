# N1++ — bio_probe hardens (Cursor, 2026-07-25)

## Landed

1. **`window_chrom` filter** on `_classify_window_bin` — mismatched BED chroms skipped; CLI `--seq-chrom`.
2. **`bins_status: skipped_seq_too_short`** when `len(seq) < window` but features_parsed > 0.
3. **Intronic bin** — verified via synthetic exon/intron/exon BED (real SARS asset still UTR+CDS only by construction).
4. **NumPy shuffle** — `shuffle_seq` uses `np.random.default_rng` when available; stdlib fallback.

## Tests

`python tools/bio/tests/test_bio_probe.py` → **33/33** (+4 N1++ cases).

## Stance

Unchanged: biology ≠ message. Hardens only.
