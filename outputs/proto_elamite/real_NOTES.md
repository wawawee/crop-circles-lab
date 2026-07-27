# G2-REAL — Proto-Elamite CDLI live fetch  🔴

Generated: 2026-07-27T03:08:56.571666+00:00

## Stance

Proto-Elamite is undeciphered (ca. 3100-2900 BCE, Susa). This probe measures *numerical-block structure* only — it does NOT translate, decipher, or place Proto-Elamite in a language family. STRUCTURE != MESSAGE. Reused tools/forensics/symbolseq.py for all metrics.

**Motto:** *structure != message.* No decipherment, no language-family claim.

### Forbidden phrases (logged so a code-reviewer catches drift)

- `translates to`
- `represents`
- `decodes as`
- `shares roots with`
- `is related to Sumerian`
- `is related to Elamite`
- `Proto-Elamite is a`
- `Proto-Elamite =`
- `Minoan =`
- `PE related to Sumerian`
- `Proto-Elamite is Sumerian`
- `Proto-Elamite is cuneiform`
- `Proto-Elamite derives from`
- `Urukian origin`
- `Sumerian-Elamite`
- `Proto-Elamite is descended from Sumerian`
- `Proto-Elamite script family`
- `Sumerian ancestor`

## Source

Open data via Cuneiform Digital Library Initiative (CDLI), https://cdli.mpiwg-berlin.mpg.de — ATF transcriptions released under the CDLI open-data terms. Per-tablet attribution by `cdli_id`.

## Fetch summary

- IDs requested: 1
- Tablets fetched: 0
- Tablets blocked: 1

### Per-tablet results

- 🔴 `P008001` -> UNREACHABLE (0 tokens)

## Probe

- N input tokens: **0**

### Header block

- tokens: 0  numerics: 0  H₁: 0.0  IC: 0.0

### Line block

- tokens: 0  numeral blocks: 0
- numeral H₁: 0.0  H(next|n): 0.0  IC: 0.0  LZ78: 1.0

- Shuffled null: observed=0.0  mean=0.0  z=0.0

### Invariants

- header_numeral_void: **True**
- header_fraction_bounded: **False**
- numeral_block_predictable: **True**
- z_lock_vs_shuffle: **False**

### Synth vs real comparison

- Synth all_pass: **True**  Real all_pass: **False**
- All invariants match: **False**  Both pass: **False**
- cond-H diff (real - synth): -1.559 bits
- z diff (real - synth): 3.16

The synthetic fixture is a simplified model of the accounting-tablet structure. Real CDLI data may contain fragmentary tablets, damage markers, and additional metadata. Match/mismatch of invariants is a STRUCTURAL comparison only — not a test of authenticity or meaning.

### Verdict: **FETCH_BLOCKED**

This analysis of real CDLI Proto-Elamite tablets measures STRUCTURE ONLY — whether the combined token stream from real tablets passes the same 4 ledger invariants as the synthetic known-answer fixture. It does NOT decipher, translate, or identify a language family. STRUCTURE != MESSAGE.


---
*G2-REAL — CDLI live fetch of Proto-Elamite tablets. Structure != message. The verdict reflects whether real CDLI ATF data shows the same accounting-ledger structural invariants as the synthetic known-answer fixture. It does NOT decipher, translate, or identify a language family.*