"""
ingest_corpus.py — Fetch Indus corpus from mayig/indus-valley-script-corpus (MIT).
Output: data/scripts/indus/corpus.json — per-artifact sign sequences.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
BASE = "https://raw.githubusercontent.com/mayig/indus-valley-script-corpus/main/corpus"

SUBDIRS = ["m001_m099", "m100_m199"]

def fetch_json(url: str) -> dict | list | None:
    try:
        with urlopen(url, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  WARN: {e}", file=sys.stderr)
        return None

def list_files(subdir: str) -> list[str]:
    api = f"https://api.github.com/repos/mayig/indus-valley-script-corpus/contents/corpus/{subdir}"
    data = fetch_json(api)
    if not isinstance(data, list):
        return []
    return [e["name"] for e in data if e["name"].endswith(".json")]

def main():
    corpus: dict[str, list[list[str]]] = {}
    n_artifacts = 0
    n_sequences = 0
    n_signs = 0
    signs_seen: set[str] = set()

    for subdir in SUBDIRS:
        files = list_files(subdir)
        print(f"{subdir}: {len(files)} files")
        for fname in sorted(files):
            url = f"{BASE}/{subdir}/{fname}"
            data = fetch_json(url)
            if not isinstance(data, list):
                continue
            for side in data:
                if not isinstance(side, dict):
                    continue
                aid = side.get("id", f"{fname}_{data.index(side)}")
                graphemes = side.get("graphemes", [])
                seq = [g["id"] for g in graphemes if isinstance(g, dict) and "id" in g]
                if seq:
                    corpus[aid] = seq
                    n_sequences += 1
                    n_signs += len(seq)
                    signs_seen.update(seq)
            n_artifacts += 1

    output = {
        "source": "mayig/indus-valley-script-corpus (MIT/Apache 2.0)",
        "attribution": "Parpola, A. et al. Corpus of Indus Seals and Inscriptions (CISI). Digitised by mayig.",
        "license": "MIT / Apache 2.0",
        "n_artifacts": n_artifacts,
        "n_sequences": n_sequences,
        "n_signs": n_signs,
        "n_distinct_signs": len(signs_seen),
        "encoding": "Parpola sign numbers (P001–Pxxx)",
        "sequences": corpus,
    }
    out_path = HERE / "corpus.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\nWrote {out_path}")
    print(f"  {n_artifacts} artifacts, {n_sequences} sequences, {n_signs} signs, {len(signs_seen)} distinct")

if __name__ == "__main__":
    main()
