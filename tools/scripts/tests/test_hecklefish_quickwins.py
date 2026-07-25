"""Smoke tests for Hecklefish quick-win probes."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]  # tests → scripts → tools → crop-circles
PY = sys.executable


def _run(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PY, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_indus_west_help() -> None:
    r = _run(["tools/scripts/indus_west_negcontrol.py", "--help"])
    assert r.returncode == 0, f"stdout={r.stdout!r}\nstderr={r.stderr!r}"
    text = (r.stdout or "") + (r.stderr or "")
    assert "West" in text or "west" in text.lower()


def test_indus_west_synthetic_runs() -> None:
    with tempfile.TemporaryDirectory() as td:
        out_j = Path(td) / "run.json"
        out_m = Path(td) / "NOTES.md"
        r = _run([
            "tools/scripts/indus_west_negcontrol.py",
            "--synthetic",
            "--west", str(ROOT / "data/scripts/indus/west/west_plaintext_fixture.json"),
            "--west-stream", "recode_like",
            "--n-shuffles", "50",
            "--also-english-ka",
            "--out-json", str(out_j),
            "--out-md", str(out_m),
        ])
        assert r.returncode == 0, r.stdout + r.stderr
        report = json.loads(out_j.read_text())
        assert "profiles" in report
        assert report["verdict"] in {
            "CLAIM_LOOKS_LIKE_RECODE",
            "CLAIM_LOOKS_LANGUAGE_LIKE",
            "NO_CLEAR_SEPARATION",
            "UNDERDETERMINED",
        }
        assert out_m.exists()


def test_indus_west_real_json_loads() -> None:
    real = ROOT / "data/scripts/indus/west/west_plaintext_real.json"
    if not real.exists():
        return
    with tempfile.TemporaryDirectory() as td:
        out_j = Path(td) / "run.json"
        out_m = Path(td) / "NOTES.md"
        r = _run([
            "tools/scripts/indus_west_negcontrol.py",
            "--synthetic",
            "--west", str(real),
            "--west-stream", "auto",
            "--n-shuffles", "30",
            "--out-json", str(out_j),
            "--out-md", str(out_m),
        ])
        assert r.returncode == 0, r.stdout + r.stderr
        report = json.loads(out_j.read_text())
        assert report.get("west_stream") == "claim_plaintext"
        assert report.get("using_real_claim_file") is True


def test_voynich_botany_help() -> None:
    r = _run(["tools/scripts/voynich_botany_probe.py", "--help"])
    assert r.returncode == 0


def test_voynich_botany_dry_run() -> None:
    with tempfile.TemporaryDirectory() as td:
        out_j = Path(td) / "run.json"
        out_m = Path(td) / "NOTES.md"
        r = _run([
            "tools/scripts/voynich_botany_probe.py",
            "--demo",
            "--dry-run",
            "--out-json", str(out_j),
            "--out-md", str(out_m),
        ], timeout=60)
        assert r.returncode == 0, r.stdout + r.stderr
        report = json.loads(out_j.read_text())
        assert report["verdict"] == "SCAFFOLD_READY"


def test_voynich_folios_present_or_skip() -> None:
    folios = ROOT / "data/scripts/voynich/plants/folios"
    jpgs = list(folios.glob("f*.jpg")) if folios.is_dir() else []
    if len(jpgs) < 3:
        return
    man = folios / "manifest.json"
    assert man.exists()
    data = json.loads(man.read_text())
    assert data.get("n_folios", 0) >= 3
    assert "iiif_manifest" in data


def test_atlas_query_runs() -> None:
    r = _run(["tools/scripts/atlas_query.py", "--domain", "script"])
    assert r.returncode == 0, r.stderr
    assert "indus" in r.stdout.lower() or "phaistos" in r.stdout.lower()


def test_anomaly_schema_and_store_exist() -> None:
    schema = json.loads((ROOT / "data/catalog/anomaly_schema.json").read_text())
    store = json.loads((ROOT / "data/catalog/anomalies.json").read_text())
    assert "properties" in schema
    assert "anomaly_id" in schema["required"]
    assert len(store["anomalies"]) >= 3
    for a in store["anomalies"]:
        for key in schema["required"]:
            assert key in a, f"missing {key} in {a.get('anomaly_id')}"


def test_stubs_dry_run() -> None:
    for script in (
        "tools/scripts/rongorongo_refrain.py",
        "tools/astro/goebekli_taurid.py",
        "tools/geo/lidar_negative_probe.py",
        "tools/scripts/stubs/alpha_variation_probe.py",
        "tools/scripts/stubs/vasco_missing.py",
    ):
        r = _run([script, "--dry-run"])
        assert r.returncode == 0, f"{script}: {r.stderr}"


if __name__ == "__main__":
    test_indus_west_help()
    test_indus_west_synthetic_runs()
    test_indus_west_real_json_loads()
    test_voynich_botany_help()
    test_voynich_botany_dry_run()
    test_voynich_folios_present_or_skip()
    test_atlas_query_runs()
    test_anomaly_schema_and_store_exist()
    test_stubs_dry_run()
    print("all hecklefish smoke tests passed")
