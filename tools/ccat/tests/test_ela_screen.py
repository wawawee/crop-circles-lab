"""Tests for ela_screen known-answer splice separation."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "ccat"))

import ela_screen as E  # noqa: E402


def test_splice_raises_block_std(tmp_path: Path | None = None):
    tmp = Path(tmp_path) if tmp_path else ROOT / "outputs" / "forensics" / "ela" / "_pytest_tmp"
    clean, spliced = E.make_known_answer_pair(tmp)
    r0 = E.screen_one(clean, tmp / "c", quality=90)
    r1 = E.screen_one(spliced, tmp / "s", quality=90, control_block_std=r0["stats"]["block_mean_std"])
    assert r1["stats"]["block_mean_std"] > r0["stats"]["block_mean_std"] * 1.15, (
        r0["stats"],
        r1["stats"],
    )


if __name__ == "__main__":
    test_splice_raises_block_std()
    print("PASS test_splice_raises_block_std")
