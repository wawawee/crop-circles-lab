# G2++ — Uruk III SFU comparator  🟢

Generated: 2026-07-25T11:19:14.523201+00:00

## Stance

Uruk III (ca. 3300-3000 BCE) Sumerian cuneiform accounting tablets are STRUCTURAL positive controls for the Proto-Elamite probe: same period, same accounting-tablet purpose, DIFFERENT sign pool. STRUCTURE != MESSAGE. This probe measures numerical-block SHAPE only — it does NOT translate, decipher, or relate Proto-Elamite and Sumerian cuneiform. Numerals are arithmetic, NOT linguistics; their shared tag system is a STRUCTURAL choice in ancient accounting, not evidence of script-family derivation. Reused tools/forensics/symbolseq.py + the G2 probe machinery end-to-end.

**Motto:** *structure != message.* NO language-family claim either way.

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

## Comparison summary

| metric | PE | Uruk | match |
|--------|----|------|-------|
| `header_numeral_void` | True | True | True |
| `header_fraction_bounded` | True | True | True |
| `numeral_block_predictable` | True | True | True |
| `z_lock_vs_shuffle` | True | True | True |

- PE all_pass: **True**
- Uruk all_pass: **True**
- both_pass: **True**
- all_invariants_match: **True**

### Numerical diffs (no language-claim interpretation)

- header H₁ diff (URUK − PE): 0.366 bits
- line cond-H diff: -0.936 bits
- LZ78 ratio diff: 0.0283
- shuffled z diff: -1.72

## SFU subset-sum probe

- status: `SKIPPED_PER_BRIEF_NON_TRIVIAL`
- note: Captain brief: 'Optional SFU/subset-sum only if trivial; else SKIP.' Schmandt-Besserat SFU = 1, 10, 60, 360, 3600 sexagesimal subdivisions of measure. Subset-sum probe would test if recorded quantities fit n1*60^k + n2*60^j + ...; implementation requires Sumerian sexagesimal digit decomposition (non-trivial) vs PE simple-integer notation. Documented as POSTPONED; re-evaluate in a follow-up ticket with explicit math-spec.

## Source

Open data via Cuneiform Digital Library Initiative (CDLI), https://cdli.mpiwg-berlin.mpg.de — ATF transcriptions released under the CDLI open-data terms. Per-tablet attribution by `cdli_id`.


---
*G2++ Uruk III SFU comparator — structure != message. Same-shape invariants in DIFFERENT sign systems confirm a shared accounting-tablet STRUCTURE, NOT script-family derivation. SFU/subset-sum probe SKIPPED per Captain brief 'Optional only if trivial; else SKIP'.*