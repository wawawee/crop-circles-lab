# `data/bio/` — tiny public FASTA slices for N1 probe runs

This directory contains **small** real NCBI public-domain sequences used by
`tools/bio/bio_probe.py` for end-to-end N1 exercises. They are intentionally
caps (NCBI NC_045512.2 head, ~4 kb; NT_187395.1 chr22 slice, ~3 kb) so the
repo stays *small* and the probe runs without a 250 MB chr1 download.

## Files

| File | Accession | Length | Purpose |
|---|---|---|---|
| `SARS_COV_2_NC_045512.2_head.fasta` | NC_045512.2 | 4 000 bp head | test the probe on a real coding-dense RNA virus genome (the entire viral genome of SARS-CoV-2 is ~99% coding, so intergenic comparison is N/A here) |
| `HUMAN_chr22_3kb.fasta` | NT_187395.1 | 3 000 bp head | test on a real mostly-intronic/intergenic human contig slice -- comparable to "junk" regions against which low-entropy coding signatures would stand out |

### Sources

- **NC_045512.2**: Wuhan-Hu-1 isolate SARS-CoV-2 complete genome. Public domain (GenBank release).
- **NT_187395.1**: Homo sapiens chromosome 22 genomic scaffold (GRCh38.p14 alternate).

Both were fetched on **2026-07-25** via NCBI E-utilities
(`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi`). No
redistribution problem -- these are U.S. public-domain sequence records.

### Refetch commands (for reproducibility / asset refresh)

```bash
mkdir -p crop-circles/data/bio && cd crop-circles/data/bio
curl -sS "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nucleotide&id=NC_045512.2&rettype=fasta&retmode=text&seq_start=1&seq_stop=4000" \
     -o SARS_COV_2_NC_045512.2_head.fasta
curl -sS "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nucleotide&id=NT_187395.1&rettype=fasta&retmode=text&seq_start=1&seq_stop=3000" \
     -o HUMAN_chr22_3kb.fasta
```

## Negative control rule (from ROADMAP_BEYOND_WHEAT.md and MISSION_BOARD.md)

Every N1 exercise runs **the same** `bio_probe.py` pipeline on a
**composition-preserving** Fisher-Yates shuffle of the same sequence. Because
the shuffle preserves all letter counts, it preserves GC% by construction -- no
separate GC-matching step is required. The headline test statistic is
`Δ_window_mean_H = real_window_H_mean − shuffled_window_H_mean`. A negative
value (real < shuffled) is the expected biological signature of a real
genome; a clearly positive value would be the surprise worth follow-up.

## Honest framing

These assets are short enough that **coding-vs-intergenic** comparison is
not robust without external BED/GFF annotation files (out of scope for N1).
We intentionally do NOT pretend to have done an annotation-aware comparison
in the N1 deliverables. A future N1+ follow-up that adds a UCSC knownGenes
BED file is the right way to enable that comparison.
