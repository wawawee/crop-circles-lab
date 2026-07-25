"""cipher_negcontrol — classical-cipher NEGATIVE CONTROL on recovered streams (B11).

Expectation for crop-circle bit recoveries: **no** classical cipher cracks to
English. Crabwood (when sampled correctly) is plain 8-bit ASCII; Chilbolton is
a bitmap. A clean crack would be surprising.

Full `matthewdgreen/decipher` needs `scripts/bootstrap.sh` + Rust — optional.
This module is a **native** lightweight screen (Caesar χ², IC, period guess)
so the lab has a documented negative without that toolchain.

Known-answer: Caesar-3 of a short English sentence must recover shift=3.
Negative: near-random bit→ASCII garbage must not yield English-like χ².

CLI:
  python tools/ccat/cipher_negcontrol.py --self-test
  python tools/ccat/cipher_negcontrol.py --from-crabwood outputs/crabwood_bits.json
  python tools/ccat/cipher_negcontrol.py --text "KHOOR..." 
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

# English letter frequencies (approx)
EN_FREQ = {
    "A": 0.08167, "B": 0.01492, "C": 0.02782, "D": 0.04253, "E": 0.12702,
    "F": 0.02228, "G": 0.02015, "H": 0.06094, "I": 0.06966, "J": 0.00153,
    "K": 0.00772, "L": 0.04025, "M": 0.02406, "N": 0.06749, "O": 0.07507,
    "P": 0.01929, "Q": 0.00095, "R": 0.05987, "S": 0.06327, "T": 0.09056,
    "U": 0.02758, "V": 0.00978, "W": 0.02360, "X": 0.00150, "Y": 0.01974,
    "Z": 0.00074,
}
EN_IC = 0.066  # expected index of coincidence for English


def letters_only(s: str) -> str:
    return re.sub(r"[^A-Za-z]", "", s).upper()


def index_of_coincidence(s: str) -> float:
    s = letters_only(s)
    n = len(s)
    if n < 2:
        return 0.0
    counts = Counter(s)
    return sum(c * (c - 1) for c in counts.values()) / (n * (n - 1))


def chi2_english(s: str) -> float:
    s = letters_only(s)
    n = len(s)
    if n == 0:
        return float("inf")
    counts = Counter(s)
    chi = 0.0
    for L, p in EN_FREQ.items():
        exp = p * n
        obs = counts.get(L, 0)
        chi += (obs - exp) ** 2 / exp
    return chi


def caesar_shift(s: str, k: int) -> str:
    """Shift letters by +k (mod 26). Encrypt with +k; decrypt with -k or +(26-k)."""
    out = []
    for ch in s:
        if "A" <= ch <= "Z":
            out.append(chr((ord(ch) - 65 + k) % 26 + 65))
        elif "a" <= ch <= "z":
            out.append(chr((ord(ch) - 97 + k) % 26 + 97))
        else:
            out.append(ch)
    return "".join(out)


def best_caesar(s: str) -> dict:
    """Minimize χ² vs English over decrypt shifts 0..25 (apply −k)."""
    best = None
    rows = []
    for k in range(26):
        plain = caesar_shift(s, -k)
        c2 = chi2_english(plain)
        row = {"shift": k, "chi2": round(c2, 2), "preview": letters_only(plain)[:60]}
        rows.append(row)
        if best is None or c2 < best["chi2"]:
            best = row
    return {"best": best, "all_shifts_top5": sorted(rows, key=lambda r: r["chi2"])[:5]}


def printable_ratio(s: str) -> float:
    if not s:
        return 0.0
    ok = sum(1 for c in s if 32 <= ord(c) < 127)
    return ok / len(s)


def english_like(s: str, *, max_chi2: float = 80.0, min_ic: float = 0.055) -> bool:
    """Loose gate: letter-only stream looks vaguely English."""
    L = letters_only(s)
    if len(L) < 40:
        return False
    return chi2_english(L) <= max_chi2 and index_of_coincidence(L) >= min_ic


def bits_to_ascii_candidates(bitstring: str) -> list[dict]:
    """Interpret 0/1 string as 8-bit ASCII under a few polarities/bit orders."""
    bits = re.sub(r"[^01]", "", bitstring)
    cands = []
    for invert in (False, True):
        b = "".join("1" if ch == "0" else "0" for ch in bits) if invert else bits
        for msb_first in (True, False):
            chars = []
            for i in range(0, len(b) - 7, 8):
                chunk = b[i : i + 8]
                if not msb_first:
                    chunk = chunk[::-1]
                chars.append(chr(int(chunk, 2) % 256))
            text = "".join(chars)
            cands.append({
                "invert": invert,
                "msb_first": msb_first,
                "n_chars": len(text),
                "printable_ratio": round(printable_ratio(text), 3),
                "preview": "".join(c if 32 <= ord(c) < 127 else "." for c in text[:80]),
                "text": text,
            })
    return cands


def analyze_text(label: str, text: str) -> dict:
    L = letters_only(text)
    caesar = best_caesar(text)
    ic = index_of_coincidence(text)
    report = {
        "label": label,
        "n_chars": len(text),
        "n_letters": len(L),
        "printable_ratio": round(printable_ratio(text), 3),
        "ic": round(ic, 4),
        "ic_vs_english": round(ic / EN_IC, 3) if EN_IC else None,
        "chi2_raw": round(chi2_english(text), 2) if L else None,
        "caesar": caesar,
        "english_like_raw": english_like(text),
        "english_like_best_caesar": english_like(caesar_shift(text, -(caesar["best"]["shift"])))
        if caesar["best"] else False,
        "verdict": None,
    }
    if report["english_like_best_caesar"] and report["n_letters"] >= 40:
        report["verdict"] = (
            "UNEXPECTED: Caesar screen found English-like text — investigate "
            "(could be true plaintext ASCII, not a 'cipher crack')"
        )
    elif report["printable_ratio"] > 0.85 and report["english_like_raw"]:
        report["verdict"] = "Looks like plaintext English (not a cipher) — expected for true Crabwood"
    else:
        report["verdict"] = (
            "NEGATIVE CONTROL PASS: no classical Caesar/English hit — "
            "stream does not behave like a monoalphabetic cipher of English"
        )
    return report


def analyze_bitstring(label: str, bits: str) -> dict:
    cands = bits_to_ascii_candidates(bits)
    # score: prefer high printable, then run caesar on letter-rich ones
    scored = []
    for c in cands:
        r = analyze_text(f"{label}|inv={c['invert']}|msb={c['msb_first']}", c["text"])
        r["bit_opts"] = {"invert": c["invert"], "msb_first": c["msb_first"]}
        r["preview"] = c["preview"]
        # drop huge text from JSON
        r.pop("caesar", None)
        r["caesar_best"] = analyze_text("_", c["text"])["caesar"]["best"]
        scored.append(r)
    scored.sort(key=lambda r: (-r["printable_ratio"], r.get("chi2_raw") or 1e9))
    any_hit = any(
        "UNEXPECTED" in (r["verdict"] or "") or "plaintext English" in (r["verdict"] or "")
        for r in scored
    )
    return {
        "label": label,
        "n_bits": len(re.sub(r"[^01]", "", bits)),
        "candidates": scored,
        "best_candidate": scored[0] if scored else None,
        "any_english_like": any_hit,
        "lab_verdict": (
            "SURPRISE — investigate further"
            if any_hit
            else "NO classical English cipher detected (expected for noise / bitmap / bad crop)"
        ),
    }


def grid_to_bits(grid: list[list[int]]) -> str:
    return "".join("1" if int(v) else "0" for row in grid for v in row)


def self_test() -> dict:
    plain = "BEWARE THE EXPECTED SPANISH INQUISITION HOLDS NO CRYPTOGRAPHIC WATER HERE"
    cipher = caesar_shift(plain, 3)
    hit = best_caesar(cipher)
    ok_caesar = hit["best"]["shift"] == 3

    # random-ish bits → should not look English
    import random
    rng = random.Random(0)
    noise_bits = "".join(str(rng.randint(0, 1)) for _ in range(8 * 200))
    noise_rep = analyze_bitstring("noise", noise_bits)
    ok_noise = not noise_rep["any_english_like"]

    # true english as bits (msb)
    eng = "CREATURE OF ASTRONOMY INTERESTS US AND YOU"
    bits = "".join(f"{ord(c):08b}" for c in eng)
    eng_rep = analyze_bitstring("planted_ascii", bits)
    ok_eng = eng_rep["any_english_like"] or eng_rep["best_candidate"]["printable_ratio"] > 0.9

    return {
        "caesar_known_answer": ok_caesar,
        "noise_negative": ok_noise,
        "planted_ascii_detectable": ok_eng,
        "pass": ok_caesar and ok_noise and ok_eng,
        "caesar_best_shift": hit["best"]["shift"],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--text", type=str, default=None)
    ap.add_argument("--from-crabwood", type=Path, default=None)
    ap.add_argument("--from-chilbolton", type=Path, default=None,
                    help="chilbolton_bits_73x23.json or grid json with bits")
    ap.add_argument("--out", type=Path, default=Path("outputs/cipher_negcontrol.json"))
    args = ap.parse_args(argv)

    root = Path(__file__).resolve().parents[2]
    reports: dict = {"caveat": (
        "Native Caesar/IC screen only. Full Decipher (matthewdgreen) optional — "
        "needs Rust bootstrap. Failure to find a cipher is the informative result."
    )}

    if args.self_test:
        st = self_test()
        print(json.dumps(st, indent=2))
        return 0 if st["pass"] else 1

    if args.text:
        reports["text"] = analyze_text("cli_text", args.text)

    if args.from_crabwood:
        data = json.loads(Path(args.from_crabwood).read_text())
        # Prefer disc-crop sweep bits if present; else use best preview as text
        bits = data.get("bits") or data.get("best", {}).get("bits")
        if bits:
            reports["crabwood"] = analyze_bitstring("crabwood", bits)
        else:
            # Reconstruct from preview is weak; use text_preview letters only
            preview = data.get("best", {}).get("text_preview") or ""
            # Also try wheat_closeout bitstream if available
            reports["crabwood_preview_only"] = analyze_text("crabwood_preview", preview)
            wh = root / "outputs" / "wheat_closeout" / "crabwood_bitstream_scan.json"
            if wh.exists():
                w = json.loads(wh.read_text())
                # pull any bitstring-like fields
                reports["crabwood_wheat_scan_meta"] = {
                    k: w[k] for k in w if k in ("best_ber", "best_order", "verdict", "caveat", "best")
                }

    if args.from_chilbolton:
        data = json.loads(Path(args.from_chilbolton).read_text())
        grid = data.get("bits") or data.get("grid")
        if grid and isinstance(grid, list):
            reports["chilbolton"] = analyze_bitstring("chilbolton", grid_to_bits(grid))
        else:
            # bits file may nest differently
            p2 = root / "outputs" / "chilbolton_bits_73x23.json"
            if p2.exists():
                d2 = json.loads(p2.read_text())
                g = d2.get("bits") or d2.get("grid")
                if g:
                    reports["chilbolton"] = analyze_bitstring("chilbolton", grid_to_bits(g))

    # Default lab run if no inputs
    if len(reports) == 1:
        cw = root / "outputs" / "crabwood_bits.json"
        ch = root / "outputs" / "chilbolton_bits_73x23.json"
        if cw.exists():
            data = json.loads(cw.read_text())
            preview = data.get("best", {}).get("text_preview") or ""
            reports["crabwood_preview"] = analyze_text("crabwood_best_preview", preview)
            # Build pseudo-bits from recovered path if n_bits known — skip
        if ch.exists():
            d2 = json.loads(ch.read_text())
            g = d2.get("bits") or d2.get("grid")
            if g:
                reports["chilbolton"] = analyze_bitstring("chilbolton", grid_to_bits(g))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(reports, indent=2))
    notes = root / "outputs" / "cipher_negcontrol_NOTES.md"
    lines = [
        "# B11 — Classical cipher negative control\n",
        reports["caveat"] + "\n",
        "## Results\n",
    ]
    for k, v in reports.items():
        if k == "caveat":
            continue
        if isinstance(v, dict) and "lab_verdict" in v:
            lines.append(f"- **{k}**: {v['lab_verdict']}")
        elif isinstance(v, dict) and "verdict" in v:
            lines.append(f"- **{k}**: {v['verdict']}")
        else:
            lines.append(f"- **{k}**: (see JSON)")
    lines.append(
        "\n## Decipher (optional)\n"
        "PyPI name `decipher` is a *different* package (Forsta surveys). "
        "Use `github.com/matthewdgreen/decipher` + `sh scripts/bootstrap.sh` (Rust). "
        "CLI entrypoint was broken under bare `pip install git+...` without bootstrap "
        "(`ModuleNotFoundError: cli`). Native screen above is sufficient for the lab rule.\n"
    )
    notes.write_text("\n".join(lines) + "\n")
    print(f"wrote {args.out} and {notes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
