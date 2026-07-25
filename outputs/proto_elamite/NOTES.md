# G2 — Proto-Elamite ledger-entropy probe  🟡

Generated: 2026-07-25T10:47:39.583765+00:00

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

## Source

Open data via Cuneiform Digital Library Initiative (CDLI), https://cdli.mpiwg-berlin.mpg.de — ATF transcriptions released under the CDLI open-data terms. Per-tablet attribution by `cdli_id`.

## Probe

- Label: `bundled:test_pe_atf.json`
- N input tokens: **49**

### Header block

- tokens: 13  numerics: 0  H₁: 3.547  IC: 0.0128  LZ78: 0.9231

### Line block

- tokens: 36  numeral blocks: 15
- numeral H₁: 2.151  H(next|n): 1.143  IC: 0.0921  LZ78: 0.6111

- Shuffled null (n=1000, unigram-preserving): observed=1.4933  mean=1.4869  z=0.07

### Invariants

- header_numeral_void: **True**
- header_fraction_bounded: **True**
- numeral_block_predictable: **True**
- z_lock_vs_shuffle: **False**

### Verdict: **INCONCLUSIVE_OR_HONEST_EMPTY**

Structure != message. These invariants confirm accounting ledgers have predictable low-entropy numeral blocks. They do NOT confirm Proto-Elamite is a language, NOT identify the script's family, and NOT imply reading ability.

---
*G2 Proto-Elamite — structure != message. Predictable low-entropy numeral blocks are NECESSARY-not-sufficient for a structured ledger, not for a language, not for anything past the arithmetic of accounting.*