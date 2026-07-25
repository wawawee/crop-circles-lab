#!/usr/bin/env python3
"""
atlas_query.py — query / print the Language Entropy Atlas.

Usage:
    python tools/scripts/atlas_query.py
    python tools/scripts/atlas_query.py --id indus_mohenjodaro
    python tools/scripts/atlas_query.py --domain script --sort z
    python tools/scripts/atlas_query.py --nearest H1=6.3 H2=2.8
    python tools/scripts/atlas_query.py --refresh-from-outputs   # TODO stub
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ATLAS_PATH = ROOT / "data" / "catalog" / "entropy_atlas.json"


def load_atlas(path: Path = ATLAS_PATH) -> dict:
    return json.loads(path.read_text())


def print_table(entries: list[dict]) -> None:
    hdr = f"{'id':28} {'N':>8} {'H1':>7} {'H2':>7} {'IC':>8} {'z':>10}  status"
    print(hdr)
    print("-" * len(hdr))
    for e in entries:
        def fmt(x, w, prec=3):
            if x is None:
                return f"{'?':>{w}}"
            if isinstance(x, float):
                return f"{x:>{w}.{prec}f}"
            return f"{x:>{w}}"
        print(
            f"{e.get('id', '?'):28} "
            f"{fmt(e.get('N'), 8, 0)} "
            f"{fmt(e.get('H1'), 7)} "
            f"{fmt(e.get('H2'), 7)} "
            f"{fmt(e.get('IC'), 8, 4)} "
            f"{fmt(e.get('z_vs_shuffle'), 10, 2)}  "
            f"{e.get('status', '')}"
        )


def nearest(entries: list[dict], h1: float | None, h2: float | None, k: int = 5) -> list[dict]:
    scored = []
    for e in entries:
        if e.get("H1") is None and h1 is not None:
            continue
        d = 0.0
        n = 0
        if h1 is not None and e.get("H1") is not None:
            d += (float(e["H1"]) - h1) ** 2
            n += 1
        if h2 is not None and e.get("H2") is not None:
            d += (float(e["H2"]) - h2) ** 2
            n += 1
        if n == 0:
            continue
        scored.append((math.sqrt(d / n), e))
    scored.sort(key=lambda t: t[0])
    return [{"distance": round(d, 4), **e} for d, e in scored[:k]]


def main() -> None:
    ap = argparse.ArgumentParser(description="Query entropy_atlas.json")
    ap.add_argument("--atlas", type=Path, default=ATLAS_PATH)
    ap.add_argument("--id", default=None)
    ap.add_argument("--domain", default=None)
    ap.add_argument("--sort", choices=["id", "z", "H1", "N"], default="id")
    ap.add_argument("--nearest", nargs="*", default=None,
                    help="e.g. --nearest H1=6.3 H2=2.8")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--refresh-from-outputs", action="store_true",
                    help="TODO: rebuild atlas from outputs/*/run.json")
    a = ap.parse_args()

    if a.refresh_from_outputs:
        print(
            "TODO: atlas refresh from outputs not implemented yet. "
            "Edit data/catalog/entropy_atlas.json manually or extend this stub.",
            file=sys.stderr,
        )
        sys.exit(2)

    atlas = load_atlas(a.atlas)
    entries = list(atlas.get("entries", []))

    if a.id:
        entries = [e for e in entries if e.get("id") == a.id]
    if a.domain:
        entries = [e for e in entries if e.get("domain") == a.domain]

    if a.nearest is not None:
        kv = {}
        for item in a.nearest:
            if "=" not in item:
                continue
            k, v = item.split("=", 1)
            kv[k.strip()] = float(v)
        hits = nearest(entries, kv.get("H1"), kv.get("H2"))
        if a.json:
            print(json.dumps(hits, indent=2))
        else:
            print_table(hits)
        return

    reverse = a.sort == "z"
    key = a.sort if a.sort != "z" else "z_vs_shuffle"

    def sort_key(e):
        v = e.get(key)
        if v is None:
            return float("inf") if not reverse else float("-inf")
        return v

    entries.sort(key=sort_key, reverse=reverse)

    if a.json:
        print(json.dumps(entries, indent=2))
    else:
        print_table(entries)
        print(f"\n{len(entries)} entries from {a.atlas.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
