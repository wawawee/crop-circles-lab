# G10 — Voynich morphology (structure-only)  🟢

Generated: 2026-07-25T12:16:21.587751+00:00

## Stance

The Voynich manuscript (bought by Wilfrid Voynich 1912; Bodleian MS 408; radiocarbon-dated ca. 1404-1438) is undeciphered. This probe measures *sign-sequence / morphology structure* only — it does NOT translate, decipher, identify the script's language family, or endorse any 2025 'Arabic ρ' viral claim. STRUCTURE != MESSAGE. Reused tools/forensics/symbolseq.py for all metrics.

**Motto:** *structure != message.* No decipherment, no language ID, no Arabic reading claim, no alien claim, no viral-blog as truth.

## Source

ZL3b-n.txt — Zandbergen, R. & Landini, G. C. (2026). Voynich Manuscript EVA transcription (IVTFF 2.0). Open transcription hosted at https://www.voynich.nu/data/ZL3b-n.txt. Compute statistics directly from this corpus; do not redistribute as a Voynich edition.

## Corpus

- Path: `data/scripts/voynich/ZL3b-n.txt`
- Text lines parsed: **5612**
- Folios: **184**
- Word tokens: **35498**  Char tokens: **193858**  Glyph tokens: **163391**  Distinct chars: **41**  Distinct glyphs: **46**

## Morphology (entropy / shuffled-control)

### Word level
- H₁: 10.873  H(next|n): 3.95  IC: 0.0025  LZ78: 0.5713
- Shuffled null (n=1000, unigram-preserving): observed=3.9502  mean=4.0853  sd=0.0024  z=-55.83

### Character level
- H₁: 3.899  H(next|n): 2.362  IC: 0.0765  LZ78: 0.1615
- Shuffled null (n=1000, unigram-preserving): observed=2.3621  mean=3.8952  sd=0.0002  z=-8259.21

### Glyph level (extended EVA digraphs: aiin, dain, cth, ch, sh)
- H₁: 3.95  H(next|n): 2.718  IC: 0.0829  LZ78: 0.1829
- Shuffled null (n=1000, unigram-preserving): observed=2.7182  mean=3.9435  sd=0.0002  z=-6448.69

### Top word bigrams
- `or aiin` ×28
- `chol daiin` ×25
- `s aiin` ×23
- `chol chol` ×20
- `qokeedy qokeedy` ×19

### Top char bigrams
- `c h` ×11050
- `h e` ×8230
- `d y` ×7024
- `a i` ×6746
- `o k` ×6313

### Top glyph bigrams
- `d y` ×7024
- `o k` ×6313
- `o l` ×5849
- `e e` ×5314
- `q o` ×5303

## Known-answer controls

### Planted Voynichese-like Markov chain
- n_tokens: 4000  n_distinct: 17  H(next|n): 3.36  LZ78: 0.3215
- Shuffled null (n=1000, unigram-preserving): observed=3.3598  mean=4.0271  sd=0.0038  z=-176.86
- Pass: **True** (z<-3 ⇒ engineered low-cond-H sequence separates from its shuffle).

### Planted Latin-like (SYNTHETIC 1st-order Markov over embedded Latin-style lexicon)
- n_tokens: 4000  n_distinct: 91  H(next|n): 4.052  LZ78: 0.393
- Shuffled null (n=1000, unigram-preserving): observed=4.0523  mean=4.4671  sd=0.0128  z=-32.42
- Pass: **True** (z<-3 ⇒ synthetic natural-language-like sequence separates from its shuffle).

## Claim under test — Dominik 2025 Arabic ρ

Dominik, M. (2025-10-21). Structural Convergence Between the Voynich Manuscript and Arabic Root Morphology. Zenodo. https://doi.org/10.5281/zenodo.17409830 (CC BY 4.0). ABSTRACT CLAIM (untested): Spearman ρ ≈ 0.82 between Voynich bigram distribution and synthetic Arabic triliteral-root bigram control. PACKAGED JSON MISMATCH: pre-packaged CSV/JSON reports ρ ≈ 0.9999 / slope ≈ 0.044, which is INCONSISTENT with the abstract's ρ ≈ 0.82. This pipeline recomputes the ρ claim UNDER the highlight test: Voynich bigram ranks vs a small embedded Semitic triliteral-root bigram list, versus a matched unigram-preserving shuffle null. We DO NOT verify the Dominik packaged JSON numerically (it is not bundled), but we report the conceptual ρ + shuffle-null z so a downstream analyst can declare CLAIM_FAILS_NULL if the recomputed ρ does not beat the shuffled null.

- Recomputed ρ vs embedded Semitic triliteral-root bigrams: **rho = -0.2452**  n_aligned = 200
- Unigram-preserving shuffle null (n=20): observed = last run pinned (Voynich tokens kept constant); shuffled mean ρ = 0.1265  sd = 0.003  z_relative_to_shuffle = -124.45
- Published (abstract, untested here): ρ ≈ 0.82. Packaged-JSON file unbundled → ρ ≈ 0.9999 / slope ≈ 0.044 (inconsistent with abstract).
- CLAIM_FAILS_NULL flag fires when z_relative_to_shuffle ≤ +2: currently **True**.

## Invariants

- voynich_word_structured: **True** (z_word<-55.83 <= -3 ⇒ structural)
- voynich_char_structured: **True** (z_char<-8259.21 <= -3 ⇒ structural)
- voynich_glyph_structured: **True** (z_glyph<-6448.69 <= -3 ⇒ structural, extended-EVA-glyph tokens via greedy longest-match)
- plant_passes: **True** (known-answer POSITIVE — pipeline can detect engineered low-cond-H sequence)
- latin_passes: **True** (known-answer POSITIVE — pipeline can detect natural-language-like markov over in-house Latin-style lexicon)
- rho_fails_null: **True** (claim-under-test fails shuffle null if True)

## Verdict: **SEQUENCE_STRUCTURE | CLAIM_FAILS_NULL**

Real-Voynich structure signal present at level FULL; however, the 2025 Dominik Arabic-ρ claim does NOT beat the unigram-preserving shuffle by 2σ on this recomputation. The abstract ρ ≈ 0.82 is not propagated as a finding; re-evaluate Dominik's packaged JSON (which we did NOT bundle) against an external auditor.

STRUCTURE != MESSAGE. These metrics distinguish 'not random noise' from noise, but NOT 'undeciphered language' from 'structured non-linguistic template' at Voynich-corpus sizes. The 2025 Dominik Arabic-ρ claim is held to a shuffle null; the published ρ ≈ 0.82 is NOT propagated as a finding.

---
*G10 Voynich — structure != message.* Conditional entropy + shuffled control + planted Voynichese/Latin + Dominik-ρ null are NECESSARY-not-sufficient for an undeciphered script. No decipherment, no language family, no aliens, no viral-blog-as-truth.

### Forbidden phrases

- `translates to`
- `decodes as`
- `reads as`
- `is Arabic`
- `is language`
- `Voynich translated`
- `Voynich deciphered`
- `Voynich is a`
- `Voynich =`
- `shares roots with`
- `is related to Arabic`
- `is related to Latin`
- `aliens wrote`
- `Dominik's Arabic translation`
- `viral blog`
- `viral decipherment`
- `etymological root of Voynich`
