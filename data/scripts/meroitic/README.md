# Meroitic script corpus — open sign streams

## Source
- **Joshua-Otten/Meroitic-Corpus** (https://github.com/Joshua-Otten/Meroitic-Corpus) — Otten & Anastasopoulos 2025.
- No license specified in source repository; all rights reserved by default.
- Sign transliterations scraped from **RAMSES Online** (https://ramses.ulg.ac.be), an annotated corpus of Late Egyptian that also indexes Meroitic inscriptions from the DAE/Méroe project.

## Files
| File | Contents | License |
|------|----------|---------|
| `mero-corpus.txt` | Raw space-separated sign transliterations (18,090 lines, 756K tokens) | All rights reserved (source repo) |
| `corpus.json` | Parsed JSON: sequences dict (ins_1 .. ins_18090), metadata | All rights reserved |
| `late_egyptian_sample.json` | Late Egyptian hieratic transliterations from RAMSES Online (10K tokens) | Fair use / research |
| `README.md` | This file | — |

## Stance
Meroitic script is partially deciphered (the script is readable, the language is poorly understood; cf. Rilly 2007, 2010). This directory supports `tools/scripts/meroitic_probe.py`, which measures *sign-sequence structure* only — no decipherment claims, no translation, no "Meroitic deciphered" claims. Structure ≠ meaning.

## Forbidden phrases
`Meroitic deciphered`, `translates to`, `represents`, `decodes as`, `shares roots with`,
`crank 99.5%`, `Ghost License`, `Lackadaisical Security`, `aliens wrote`

## Usage
```
python tools/scripts/meroitic_probe.py              # real corpus
python tools/scripts/meroitic_probe.py --synthetic   # known-answer demo
```

## Attribution
- Otten, J. & Anastasopoulos, A. (2025). *Meroitic-Corpus: first machine-readable Meroitic corpus*. GitHub.
- Rilly, C. (2007). *La langue du royaume de Méroé*. Paris: Champion.
- Rilly, C. (2010). *Le méroïtique et sa famille linguistique*. Leuven: Peeters.
- RAMSES Online — Base de données d'annotations des textes égyptiens de la période ramesside.
- Millet, N. B. *Meroitic Nubia*. (vocabulary list).
- Lobban, R. *Meroitic vocabulary list*. (vocabulary list).
