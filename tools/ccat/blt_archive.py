"""Archive BLT lab-report HTML/text from Wayback for lab-data-only cases."""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

UA = "TIN-STUDY-CropCircleResearch/0.1 (personal educational research)"

# Known Wayback snapshots (from earlier CDX)
TARGETS = {
    "edmonton_labreport": "https://web.archive.org/web/20101120084111id_/http://bltresearch.com/labreports/edmonton.php",
    "labreports_index": "https://web.archive.org/web/20090620211016id_/http://www.bltresearch.com/labreports.php",
    "published_index": "https://web.archive.org/web/20090619205918id_/http://www.bltresearch.com/published.php",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", "replace")


def html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    html = re.sub(r"(?is)<br\s*/?>", "\n", html)
    html = re.sub(r"(?is)</p>", "\n\n", html)
    html = re.sub(r"(?is)<[^>]+>", " ", html)
    html = re.sub(r"&nbsp;", " ", html)
    html = re.sub(r"&amp;", "&", html)
    html = re.sub(r"[ \t]+", " ", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


def archive_all(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, url in TARGETS.items():
        try:
            html = fetch(url)
            (out_dir / f"{name}.html").write_text(html, encoding="utf-8")
            text = html_to_text(html)
            (out_dir / f"{name}.txt").write_text(text, encoding="utf-8")
            # keyword sniffs
            keys = ["cherhill", "logan", "eltopia", "iron", "node", "expulsion", "microwave", "edmonton"]
            hits = {k: len(re.findall(k, text, re.I)) for k in keys}
            manifest[name] = {"url": url, "chars": len(text), "keyword_hits": hits, "ok": True}
            print(f"OK {name} chars={len(text)} hits={hits}")
        except Exception as e:  # noqa: BLE001
            manifest[name] = {"url": url, "ok": False, "error": str(e)}
            print(f"FAIL {name}: {e}")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data/reports/blt_wayback"))
    args = ap.parse_args()
    archive_all(args.out)


if __name__ == "__main__":
    main()
