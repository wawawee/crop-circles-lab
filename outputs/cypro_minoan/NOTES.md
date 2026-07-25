# G11 — Cypro-Minoan sign-sequence structure probe  🟢
Generated: 2026-07-25T12:21:45.236140+00:00

## Stance
Cypro-Minoan (ca. 1500-1100 BCE, Cyprus / Ugarit) script(s) is/are undeciphered. This probe measures *sign-sequence structure* only — it does NOT translate, decipher, or claim language family. STRUCTURE != MESSAGE. Reused tools/forensics/symbolseq.py.

**Motto:** *structure != message.* No decipherment, no language-family claim.
### Forbidden phrases
- `translates to`
- `represents`
- `decodes as`
- `shares roots with`
- `is related to`
- `CM is Linear A`
- `aliens wrote`

## Source
Corazza et al. 2022 PLOS ONE (Figshare 6095488), CC BY 4.0. Sign sequences from sign2vec_d context.csv (CC-BY). Sign images copyright original publishers.

- 563 inscriptions, 2848 tokens, 108 distinct signs
- 39 sites; tablet: 1722 signs, other: 1126 signs

## Group analyses

### full_corpus
- tokens=2848  distinct=108  H₁=5.656  IC=0.0438
- H(next|prev)=4.032  LZ78=0.4301
- shuffle null: observed=4.0316  mean=4.419  z=-28.95
- top bigrams: [(['I', '102'], 43), (['I', '038'], 35), (['023', 'I'], 33), (['097', 'I'], 32), (['013', 'I'], 29)]

### tablet
- tokens=1722  distinct=80  H₁=5.313  IC=0.0584
- H(next|prev)=3.581  LZ78=0.428
- shuffle null: observed=3.5809  mean=4.0492  z=-26.69
- top bigrams: [(['I', '102'], 38), (['I', '038'], 32), (['013', 'I'], 25), (['075', 'I'], 22), (['082', 'I'], 19)]

### other_media
- tokens=1126  distinct=85  H₁=5.588  IC=0.033
- H(next|prev)=3.561  LZ78=0.4805
- shuffle null: observed=3.5612  mean=3.8288  z=-12.04
- top bigrams: [(['023', 'I'], 20), (['097', 'I'], 19), (['I', '104'], 9), (['I', '027'], 8), (['097', '023'], 8)]

### site_CM_ENKO
- tokens=2093  distinct=93  H₁=5.483  IC=0.0498
- H(next|prev)=3.803  LZ78=0.4338
- shuffle null: observed=3.8026  mean=4.2023  z=-26.42
- top bigrams: [(['I', '102'], 38), (['I', '038'], 31), (['097', 'I'], 28), (['013', 'I'], 28), (['082', 'I'], 22)]

### site_CM_RASH
- tokens=304  distinct=52  H₁=4.969  IC=0.0481
- H(next|prev)=2.311  LZ78=0.5164
- shuffle null: observed=2.3107  mean=2.7943  z=-11.99
- top bigrams: [(['051', '028'], 11), (['028', 'I'], 11), (['I', '051'], 9), (['P', '102'], 6), (['100', 'I'], 6)]

### site_CM_KALA
- tokens=170  distinct=49  H₁=5.001  IC=0.0424
- H(next|prev)=1.991  LZ78=0.6059
- shuffle null: observed=1.9905  mean=2.1561  z=-3.86
- top bigrams: [(['091', 'I'], 6), (['I', '104'], 5), (['104', '024'], 4), (['024', '091'], 3), (['086', 'I'], 3)]

## Cross-group Jaccard overlap

- full_corpus vs other_media: J=0.787  shared=85  A-only=23  B-only=0
- full_corpus vs site_CM_ENKO: J=0.8611  shared=93  A-only=15  B-only=0
- full_corpus vs site_CM_KALA: J=0.4537  shared=49  A-only=59  B-only=0
- full_corpus vs site_CM_RASH: J=0.4815  shared=52  A-only=56  B-only=0
- full_corpus vs tablet: J=0.7407  shared=80  A-only=28  B-only=0
- other_media vs site_CM_ENKO: J=0.798  shared=79  A-only=6  B-only=14
- other_media vs site_CM_KALA: J=0.5765  shared=49  A-only=36  B-only=0
- other_media vs site_CM_RASH: J=0.4421  shared=42  A-only=43  B-only=10
- other_media vs tablet: J=0.5278  shared=57  A-only=28  B-only=23
- site_CM_ENKO vs site_CM_KALA: J=0.5106  shared=48  A-only=45  B-only=1
- site_CM_ENKO vs site_CM_RASH: J=0.3942  shared=41  A-only=52  B-only=11
- site_CM_ENKO vs tablet: J=0.6635  shared=69  A-only=24  B-only=11
- site_CM_KALA vs site_CM_RASH: J=0.4225  shared=30  A-only=19  B-only=22
- site_CM_KALA vs tablet: J=0.4176  shared=38  A-only=11  B-only=42
- site_CM_RASH vs tablet: J=0.65  shared=52  A-only=0  B-only=28
- (full pairwise matrix: 861 pairs in run.json)

## Cross-group shared-sign analysis

- Signs shared across all groups: 57
  ['001', '002', '004', '005', '006', '007', '008', '009', '011', '012', '013', '017', '019', '021', '023']...
- Signs unique to tablet: 23
- Signs unique to other media: 28

## Known-answer: synthetic scribal variants

- Label: synthetic_scribal_variants_ka
- tokens=272  distinct=43
- H₁=4.629  H(next|prev)=1.94
- shuffle null: observed=1.9404  mean=2.807  z=-19.31
- Scribal variants (shared sign set, bigram structure) MUST show strong conditional structure vs shuffle (z << -3).

## Negative control

- Label: unigram_shuffle_negative_control
- tokens=2848  distinct=108
- shuffle null: observed=4.4271  mean=4.4191  z=0.6
- A shuffled version of the real data must NOT light up as structured.

## Verdict

**STRUCTURE_SIGNAL | MEDIA_DRIVEN_ALLOGRAPHY**

- full_corpus: STRUCTURE_SIGNAL z=-28.95
- tablet: STRUCTURE_SIGNAL z=-26.69
- other_media: STRUCTURE_SIGNAL z=-12.04
- site_CM_ENKO: STRUCTURE_SIGNAL z=-26.42
- site_CM_RASH: STRUCTURE_SIGNAL z=-11.99
- site_CM_KALA: STRUCTURE_SIGNAL z=-3.86
- Cross-group Jaccard mean: 0.0649
- Tablet vs other shared: 0.5278
- KA scribal variants: z=-19.31 PASS

## Caveats

1. **Corpus reconstructed from trigram-sliding-window data** — sign sequences are read from individual cropped sign image paths, not from authoritative transliteration tables. Directionality (LTR/RTL/boustrophedon) may not be preserved.
2. **CM1/CM2/CM3 labels not directly available** in the open sign2vec_d data. Site-based and medium-based labels used as proxies.
3. **Token normalization** strips underscore-suffixed variants (e.g., '046_' → '046'). These are paleographic variants, not distinct graphemes, per the paper's argument.
4. **Short sequences predominate** — many inscriptions carry only 1–5 signs. Longer tablet sequences drive most structural signal.
5. **No decipherment, language ID, or script classification.**