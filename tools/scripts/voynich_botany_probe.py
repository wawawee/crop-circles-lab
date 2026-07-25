#!/usr/bin/env python3
"""
voynich_botany_probe.py — Voynich plant illustrations vs shape/botany controls.

Stance: STRUCTURE != MESSAGE. Shape similarity ≠ species ID ≠ decipherment.
Extends G10 Voynich morphology with a *visual* plant-page probe using CCAT
edge / fractal / symmetry features (same stack as crop-circle forensics).

Default path is offline: generate synthetic plant-like silhouettes + run CCAT.
Real Beinecke IIIF folios + POWO/GBIF matching are documented TODOs.

Outputs:
  outputs/voynich_botany/run.json + NOTES.md

Usage:
    python tools/scripts/voynich_botany_probe.py
    python tools/scripts/voynich_botany_probe.py --demo
    python tools/scripts/voynich_botany_probe.py --dry-run
    python tools/scripts/voynich_botany_probe.py --plants-dir path --controls-dir path
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA_DIR = ROOT / "data" / "scripts" / "voynich" / "plants"
OUT_DIR = ROOT / "outputs" / "voynich_botany"

sys.path.insert(0, str(ROOT))

STANCE = (
    "Voynich plant pages (~herbal section) are undeciphered illustrations. "
    "This probe measures *visual edge/shape structure* via CCAT and compares "
    "candidate pages to synthetic plant-like controls. It does NOT identify "
    "species, endorse New-World plant claims, or decipher the manuscript. "
    "STRUCTURE != MESSAGE."
)

FORBIDDEN_PHRASES = (
    "is sunflower",
    "is capsicum",
    "New World plant proves",
    "Voynich deciphered",
    "species identified as",
    "aliens drew",
)

TODO_NEXT = [
    "Crop illustration regions on Beinecke folios (exclude text / root labels)",
    "Expand POWO/GBIF leaf/habit reference set under botany_controls/real/",
    "Optional: wire --powo-search (Kew POWO API) — rate-limit + attribution required",
    "Optional: Google Lens / reverse-image — commercial ToS; keep offline-first",
]


def _image_paths(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        p for p in directory.iterdir()
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".webp"}
    )


def resolve_plant_dirs(
    plants_dir: Path | None,
    controls_dir: Path | None,
    force_synth: bool = False,
) -> tuple[list[Path], list[Path], dict]:
    """Prefer Beinecke folios/ + real botanical controls when present."""
    folios_dir = DATA_DIR / "folios"
    real_ctrl = DATA_DIR / "botany_controls" / "real"
    meta: dict = {"plants_source": None, "controls_source": None}

    if plants_dir is not None:
        plants = _image_paths(plants_dir)
        meta["plants_source"] = str(plants_dir)
    elif not force_synth and _image_paths(folios_dir):
        plants = _image_paths(folios_dir)
        meta["plants_source"] = str(folios_dir.relative_to(ROOT))
        update_manifest_with_folios(plants)
    else:
        fx = ensure_fixtures(force=force_synth)
        plants = fx["plants"]
        meta["plants_source"] = "synthetic_fixtures"

    if controls_dir is not None:
        controls = _image_paths(controls_dir)
        meta["controls_source"] = str(controls_dir)
    elif not force_synth and _image_paths(real_ctrl):
        controls = _image_paths(real_ctrl)
        meta["controls_source"] = str(real_ctrl.relative_to(ROOT))
    else:
        fx = ensure_fixtures(force=False)
        controls = fx["controls"]
        meta["controls_source"] = "synthetic_controls"

    return plants, controls, meta


def update_manifest_with_folios(plant_paths: list[Path]) -> None:
    """Merge Beinecke folio paths into plants/manifest.json if folios/manifest exists."""
    folios_man = DATA_DIR / "folios" / "manifest.json"
    manifest_path = DATA_DIR / "manifest.json"
    plants = []
    if folios_man.exists():
        fm = json.loads(folios_man.read_text())
        for e in fm.get("folios", []):
            plants.append({
                "folio_id": e.get("folio_id"),
                "path": e.get("path"),
                "source_iiif": e.get("source_iiif"),
                "attribution": e.get("attribution"),
            })
    else:
        for p in plant_paths:
            plants.append({
                "folio_id": p.stem,
                "path": str(p.relative_to(ROOT)) if ROOT in p.resolve().parents else str(p),
            })
    controls = []
    real_ctrl = DATA_DIR / "botany_controls" / "real"
    ctrl_meta = real_ctrl / "DATA_SOURCES.json"
    if ctrl_meta.exists():
        cm = json.loads(ctrl_meta.read_text())
        for c in cm.get("controls", []):
            controls.append({**c, "kind": "pd_botanical_plate"})
    else:
        for p in _image_paths(DATA_DIR / "botany_controls"):
            controls.append({
                "id": p.stem,
                "path": str(p.relative_to(ROOT)),
                "kind": "synthetic_or_local",
            })
    out = {
        "generated_for": "voynich_botany_probe",
        "note": "Beinecke IIIF herbal folio sample + PD botanical controls when present.",
        "iiif_manifest": "https://collections.library.yale.edu/manifests/2002046",
        "catalog": "https://collections.library.yale.edu/catalog/2002046",
        "plants": plants,
        "controls": controls,
        "todos": TODO_NEXT,
    }
    manifest_path.write_text(json.dumps(out, indent=2))


def _require_cv():
    try:
        import cv2  # noqa: F401
        import numpy as np  # noqa: F401
        from tools.ccat.ccat import analyze_image  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            f"voynich_botany_probe needs opencv + numpy + tools.ccat: {exc}"
        ) from exc


def synthesize_plant_fixture(path: Path, kind: str = "voynichish", seed: int = 0) -> Path:
    """Draw a simple plant-like silhouette (stdlib + cv2) for offline CI."""
    import cv2
    import numpy as np

    rng = np.random.default_rng(seed)
    canvas = np.full((320, 240, 3), 245, dtype=np.uint8)
    # stem
    cv2.line(canvas, (120, 300), (120, 140), (40, 90, 40), 3)
    # leaves / lobes
    n_lobes = 5 if kind == "voynichish" else 3
    for i in range(n_lobes):
        ang = -0.6 + i * (1.2 / max(n_lobes - 1, 1))
        if kind == "voynichish":
            ang += float(rng.normal(0, 0.08))
        dx = int(70 * math.sin(ang))
        dy = int(-55 * math.cos(ang))
        pt = (120 + dx, 180 + dy)
        axes = (28 + int(rng.integers(0, 12)), 14 + int(rng.integers(0, 8)))
        cv2.ellipse(canvas, pt, axes, math.degrees(ang) * 40, 0, 360, (30, 110, 50), -1)
        cv2.ellipse(canvas, pt, axes, math.degrees(ang) * 40, 0, 360, (20, 70, 30), 1)
    # flower / head
    if kind.startswith("realish"):
        cv2.circle(canvas, (120, 110), 22, (50, 160, 200), -1)
        cv2.circle(canvas, (120, 110), 10, (20, 80, 140), -1)
    else:
        # irregular “fantasy” head
        pts = np.array(
            [
                [120 + int(18 * math.cos(t)), 105 + int(14 * math.sin(1.7 * t))]
                for t in [i * math.pi / 6 for i in range(12)]
            ],
            dtype=np.int32,
        )
        cv2.fillPoly(canvas, [pts], (90, 70, 140))
    # parchment noise
    noise = rng.integers(0, 18, canvas.shape, dtype=np.uint8)
    canvas = cv2.subtract(canvas, noise)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), canvas)
    return path


def ensure_fixtures(force: bool = False) -> dict:
    """Create demo plant + control images + manifest if missing."""
    fixtures = DATA_DIR / "fixtures"
    controls = DATA_DIR / "botany_controls"
    manifest_path = DATA_DIR / "manifest.json"
    plant_paths = []
    control_paths = []
    for i in range(6):
        p = fixtures / f"synthetic_plant_{i:02d}.png"
        if force or not p.exists():
            synthesize_plant_fixture(p, kind="voynichish", seed=10 + i)
        plant_paths.append(p)
    for i, kind in enumerate(("realish_a", "realish_b", "realish_c", "realish_d")):
        p = controls / f"synthetic_control_{i:02d}.png"
        if force or not p.exists():
            synthesize_plant_fixture(p, kind=kind, seed=100 + i)
        control_paths.append(p)
    manifest = {
        "generated_for": "voynich_botany_probe",
        "note": "Synthetic fixtures until Beinecke IIIF folios are acquired.",
        "plants": [
            {
                "folio_id": f"SYN_P{i:02d}",
                "path": str(p.relative_to(ROOT)),
                "iiif_todo": "https://collections.library.yale.edu/catalog/2002046",
            }
            for i, p in enumerate(plant_paths)
        ],
        "controls": [
            {"id": f"CTRL_{i:02d}", "path": str(p.relative_to(ROOT)), "kind": "synthetic_realish"}
            for i, p in enumerate(control_paths)
        ],
        "todos": TODO_NEXT,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return {"plants": plant_paths, "controls": control_paths, "manifest": manifest}


def feature_vector(res: dict) -> dict:
    sym = res.get("symmetry") or {}
    return {
        "edge_ratio": res.get("edge_pixel_ratio"),
        "fractal_dim": res.get("fractal_dimension"),
        "circles": res.get("circles_detected"),
        "lines": res.get("lines_detected"),
        "intensity_std": res.get("intensity_std"),
        "rot_best": max(
            (v for k, v in sym.items() if k.startswith("rot_")),
            default=0.0,
        ),
        "mirror": sym.get("mirror"),
    }


def _dist(a: dict, b: dict) -> float:
    keys = ("edge_ratio", "fractal_dim", "intensity_std", "rot_best", "mirror")
    s = 0.0
    n = 0
    for k in keys:
        va, vb = a.get(k), b.get(k)
        if va is None or vb is None:
            continue
        s += (float(va) - float(vb)) ** 2
        n += 1
    return math.sqrt(s / n) if n else float("nan")


def analyze_dir(paths: list[Path], label: str) -> list[dict]:
    from tools.ccat.ccat import analyze_image

    out = []
    for p in paths:
        if not p.exists():
            out.append({"id": p.stem, "path": str(p), "error": "missing"})
            continue
        res = analyze_image(p).to_dict()
        feats = feature_vector(res)
        out.append({"id": p.stem, "path": str(p.relative_to(ROOT)) if ROOT in p.parents else str(p),
                    "label": label, "features": feats, "ccat": res})
    return out


def nearest_control(plant: dict, controls: list[dict]) -> dict:
    pf = plant.get("features") or {}
    best = None
    best_d = float("inf")
    for c in controls:
        if "features" not in c:
            continue
        d = _dist(pf, c["features"])
        if d < best_d:
            best_d = d
            best = c
    return {
        "plant_id": plant.get("id"),
        "nearest_control": None if best is None else best.get("id"),
        "distance": None if best is None else round(best_d, 5),
        "interpretation": (
            "Relative shape distance only — not a species ID. "
            "Lower = more similar to synthetic 'realish' control silhouette."
        ),
    }


def run_probe(plants: list[Path], controls: list[Path], dry_run: bool = False) -> dict:
    if dry_run:
        return {
            "label": "dry_run",
            "stance": STANCE,
            "n_plants": len(plants),
            "n_controls": len(controls),
            "plant_paths": [str(p) for p in plants],
            "control_paths": [str(p) for p in controls],
            "todos": TODO_NEXT,
            "verdict": "SCAFFOLD_READY",
            "metrics": {},
            "matches": [],
        }

    plant_rows = analyze_dir(plants, "voynich_or_synth_plant")
    control_rows = analyze_dir(controls, "botany_control")
    matches = [nearest_control(p, control_rows) for p in plant_rows if "features" in p]
    dists = [m["distance"] for m in matches if m.get("distance") is not None]
    mean_d = round(sum(dists) / len(dists), 5) if dists else None
    # Heuristic: if all plants are *closer* to each other than to controls,
    # that is consistent with a constructed / self-similar herbal style —
    # NOT proof of hoax.
    within = []
    for i, a in enumerate(plant_rows):
        if "features" not in a:
            continue
        for b in plant_rows[i + 1 :]:
            if "features" not in b:
                continue
            within.append(_dist(a["features"], b["features"]))
    mean_within = round(sum(within) / len(within), 5) if within else None

    verdict = "UNDERDETERMINED"
    if mean_d is not None and mean_within is not None:
        if mean_within < mean_d * 0.85:
            verdict = "SELF_SIMILAR_VS_CONTROLS"
        elif mean_d < mean_within * 0.85:
            verdict = "CLOSER_TO_CONTROLS"
        else:
            verdict = "NO_CLEAR_SEPARATION"

    return {
        "label": "voynich_botany_ccat",
        "stance": STANCE,
        "forbidden_phrases": list(FORBIDDEN_PHRASES),
        "n_plants": len(plant_rows),
        "n_controls": len(control_rows),
        "plants": [{k: v for k, v in r.items() if k != "ccat"} for r in plant_rows],
        "controls": [{k: v for k, v in r.items() if k != "ccat"} for r in control_rows],
        "matches": matches,
        "metrics": {
            "mean_distance_to_nearest_control": mean_d,
            "mean_pairwise_plant_distance": mean_within,
            "n_pairs_within": len(within),
        },
        "verdict": verdict,
        "todos": TODO_NEXT,
        "caveat": (
            "Self-similarity among Voynich herbal drawings is expected for a "
            "single illustrator style; it is NOT a species match and NOT "
            "evidence of hoax vs botanical realism by itself. "
            "Beinecke IIIF pages (when used) are whole-folio scans — crop "
            "illustration regions for cleaner shape matching."
        ),
        "tools_used": ["ccat.analyze_image", "voynich_botany_probe"],
    }


def write_notes(report: dict) -> str:
    lines = [
        "# Voynich botany probe (plant pages × CCAT)\n",
        f"Generated: {report.get('generated_at', '?')}\n",
        "## Stance\n",
        report.get("stance", STANCE),
        "",
        "**Motto:** structure ≠ message. Shape ≠ species ≠ decipherment.\n",
        "## Metrics\n",
        f"- N plants: **{report.get('n_plants', 0)}**  controls: **{report.get('n_controls', 0)}**",
        f"- Mean distance → nearest control: **{report.get('metrics', {}).get('mean_distance_to_nearest_control')}**",
        f"- Mean pairwise plant distance: **{report.get('metrics', {}).get('mean_pairwise_plant_distance')}**",
        "",
        f"## Verdict: **{report.get('verdict', '?')}**\n",
        report.get("caveat", ""),
        "",
        "### Nearest-control matches\n",
    ]
    for m in report.get("matches", [])[:12]:
        lines.append(
            f"- `{m.get('plant_id')}` → `{m.get('nearest_control')}`  d={m.get('distance')}"
        )
    lines.append("\n## TODOs (real botany)\n")
    for t in report.get("todos", TODO_NEXT):
        lines.append(f"- [ ] {t}")
    lines.append("\n---\n*Voynich botany — Hecklefish quick win. No species claims.*")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Voynich plant pages vs botany/shape controls (CCAT wrapper)."
    )
    ap.add_argument("--demo", action="store_true",
                    help="Force synthetic fixtures (ignore Beinecke folios).")
    ap.add_argument("--dry-run", action="store_true", help="List paths / plan; skip CCAT.")
    ap.add_argument("--plants-dir", type=Path, default=None)
    ap.add_argument("--controls-dir", type=Path, default=None)
    ap.add_argument("--out-json", type=Path, default=None)
    ap.add_argument("--out-md", type=Path, default=None)
    a = ap.parse_args()

    _require_cv()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    plants, controls, src_meta = resolve_plant_dirs(
        a.plants_dir, a.controls_dir, force_synth=a.demo
    )

    report = run_probe(plants, controls, dry_run=a.dry_run)
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["plants_source"] = src_meta.get("plants_source")
    report["controls_source"] = src_meta.get("controls_source")
    if src_meta.get("plants_source") and "folios" in str(src_meta.get("plants_source")):
        report["caveat"] = (
            "Beinecke IIIF herbal folio sample (whole pages). "
            + report.get("caveat", "")
        )

    out_json = a.out_json or OUT_DIR / "run.json"
    out_md = a.out_md or OUT_DIR / "NOTES.md"
    out_json.write_text(json.dumps(report, indent=2, default=str))
    out_md.write_text(write_notes(report))
    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    print(f"verdict={report.get('verdict')} metrics={report.get('metrics')}")
    print(f"sources plants={src_meta.get('plants_source')} controls={src_meta.get('controls_source')}")


if __name__ == "__main__":
    main()
