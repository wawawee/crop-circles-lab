# Indus script corpus — open sign streams

## Source
- **mayig/indus-valley-script-corpus** (https://github.com/mayig/indus-valley-script-corpus) — MIT / Apache 2.0.
- Digitisation of **CISI (Corpus of Indus Seals and Inscriptions)** by Parpola et al.
- Sign encoding: Parpola sign numbers (P001–Pxxx) with integer feature vectors for allographs.

## Files
| File | Contents | License |
|------|----------|---------|
| `corpus.json` | Consolidated Mohenjo-daro corpus: 179 sequences, 1003 signs, 182 distinct | MIT / Apache 2.0 |
| `ingest_corpus.py` | One-shot fetcher for mayig corpus | MIT / Apache 2.0 |
| `README.md` | This file | — |

## Attribution
- Parpola, A. et al. *Corpus of Indus Seals and Inscriptions* (CISI). Suomalainen Tiedeakatemia, Helsinki.
- mayig (GitHub user). *indus-valley-script-corpus*. https://github.com/mayig/indus-valley-script-corpus
- Wells, B. K. (2015). *The Archaeology and Epigraphy of Indus Writing*. Archaeopress.
- Mahadevan, I. (1977). *The Indus Script: Texts, Concordance and Tables*. MASI 77.

## Stance
Indus script is undeciphered. This directory supports `tools/scripts/indus_probe.py`,
which measures *sign-sequence structure* only — no decipherment, no language-family claims,
no Dravidian/IE/Sumerian assertions.

## Forbidden phrases
`translates to`, `represents`, `decodes as`, `shares roots with`, `is related to Dravidian`,
`is related to Sumerian`, `Indus script is a`, `Indus script =`, `aliens wrote`.
