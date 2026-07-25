# Proto-Elamite corpus — open data files

## Source
- **CDLI** (https://cdli.mpiwg-berlin.mpg.de / https://cdli.ucla.edu) — the
  Cuneiform Digital Library Initiative, open-access ATF transcriptions of
  Proto-Elamite and Susa-era tablets. Per-tablet attribution via `cdli_id`.
- **Licence**: CDLI open-data terms (per-tablet attribution required).
- **Period**: ca. 3100-2900 BCE, Susa, south-western Iran.

## Files
| File | Contents | Status |
|------|----------|--------|
| `uruk_comparator_refs.json` | Static list of candidate Uruk III SFU-comparator tablet CDLI IDs (Schmandt-Besserat Sub-Fund-Units context). **POSTPONED live fetch**: comparator design path documented, NOT activated in MVP. | 🟡 POSTPONED |
| `README.md` | This file | — |

## Stance
Proto-Elamite is undeciphered. This directory supports
`tools/scripts/proto_elamite_probe.py`, which measures *numeric-block
structure* only — no decipherment, no language-family claims.

## Forbidden phrases
Logged in `tools/scripts/proto_elamite_probe.py :: FORBIDDEN_PHRASES`:
`translates to`, `represents`, `decodes as`, `shares roots with`, `is
related to Sumerian`, `is related to Elamite`, `Proto-Elamite is a`,
`Proto-Elamite =`, `Minoan =`.

## Usage
This dataset is referenced from `tools/scripts/proto_elamite_probe.py`.
Production live-fetch requires internet access + a `cdli_id` argument;
without `--fetch-online` the probe returns an honest-empty
NEVER_ATTEMPTED result.
