# G16 — Meroitic sign-sequence structure probe  🟢
Generated: 2026-07-25T13:18:35.534051+00:00

## Stance
Meroitic script is partially deciphered (the script's syllabic values are mostly known; the language is poorly understood; cf. Rilly 2007, 2010). This probe measures *sign-sequence structure* only — it does NOT translate, decipher beyond published readings, or make 'Meroitic deciphered' claims. STRUCTURE != MESSAGE. Reused tools/forensics/symbolseq.py.

**Motto:** *structure != meaning.* No decipherment beyond published readings. No translation claims.
### Forbidden phrases
- `Meroitic deciphered`
- `translates to`
- `represents`
- `decodes as`
- `shares roots with`
- `crank 99.5%`
- `Ghost License`
- `Lackadaisical Security`
- `99.5% decipherment`
- `aliens wrote`

## Source
Corpus: Joshua-Otten/Meroitic-Corpus (GitHub open, 2025), Otten & Anastasopoulos. No license specified; all rights reserved by default. Sign transliterations scraped from RAMSES Online (ramses.ulg.ac.be). Late Egyptian control: RAMSES Online — Late Egyptian hieratic texts. Both sourced from the same RAMSES database; writing systems differ.

- Meroitic corpus: 18090 inscriptions, 755335 tokens, 1866 distinct signs
- Late Egyptian control: 10013 tokens, 1213 distinct signs

## Group analyses

### meroitic_corpus_ramses
- tokens=755335  distinct=1866  H₁=7.66  IC=0.0168
- H(next|prev)=1.497  LZ78=0.0595
- shuffle null: observed=1.4973  mean=7.3218  z=-11336.3
- top bigrams: [(['yetmdelEwi', 'wEmnitX'], 22060), (['yetmdelEwi', 'aribet'], 21812), (['yetmdelEwi', 'SmlE'], 9367), (['wEmnitX', 'Sklte'], 8462), (['aribet', 'wetemtr'], 5136)]

## Known-answer: royal-name structure

- Sequences containing royal-name tokens: 10357
- Royal-name token stats: {'n_total_tokens': 755335, 'n_royal_name_tokens': 19653, 'pct_royal_name': 2.6}
- shuffled null: observed=1.2372  mean=6.7265  z=-9467.0
- Royal-name sequences MUST show conditional structure vs shuffle (z << -3) if royal-name collocations are real.

## Late Egyptian control (structure comparator)

- tokens=10013  distinct=1213
- H₁=8.02  H(next|prev)=3.226
- shuffle null: observed=3.2263  mean=4.6212  z=-166.51
- Note: Late Egyptian is a KNOWN language (Afro-Asiatic). Its structure signal is a sanity check — NOT evidence that Meroitic is Egyptian.

## Negative control

- Label: unigram_shuffle_negative_control
- tokens=755335  distinct=1866
- shuffle null: observed=7.3212  mean=7.3221  z=-1.41
- A unigram-matched shuffle of Meroitic must NOT light up.

## Verdict: **STRUCTURE_SIGNAL**

- meroitic_corpus_ramses: STRUCTURE_SIGNAL z=-11336.3
- KA royal-name: z=-9467.0 PASS
- Late Egyptian control: z=-166.51 structure_expected
- Negative control: z=-1.41 PASS

Structure != meaning. Entropy and bigram statistics confirm sign-sequence structure distinct from noise, but do NOT constitute decipherment. Meroitic sign values are known; the language remains poorly understood.

## Caveats
1. **Corpus is heterogeneous** — RAMSES scrapings aggregate inscriptions of varying length and quality; no per-inscription metadata (site, medium, date) is available in the open corpus.
2. **Late Egyptian control is small** (~10K tokens vs 755K Meroitic). Structure signal is not directly comparable; the control only confirms that a known-language corpus passes the same test.
3. **Royal-name set is provisional** — based on published vocabularies (Millet, Lobban, Rilly). Not exhaustive.
4. **This is structure analysis, not decipherment.** Entropy and bigram statistics are necessary but not sufficient for identifying language properties.
5. **Meroitic is partially deciphered** — sign values are known; this does not imply the language is understood.

---
*G16 Meroitic — structure != meaning. No translation, no decipherment, no aliens.*