"""
ingest_cm_corpus.py — Download and build Cypro-Minoan corpus from Corazza 2022
data (sign2vec_d GitHub, context.csv trigrams).

Stance: structure != meaning. No decipherment claims.

Output: data/scripts/cypro_minoan/corpus.json
"""
from __future__ import annotations

import csv
import json
import os
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA_DIR = ROOT / "data" / "scripts" / "cypro_minoan"
OUT_PATH = DATA_DIR / "corpus.json"

CONTEXT_URL = "https://raw.githubusercontent.com/ashmikuz/sign2vec_d/main/data/contexts/context.csv"
LICENSE_URL = "https://raw.githubusercontent.com/ashmikuz/sign2vec_d/main/LICENSE"


def download_csv(url: str, path: Path) -> None:
    print(f"Downloading {url} ...")
    urllib.request.urlretrieve(url, path)
    print(f"  -> {path} ({path.stat().st_size} bytes)")


def is_valid_sign(s: str) -> bool:
    if not s or s == "None" or s == "False":
        return False
    if s in ("boh", "et", "punto", "SPACE"):
        return False
    return True


def normalize_sign(s: str) -> str:
    if s in ("I", "II", "III", "IIII", "IIIIII", "VII", "X", "XXX"):
        return s
    if s in ("CC", "CCC"):
        return s
    return s


def build_corpus(csv_path: Path) -> dict:
    """Parse context.csv trigrams into per-inscription sign sequences."""
    inscriptions: dict[str, dict] = {}
    site_counter: Counter = Counter()
    sign_counter: Counter = Counter()
    raw_tokens: list[str] = []
    clean_tokens: list[str] = []

    with open(csv_path) as f:
        reader = csv.reader(f)
        for row in reader:
            cur = row[1]
            if not cur or cur == "None":
                continue

            parts = cur.split("/")
            if len(parts) < 2:
                continue
            fold = parts[0]
            rest = parts[1]
            segs = rest.split(".")

            if len(segs) < 3:
                continue

            site_code = segs[0]
            sign_raw = segs[-2]
            ins_key = ".".join(segs[:-2])
            line_key = (ins_key, segs[-3] if len(segs) >= 4 else "r00")

            if "_" in sign_raw:
                pos_str, sign_val = sign_raw.split("_", 1)
            else:
                pos_str, sign_val = "0", sign_raw

            raw_tokens.append(sign_val)
            if is_valid_sign(sign_val):
                clean_tokens.append(sign_val)
                nv = normalize_sign(sign_val)
                if nv:
                    sign_counter[nv] += 1

            uid = f"{site_code}/{ins_key}"
            if uid not in inscriptions:
                inscriptions[uid] = {
                    "site": site_code,
                    "inscription": ins_key,
                    "rows": defaultdict(list),
                    "tokens_raw": [],
                }
            inscriptions[uid]["rows"][line_key[1]].append(sign_val)
            inscriptions[uid]["tokens_raw"].append(sign_val)
            site_counter[site_code] += 1

    clean_only: dict[str, list[str]] = {}
    for uid, info in inscriptions.items():
        clean = [s for s in info["tokens_raw"] if is_valid_sign(s)]
        if clean:
            clean_only[uid] = clean

    return {
        "metadata": {
            "n_total_signs_raw": len(raw_tokens),
            "n_total_signs_cleaned": len(clean_tokens),
            "n_inscriptions": len(inscriptions),
            "n_inscriptions_with_clean_data": len(clean_only),
            "n_sites": len(site_counter),
            "n_sign_types_syllabograms": len(
                [s for s in sign_counter if s.isdigit() and len(s) == 3]
            ),
            "n_sign_types_total": len(sign_counter),
            "sites": dict(site_counter.most_common()),
            "top_signs": dict(sign_counter.most_common(30)),
            "source": (
                "Corazza et al. 2022 PLOS ONE (Figshare collection 6095488). "
                "Signs extracted from sign2vec_d/context.csv (CC-BY). "
                "Sign numbering per Corazza consensual graphemes."
            ),
            "paper": (
                "Corazza, M., Tamburini, F., Valério, M., & Ferrara, S. (2022). "
                "Unsupervised deep learning supports reclassification of Bronze age "
                "cypriot writing system. PLOS ONE 17(7): e0269544."
            ),
            "license": "CC BY 4.0 (Corazza et al.) — sign images copyright original publishers.",
            "stance": "structure != meaning. No decipherment claims.",
        },
        "sequences": {
            uid: {
                "tokens": toks,
                "site": uid.split("/")[0],
                "inscription": uid.split("/", 1)[1],
            }
            for uid, toks in clean_only.items()
        },
    }


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    csv_tmp = Path("/tmp/cm_context.csv")
    download_csv(CONTEXT_URL, csv_tmp)

    corpus = build_corpus(csv_tmp)
    OUT_PATH.write_text(json.dumps(corpus, indent=2, ensure_ascii=False))
    print(f"Wrote {OUT_PATH}")
    print(f"  Raw signs: {corpus['metadata']['n_total_signs_raw']}")
    print(f"  Clean signs: {corpus['metadata']['n_total_signs_cleaned']}")
    print(f"  Inscriptions: {corpus['metadata']['n_inscriptions']}")
    print(f"  Sites: {corpus['metadata']['n_sites']}")
    print(f"  Sign types: {corpus['metadata']['n_sign_types_total']}")


if __name__ == "__main__":
    main()
