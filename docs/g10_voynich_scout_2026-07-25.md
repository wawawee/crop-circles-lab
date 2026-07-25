# G10 Scout Brief — Voynich morphology (STRUCTURE-ONLY)

> From Cursor explore scout ([Scout Voynich open corpora](b510595f-c939-4507-8de5-99e4dc3f9944)), 2026-07-25.  
> Stance: structure metrics only. Ban “translated / deciphered / Arabic reading.”  
> 2025 Arabic-ρ result = **claim-under-test** + shuffle nulls, not gospel.  
> Reuse `tools/forensics/symbolseq.py`.

---

## 1. Open corpora / dumps (text, no images)

| Corpus | URL | Alphabet | ~Size | License / notes |
|--------|-----|----------|-------|-----------------|
| **ZL3b-n (Zandbergen–Landini)** — preferred | https://www.voynich.nu/data/ZL3b-n.txt | EVA extended | **~402 KB** | Attribute Zandbergen & Landini; MS public domain |
| **IT2a-n (Takahashi / Stolfi)** | https://www.voynich.nu/data/IT2a-n.txt | Basic EVA | **~334 KB** | Takeshi Takahashi |
| **Index + README** | https://www.voynich.nu/data/ · https://www.voynich.nu/data/000_README.txt | — | — | IVTFF 2.0 |
| **HF mirror** | https://huggingface.co/datasets/AncientLanguages/Voynich | multi | **~765 KB** | Same sources |
| **2025 Zenodo Arabic morphology (ρ claim)** | https://doi.org/10.5281/zenodo.17409830 | Takahashi-cleaned + Arabic control | zip **~281 KB** | **CC BY 4.0** — Matthew Dominik |
| **2025 Zenodo Kang lexicon** | https://doi.org/10.5281/zenodo.16762441 | f82r only | tiny | Optional foil; not primary |

**Skip:** Beinecke IIIF images; embargoed Zenodo full datasets; “decryption / English translation” packs.

---

## 2. Text-only fetch?

**Yes.** `curl -O https://www.voynich.nu/data/ZL3b-n.txt` (~402 KB). Dominik zip ~281 KB, no images.

---

## 3. “2025 Arabic ρ claim” (claim-under-test)

- **Cite:** Dominik, M. (2025-10-21). *Structural Convergence Between the Voynich Manuscript and Arabic Root Morphology.* Zenodo. https://doi.org/10.5281/zenodo.17409830 (CC BY 4.0).
- **Abstract claim:** Spearman **ρ ≈ 0.82** vs synthetic Arabic triliteral-root control.
- **Packaged JSON mismatch:** reports ρ ≈ 0.9999 / slope ≈ 0.044 — **does not match abstract**. Recompute with shuffle nulls; do not endorse Arabic reading.

---

## 4. Recommended minimal ingest

**Primary:** `ZL3b-n.txt`

**Parse → symbolseq fields:**
- `words`: lists of EVA glyphs (split `.`-words; strip IVTFF `<>`; `[a:b]` → first)
- `tokens_flat`: flatten glyphs (or words-as-tokens — pick one level)
- `folio_id`: from `<f1r.1,@P0>` → `f1r`

**Do not** lead with Dominik’s pre-filtered `voynich_eva_words.txt` as sole corpus — claim-replication input only.

---

## 5. Known-answer / controls

1. Planted Voynichese-like bigrams → expect structure vs shuffle.
2. Unigram-matched shuffle negative.
3. Latin/Italian control (~same N) — compare magnitude **without** language ID.
4. Dominik ρ vs shuffled family/continuation nulls.
5. Optional: IT vs ZL cross-alphabet sanity.

---

## Mission paste (Minimax M3)

```
G10 Voynich morphology — STRUCTURE_ONLY. Ban: translated/deciphered/Arabic reading.
Branch: feat/g10-voynich-morphology (from latest main).
Ingest: https://www.voynich.nu/data/ZL3b-n.txt (~402KB IVTFF EVA) → data/scripts/voynich/ + README.
Fields: words[[glyph]], tokens_flat, folio_id from <fXr…>.
Reuse tools/forensics/symbolseq.py (cond-H, IC, LZ78, structured_vs_shuffled, repeat_structure).
Claim-under-test ONLY: Dominik 2025 Zenodo 10.5281/zenodo.17409830 (ρ≈0.82 abstract; packaged JSON mismatch) — replicate with shuffle nulls; do not endorse.
Known-answer: plant Voynichese-like bigrams; Latin/Italian control ~same N; unigram shuffle negative.
Verdict: SEQUENCE_STRUCTURE | NO_SIGNAL | UNDERDETERMINED | CLAIM_FAILS_NULL — never “translated”.
Outputs: outputs/voynich/run.json + NOTES.md. Update MISSION_BOARD G10. PR for Cursor. No images. No decipherment.
Do NOT touch radio, BLC1, Amazon, or G9/Indus.
```
