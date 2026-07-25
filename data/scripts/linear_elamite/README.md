# Linear Elamite corpus — open data files

## Status

🟡 **HONEST SKIP** — no open dump was bundled into the repo at G12 time. The
probe (`tools/scripts/linear_elamite_probe.py`) ships with a deterministic
**synthetic** Linear-Elamite-like corpus (`synth_corpus.json`) for the math
probe + 4 invariants math validation. A polite live-fetcher against CDLI
Zenodo `10.5281/zenodo.4960710` is wired (default `NEVER_ATTEMPTED`, no
network contact unless the user explicitly invokes `--fetch-online`).

This is the G2/G2++/G10-style `NEVER_ATTEMPTED` honest-empty stance: ship
the math probe + comparison machinery + verdict tree, never fabricate
"real corpus" tokens when the dump is gated or blocked.

## What G12 does NOT include (and why)

- **No image dumps.** The brief explicitly excludes image artefacts;
  sign-ID streams only.
- **No SES (Proto-Elamite/Sumerian) language-family bridge claims.** G12
  treats LE as a structural probe and uses Proto-Elamite / Uruk III as
  STRUCTURE comparators only. `language_family_claim_made: false` is
  asserted in any comparator output.
- **No Desset/Liège-2024 endorsement.** The 2024 publicity is filed as a
  claim-under-test (`desset_2024_claim_block`); we recompute whatever
  frequency/bigram claim we can on the open data WITHOUT endorsing any
  phonetic/glottal-stop reading.

## Open-data pointers (documented for downstream follow-up)

| Source | Pointer | Status | Reason |
|--------|---------|--------|--------|
| **CDLI Zenodo (open)** | `10.5281/zenodo.4960710` | attempted, gated | Polite live-fetcher wired; default NEVER_ATTEMPTED. |
| **Hatamti / Liège 2024** *(in press)* | Liege University transcription release | pending release | Catalogued sign list only; phonetic values still disputed. |
| **Meriggi / Hinz sign lists** | Historical (paper) | HARD_COPY_ONLY | Public-domain summary in scholarly works; not machine-readable. |

## Files

| File | Contents |
|------|----------|
| `README.md` | This file |
| `synth_corpus.json` | Deterministic synthetic LE-like corpus (formulaic + monumental sub-bundles). Math-probe inputs. |
| `open_status.json` | Honest record of online-fetch attempts (status `NEVER_ATTEMPTED` by default). |

## Stance

Linear Elamite (ca. 2200-1850 BCE, Anshan/Susa) is UNDECIPHERED. This
directory supports `tools/scripts/linear_elamite_probe.py`, which measures
*structural entropy of the unified sign sequence* and applies the
**ledger-style 4 invariants** that G2 calibrated on Proto-Elamite
accounting tablets. The invariants *will NOT* pass on monumental / narrative
LE inscriptions — and that failure is itself informative: it tells you
the corpus contains narrative text, not accounting ledgers. The
**anticipated verdict** on a dump dominated by monumental inscriptions is
`UNDERDETERMINED` with the caveat that the chosen invariants target
accounting-tablet structure only.

Forbidden phrases logged in `tools/scripts/linear_elamite_probe.py ::
LE_FORBIDDEN_PHRASES`:
- `Linear Elamite deciphered`
- `Linear Elamite = `
- `Elamite represents `
- `translates to`
- `decodes as`
- `shares roots with`
- `is related to Akkadian`
- `is related to Sumerian`
- `is related to Elamite`
- `alien`
- `viral blog`
- `youtube decipherment`
- a list of additional phrases from `FORBIDDEN_PHRASES` (inherited verbatim from G2)

## Usage

```bash
# Math-prove the 4 invariants on the synthetic corpus (no network):
python tools/scripts/linear_elamite_probe.py --synthetic

# Polite live fetch from CDLI Zenodo 10.5281/zenodo.4960710:
python tools/scripts/linear_elamite_probe.py --fetch-online --cdli-record z4960710

# Bypass the polite default with a USER_OVERRIDE bundled corpus:
python tools/scripts/linear_elamite_probe.py --bundled-corpus path/to/lei.json
```

## Ethics / licensing

- **CDLI**: open-data terms, per-tablet attribution via `cdli_id`. No
  republish without per-record bundling.
- **Hatamti / Liège 2024**: pending accessibility — treat any quotation as
  fair-use scholarly reference ONLY.
- Any verdict or visualisation of "real" LE data must carry an explicit
  `_PRIVATE_NOT_FOR_REDISTRIBUTION` marker when bundled into research
  artefacts (captain's brief: "no large image dumps").

---

*G12 Linear Elamite — structure != message. The ledger invariants target
an accounting-tablet SHAPE; failing them on monumental LE inscriptions
means "this is not an accounting text", NOT "this script lacks structure".
Desset/Liège 2024 is filed as a claim-under-test only; verification on
the open dump is recompute + shuffle-null.*
