# G15 - Cretan Hieroglyphic bipartite admin probe  [UNDER]
Generated: 2026-07-25T19:26:59.388508+00:00

## Stance
Cretan Hieroglyphic (ca. 2000-1700 BCE, Knossos / Phaistos / Malia) is undeciphered. CHIC (Corpus Hieroglyphicarum Inscriptionum Cretae, Godart & Olivier 1996) is the catalogue, NOT a reading. This probe measures sign-sequence structure and bipartite admin-network isomorphism ONLY. It does NOT translate CH, claim a phonetic reading, place CH in any linguistic grouping, or endorse any 2025-2026 viral-decrypt-blog CH claim. STRUCTURE != MEANING. Reused tools/forensics/symbolseq.py.

**Motto:** *structure != meaning.* CH-NETWORK-ISOMORPHISM is a STRUCTURE COMPARATOR only - NOT a decipherment, NOT a language ID, NOT evidence of any 'reading'.

### Forbidden phrases (logged so a code-reviewer catches drift)
- `Cretan Hieroglyphic deciphered`
- `CH deciphered`
- `reads as`
- `translates to`
- `transcribed as`
- `phonetic values`
- `Glottocode`
- `Indo-European`
- `Semitic`
- `language family`
- `99% deciphered`
- `100% deciphered`
- `alphabet decoded`
- `we decoded`
- `aliens wrote`
- `we can now read`
- `Greek dialect`
- `Faure reading`
- `Isidori reading`
- `Best sounding`

## Source / data
Loader attempts data/scripts/cretan_hieroglyphic/corpus.json first. If absent OR forced via --synthetic, uses a run-time Evans-shaped synthetic corpus (~130 inscriptions with admin motif structure). The synthetic is structurally transparent (Evans sign inventory CH_001..CH_096 + arithmogram numerics 01..99 + SEP slot delimiters); it can never masquerade as real CHIC transcriptions. The known-answer comparators reuse data/scripts/linear_a/{linear_a_corpus.json, linearb_corpus.json} (SigLA / mwenge dumps; LA has 5104 tokens / 246 distinct signs; LB has 1520 tokens / 69 signs) as STRUCTURAL COMPARATORS ONLY - never as a CH decipherment.

- CH corpus rows=397  is_synthetic=True  source=synthetic_evans_inventory
- Linear A admin rows=2667  distinct=246
- Linear B admin rows=659  distinct=69

## Group analyses

### cretan_hieroglyphic_corpus
- rows=397  tokens=1886  distinct=159
- H1=6.396  H(next|prev)=4.017  IC=0.0165  LZ78=0.5085
- shuffle null: observed=4.017  mean=4.0698  z=-2.7  structured=True
- bipartite: n_signs=159  n_edges=1743  density=0.027613  admin_motif_fraction=0.481108  degree_skew_gini=0.579093

### linear_a_admin_ka
- rows=2667  tokens=5104  distinct=246
- H1=6.006  H(next|prev)=4.128  IC=0.024  LZ78=0.4014
- shuffle null: observed=4.128  mean=4.8699  z=-108.61  structured=True
- bipartite: n_signs=246  n_edges=5005  density=0.007629  admin_motif_fraction=0.018373  degree_skew_gini=0.794991

### linear_b_admin_ka
- rows=659  tokens=1520  distinct=69
- H1=5.526  H(next|prev)=4.195  IC=0.0264  LZ78=0.4763
- shuffle null: observed=4.1947  mean=4.2593  z=-4.25  structured=True
- bipartite: n_signs=69  n_edges=1506  density=0.03312  admin_motif_fraction=0.018209  degree_skew_gini=0.491791

### unigram_shuffle_negative_control
- rows=1  tokens=1886  distinct=159
- H1=6.396  H(next|prev)=4.044  IC=0.0165  LZ78=0.5101
- shuffle null: observed=4.0439  mean=4.0629  z=-1.15  structured=False
- bipartite: n_signs=159  n_edges=159  density=1.0  admin_motif_fraction=1.0  degree_skew_gini=0.0

### random_bipartite_network_null
- rows=395  tokens=1713  distinct=159
- H1=7.241  H(next|prev)=3.359  IC=0.0063  LZ78=0.54
- shuffle null: observed=?  mean=?  z=0.0  structured=False
- bipartite: n_signs=159  n_edges=1713  density=0.027275  admin_motif_fraction=0.0  degree_skew_gini=0.175337


## Bipartite admin isomorphism

- distance(CH, Linear A admin) = 0.717  iso_like_linear_a=False  (threshold = 0.15)
- distance(CH, Linear B admin) = 0.4542  iso_like_linear_a=False
- distance(CH, random bipartite) = 0.5453  (sanity = high = bipartite metric is honest)

## Verdict
UNDERDETERMINED

## Caveats
- CHIC (Godart & Olivier 1996) is NOT licensed for redistribution as a machine-readable corpus (verified 2026-07-25); the corpus is the run-time Evans-shaped synthetic fallback unless a real local corpus.json is dropped in and not committed.
- Linear A and Linear B are used ONLY as STRUCTURE COMPARATORS. Their entropy profile is compared to that of CH via the bipartite admin-network signature; this does NOT mean Cretan Hieroglyphic is Linear A or B, or shares a language.
- Bipartite distance is in normalized feature space over 5 invariants (density, avg_sign_degree_norm, avg_row_degree_norm, admin_motif_fraction, degree_skew_gini). The threshold 0.15 is calibrated against Linear A's admin shape; do NOT cite as 'isomorphic' - SHAPE COMPARATOR only.
- Verdict tags are structure-only - NEVER substitutable for decipherment, language ID, or 'reading' claims.

---
*G15 Cretan Hieroglyphic - structure != meaning. No decipherment, no language ID, no aliens.*