# G12 — Linear Elamite entropy bounds  🟢

Generated: 2026-07-25T12:47:05.877553+00:00

## Stance

Linear Elamite (ca. 2200-1850 BCE, Anshan/Susa) is UNDECIPHERED. This probe measures *structural entropy of the unified sign sequence* and applies the 4 ledger-style invariants the G2 probe calibrated on Proto-Elamite accounting tablets. The invariants WILL NOT pass on monumental / narrative LE inscriptions — that failure means 'this is not an accounting tablet', NOT 'this script lacks structure'. STRUCTURE != MESSAGE. Reused tools/forensics/symbolseq.py for all metrics.

### Monumental caveat

Unlike Proto-Elamite, which is overwhelmingly accounting-tablet, Linear Elamite has famous monumental inscriptions (silver beakers, metalwork, royal stelae). The 4 ledger invariants target an accounting-tablet SHAPE — they will FAIL on monumental corpora by construction, and that failure is itself informative: it tells you the corpus is narrative, not numeric-ledger. Do NOT interpret a monumental-bundle FAIL as 'LE lacks linguistic structure'.

**Motto:** *structure != message.* No decipherment. No language ID. No script-family claim.

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
- `Linear Elamite deciphered`
- `Linear Elamite is deciphered`
- `LE deciphered`
- `LE = `
- `Elamite = `
- `Linear Elamite = `
- `Linear Elamite translates`
- `Elamite represents `
- `is related to Akkadian`
- `is the same as Akkadian`
- `Sumerian-Elamite`
- `Akkadian-Elamite`
- `viral blog`
- `youtube decipherment`
- `anonymous `
- `99% deciphered`
- `100% deciphered`
- `alien origin`
- `aliens wrote`
- `extraterrestrial script`
- `ancient aliens`
- `alien`

## Source

Open data via Cuneiform Digital Library Initiative (CDLI) and Zenodo mirror at https://zenodo.org/record/4960710 — per-tablet attribution via `cdli_id`, released under the CDLI open-data terms.

## Probe

- Label: `synthetic_known_answer`
- N input tokens: **96**

### Header block

- tokens: 13  numerics: 0  H₁: 2.661  IC: 0.1026  LZ78: 0.6923

### Line block

- tokens: 83  numeral blocks: 30
- numeral H₁: 1.785  H(next|n): 0.501  IC: 0.1411  LZ78: 0.4819

- Shuffled null (n=1000, unigram-preserving): observed=1.9128  mean=2.1924  z=-3.68

### Invariants

- header_numeral_void: **True**
- header_fraction_bounded: **True**
- numeral_block_predictable: **True**
- z_lock_vs_shuffle: **True**

### Verdict: **STRUCTURED_NUMERIC_LEDGER**

Structure != message. These invariants confirm that the passed bundle carries an accounting-tablet SHAPE. They do NOT confirm LE is a language, NOT identify the script's family, and NOT imply reading ability.

---
*G12 Linear Elamite — structure != message. Predictable low-entropy numeral blocks are necessary-not-sufficient for an accounting-tablet STRUCTURE, not for a language, not for any reading capability.*