# Linear A corpus — open sign streams

## Source
- **SigLA** (https://sigla.phis.me) — Ester Salgarella and Simon Castellan. CC BY-NC-SA 4.0.
- **lineara.xyz** (https://github.com/mwenge/lineara.xyz) — mwenge's Linear A Explorer. Data compiled from GORILA (Godart & Olivier) and George Douros' tabulations.

## Files
| File | Contents | License |
|------|----------|---------|
| `linear_a_corpus.json` | Extracted syllabogram sequences from all documents (5104 tokens, 246 distinct signs) | Data: CC BY-NC-SA 4.0 (SigLA) / GORILA © École Française d'Athènes |
| `linearb_corpus.json` | Linear B syllabogram corpus from words_in_linearb.js (1520 tokens, 69 signs) | Same source terms |
| `LinearAInscriptions.js` | Raw data dump from mwenge/lineara.xyz | See above |
| `words_in_linearb.js` | Linear B word lists (identical + similar to Linear A) | See above |
| `README.md` | This file | — |

## Attribution
- Salgarella, E. & Castellan, S. (2020–). *SigLA: The signs of Linear A*. https://sigla.phis.me
- Godart, L. & Olivier, J.-P. (1970). *Recueil des Inscriptions en Linéaire A* (GORILA). École Française d'Athènes.
- Douros, G. Linear A inscriptions tabulation. http://users.teilar.gr/~g1951d/
- mwenge. *Linear A Explorer*. https://github.com/mwenge/lineara.xyz

## Usage
Corpus is extracted as `words` (list of lists of syllabogram tokens) and `tokens_flat` (flat sequence). No images, only sign sequences.
