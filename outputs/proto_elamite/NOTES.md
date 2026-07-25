# G2 — Proto-Elamite ledger-entropy probe  🟢

Generated: 2026-07-25T11:20:24.004871+00:00

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

## Probe

- Label: `synthetic_known_answer`
- N input tokens: **102**

### Header block

- tokens: 13  numerics: 0  H₁: 2.873  IC: 0.0769  LZ78: 0.7692

### Line block

- tokens: 89  numeral blocks: 30
- numeral H₁: 2.0  H(next|n): 1.559  IC: 0.1382  LZ78: 0.4831

- Shuffled null (n=1000, unigram-preserving): observed=2.0356  mean=2.2809  z=-3.28

### Invariants

- header_numeral_void: **True**
- header_fraction_bounded: **True**
- numeral_block_predictable: **True**
- z_lock_vs_shuffle: **True**

### Verdict: **STRUCTURED_NUMERIC_LEDGER**

Structure != message. These invariants confirm accounting ledgers have predictable low-entropy numeral blocks. They do NOT confirm Proto-Elamite is a language, NOT identify the script's family, and NOT imply reading ability.

---
*G2 Proto-Elamite — structure != message. Predictable low-entropy numeral blocks are NECESSARY-not-sufficient for a structured ledger, not for a language, not for anything past the arithmetic of accounting.*