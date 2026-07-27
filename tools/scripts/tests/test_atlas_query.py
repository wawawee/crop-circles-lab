"""Tests for atlas_query / entropy_atlas."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ATLAS = ROOT / "data" / "catalog" / "entropy_atlas.json"
SCHEMA = ROOT / "data" / "catalog" / "anomaly_schema.json"
QUERY = ROOT / "tools" / "scripts" / "atlas_query.py"


def test_atlas_exists_and_has_domains():
    assert ATLAS.exists()
    data = json.loads(ATLAS.read_text())
    assert data["n_domains"] >= 10
    assert len(data["domains"]) == data["n_domains"]
    assert "structure" in data["stance"].lower() or "!=" in data["stance"]


def test_schema_has_verdict_tokens():
    schema = json.loads(SCHEMA.read_text())
    assert "NO_SIGNAL" in schema["verdict_tokens_common"]
    assert "FIXTURE_ONLY" in schema["honesty_flags"]


def test_atlas_query_list():
    r = subprocess.run([sys.executable, str(QUERY), "list"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "indus" in r.stdout


def test_atlas_query_find():
    r = subprocess.run([sys.executable, str(QUERY), "find", "UNDERDETERMINED"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0
    assert "hit" in r.stdout.lower()


def test_atlas_query_get():
    r = subprocess.run([sys.executable, str(QUERY), "get", "voynich"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0
    assert "voynich" in r.stdout


def test_no_forbidden_in_atlas_stance():
    data = json.loads(ATLAS.read_text())
    bad = ("aliens", "deciphered", "new physics proven")
    blob = json.dumps(data).lower()
    for b in bad:
        assert b not in blob


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t(); print("PASS", t.__name__)
        except Exception as e:
            failed += 1; print("FAIL", t.__name__, e)
    print(f"{len(tests)-failed}/{len(tests)} passed")
    raise SystemExit(failed)
