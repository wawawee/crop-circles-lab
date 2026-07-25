# Voynich corpus — open transcription (text only)

## Source

- **ZL3b-n.txt** — Zandbergen & Landini EVA transcription of the Voynich
  manuscript, hosted at <https://www.voynich.nu/data/ZL3b-n.txt>
  (~402 KB, IVTFF 2.0, 8500+ lines, EVA extended alphabet).
- **HuggingFace mirror** — `AncientLanguages/Voynich` (same ZL/Takahashi
  sources).
- **2025 Zenodo Arabic-root morphology (claim-under-test only)** — Dominik, M.
  (2025-10-21). *Structural Convergence Between the Voynich Manuscript and
  Arabic Root Morphology.* Zenodo. <https://doi.org/10.5281/zenodo.17409830>
  (CC BY 4.0). **NOT bundled** — we recompute Voynich bigram frequencies
  ourselves from ZL3b-n.txt and compare to a small embedded list of common
  Semitic triliteral roots (common-knowledge lexical patterns, no third-party
  content required).

## Files

| File | Contents | License / Notes |
|------|----------|-----------------|
| `ZL3b-n.txt` | ZL3b-n transcription of all Voynich folios (IVTFF 2.0, EVA) | Attribute Zandbergen & Landini; MS manuscript public domain; hosted openly at voynich.nu |
| `README.md`  | This file | — |

## Attribution

- Zandbergen, R., & Landini, G. C. *The Voynich Manuscript* transcription
  ZL3b-n. <https://www.voynich.nu/data/ZL3b-n.txt>
- Takahashi, T. (Stolfi transliteration IT2a-n). Basic EVA alphabet.
- IVTFF 2.0 — transcription convention.

## Skip list (intentionally not bundled)

- Beinecke IIIF page scans (we analyse statistical structure of the
  transcription; no images needed).
- Embargoed Zenodo corpora.
- "Decryption / English-translation" packs.
- Dominik's pre-filtered `voynich_eva_words.txt` — we use raw ZL3b-n as
  primary source so claim-replication is not biased by Dominik's prefilter.

## Stance

Voynich is undeciphered. This directory supports
`tools/scripts/voynich_probe.py`, which measures *sign-sequence / morphology
structure* only — no decipherment, no language-family claims, no "Arabic
reading" claims, no alien authorship claims. The 2025 Dominik Arabic-ρ result
is treated strictly as a **claim-under-test** and re-evaluated against a
matched shuffle null; the published ρ ≈ 0.82 is **not** propagated as a
finding.

## Forbidden phrases

The probe's forbidden-phrase list is the literal enumeration that the
drift guard scans NOTES.md body prose against. **This README is documentation,
not prose-guard content — do not run the prose-guard against this file.**
The audit surface lives in `tools/scripts/voynich_probe.py :: FORBIDDEN_PHRASES`
and is rendered to NOTES.md via the `log_section` block at the END of the
file (which the body-only guard explicitly skips).

> *Forbidden-phrase audit surface (rendered by the probe's `log_section`):*
> *translates to, decodes as, reads as, is Arabic, is language, Voynich
> translated, Voynich deciphered, Voynich is a, Voynich =, shares roots
> with, is related to Arabic, is related to Latin, aliens wrote,
> Dominik's Arabic translation, viral blog, viral decipherment,
> etymological root of Voynich.*

## Usage

```python
import sys
sys.path.insert(0, ".")
from tools.scripts.voynich_probe import parse_zl_ivtff
sequences = parse_zl_ivtff("data/scripts/voynich/ZL3b-n.txt")
```

CLI:

```bash
python tools/scripts/voynich_probe.py \
    --data data/scripts/voynich/ZL3b-n.txt \
    --out-json outputs/voynich/run.json \
    --out-md outputs/voynich/NOTES.md
```

The probe logs the 2025 Arabic-ρ result as
`claim_under_test_results.dominik_rho.value` plus a shuffle-null
distribution so a code-reviewer or downstream analyst can decide
`CLAIM_FAILS_NULL` vs `SEQUENCE_STRUCTURE` from the same JSON.

## Provenance fetch

The download script for ZL3b-n lives in the probe as
`fetch_zl3b_n(target_path)` (HTTP 200 verified scout-2026-07-25). If
--data is missing and --fetch-corpus is passed, the probe downloads
once into data/scripts/voynich/ZL3b-n.txt.
