#!/usr/bin/env python3
"""atlas_query — query data/catalog/entropy_atlas.json (structure != meaning).

Usage:
  python tools/scripts/atlas_query.py list
  python tools/scripts/atlas_query.py find UNDERDETERMINED
  python tools/scripts/atlas_query.py get indus
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATLAS = ROOT / "data" / "catalog" / "entropy_atlas.json"


def load() -> dict:
    return json.loads(ATLAS.read_text())


def cmd_list(_: argparse.Namespace) -> int:
    atlas = load()
    for e in atlas["domains"]:
        v = e.get("verdict")
        print(f"{e['domain']:22s} {v}")
    print(f"\n{atlas['n_domains']} domains — {atlas['generated_at']}")
    return 0


def cmd_find(args: argparse.Namespace) -> int:
    needle = args.token.upper()
    atlas = load()
    hits = [e for e in atlas["domains"] if needle in str(e.get("verdict", "")).upper()]
    for e in hits:
        print(f"{e['domain']:22s} {e.get('verdict')}")
    print(f"{len(hits)} hit(s)")
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    atlas = load()
    for e in atlas["domains"]:
        if e["domain"] == args.domain:
            print(json.dumps(e, indent=2, ensure_ascii=False))
            return 0
    print(f"not found: {args.domain}", file=sys.stderr)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.set_defaults(func=cmd_list)
    p = sub.add_parser("find"); p.add_argument("token"); p.set_defaults(func=cmd_find)
    p = sub.add_parser("get"); p.add_argument("domain"); p.set_defaults(func=cmd_get)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
