# Cypro-Minoan sign-sequence corpus

## Source

- **Corazza et al. 2022 PLOS ONE** — *Unsupervised deep learning supports reclassification of Bronze age cypriot writing system*. PLOS ONE 17(7): e0269544.
- **Figshare collection 6095488** (https://plos.figshare.com/collections/6095488) — Supplementary tables.
- **GitHub: ashmikuz/sign2vec_d** (https://github.com/ashmikuz/sign2vec_d) — context.csv with sliding-window trigrams of 2899 sign images from 213 inscriptions.
- **INSCRIBE project** (https://corpora.ficlit.unibo.it/INSCRIBE/PaperCM/) — Scatterplots.

## Files

| File | Contents | License |
|------|----------|---------|
| `corpus.json` | Parsed sign sequences (2848 clean tokens from 565 rows, 39 sites) | CC BY 4.0 (sign sequences derived from sign2vec_d) |
| `README.md` | This file | — |

## Subgroups (traditional classification)

Per Corazza et al. (2022):
- **CM1**: 4 clay tablet fragments from Enkomi (1153 signs) — restricted, formulaic
- **CM2**: Majority of corpus from Enkomi + Ras Shamra/Ugarit (1430 signs)
- **CM3**: Smaller subset of Enkomi inscriptions (316 signs)

The paper argues these divisions reflect **media-driven allography** rather than distinct scripts.

## Sign numbering

Corazza consensual graphemes: 001–114 (+ 201, 202), 96 syllabogram categories.
Numerals: I, II, III, VII, X, XXX, CC, CCC.
Sequence divider: P.
See Table 1 in the paper for the 15 most frequent signs.

## Attribution

Corazza, M., Tamburini, F., Valério, M., & Ferrara, S. (2022). Unsupervised deep learning supports reclassification of Bronze age cypriot writing system. *PLOS ONE* 17(7): e0269544. https://doi.org/10.1371/journal.pone.0269544

## Stance

structure != meaning. No decipherment claims.
