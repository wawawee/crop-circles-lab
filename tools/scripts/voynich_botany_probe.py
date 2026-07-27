"""
voynich_botany_probe.py — G10++ mission: Voynich plant pages × CCAT shape metrics.

Stance: SHAPE STRUCTURE ≠ HERBAL ID / DECIPHERMENT. This probe measures
geometric shape properties (edge ratio, fractal dimension, symmetry, line/circle
counts) of SYNTHETIC BOTANICAL drawings against null controls. It does NOT
identify species, decipher plant labels, or claim herbal correspondences.

Reuses tools.ccat for ALL shape metrics (read-only). No real Beinecke IIIF or
POWO images are processed — those are optional and BLOCKED_IIIF if attempted.

Outputs:
  outputs/voynich_botany/run.json + NOTES.md

Usage:
    # Full pipeline (synthetic only)
    python tools/scripts/voynich_botany_probe.py

    # Override output paths
    python tools/scripts/voynich_botany_probe.py \
        --out-json outputs/voynich_botany/run.json \
        --out-md outputs/voynich_botany/NOTES.md
"""
from __future__ import annotations

import json
import math
import random as rnd
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA_DIR = ROOT / "data" / "voynich_botany"
OUT_DIR = ROOT / "outputs" / "voynich_botany"

sys.path.insert(0, str(ROOT))
from tools.ccat.ccat import (  # noqa: E402
    box_counting_dimension,
    detect_circles,
    detect_lines,
    edge_ratio,
    mirror_symmetry_score,
    rotational_symmetry_score,
)

# -----------------------------------------------------------------------------
# Stance / forbidden phrases
# -----------------------------------------------------------------------------

BOTANY_STANCE = (
    "G10++ probes SHAPE STRUCTURE of synthetic botanical drawings against "
    "synthetic null controls. It does NOT identify plant species, decipher "
    "herbarium labels, make pharma claims, or map Voynich plant pages "
    "to real-world flora. All images are synthetic (generated programmatically). "
    "No Beinecke IIIF or POWO data is processed. "
    "STRUCTURE != HERBAL ID / DECIPHERMENT."
)

FORBIDDEN_PHRASES: tuple[str, ...] = (
    "identifies as",
    "is a known plant",
    "herbal identification",
    "species identified",
    "botanical match",
    "corresponds to",
    "this plant is",
    "use as medicine",
    "Voynich decoded",
    "translates to",
    "deciphered",
    "herbal remedy",
    "ethnobotanical",
    "plant species found",
    "aliens",
    "extraterrestrial botany",
    "healing property",
    "pharma application",
)

# Prose paths scanned by forbidden-phrase guard.
PROSE_KEY_PATHS: tuple[tuple[str, ...], ...] = (
    ("stance",),
    ("caveat",),
    ("verdict_block", "notes"),
)

# -----------------------------------------------------------------------------
# Synthetic botanical image generator
# -----------------------------------------------------------------------------

IMG_SIZE = 300


def _draw_leaf(
    img: np.ndarray, cx: int, cy: int, angle_deg: int,
    length: int, rng: np.random.RandomState,
) -> None:
    axes = (max(length // 4, 2), max(length // 2, 2))
    cv2.ellipse(img, (cx, cy), axes, angle_deg, 0, 360, 0, -1)
    dx = int(length // 2 * math.cos(math.radians(angle_deg)))
    dy = int(length // 2 * math.sin(math.radians(angle_deg)))
    cv2.line(img, (cx, cy), (cx + dx, cy + dy), 80, 1)


def _draw_roots(
    img: np.ndarray, x: int, y: int, rng: np.random.RandomState,
) -> None:
    n_roots = rng.randint(3, 6)
    for _ in range(n_roots):
        side = rng.choice([-1, 1])
        end_x = x + side * rng.randint(15, 50)
        end_y = y + rng.randint(5, 25)
        cv2.line(img, (x, y), (end_x, end_y), 0, 2)
        branch_x = end_x + side * rng.randint(5, 15)
        branch_y = end_y + rng.randint(3, 10)
        cv2.line(img, (end_x, end_y), (branch_x, branch_y), 40, 1)


def _draw_flower(
    img: np.ndarray, cx: int, cy: int, rng: np.random.RandomState,
) -> None:
    cv2.circle(img, (cx, cy), 12, 0, -1)
    cv2.circle(img, (cx, cy), 8, 200, -1)
    n_petals = rng.randint(5, 9)
    for i in range(n_petals):
        a = 360.0 * i / n_petals
        px = cx + int(16 * math.cos(math.radians(a)))
        py = cy + int(16 * math.sin(math.radians(a)))
        cv2.ellipse(img, (px, py), (6, 10), int(a), 0, 360, 0, -1)


def make_plant_image(size: int = IMG_SIZE, seed: int = 0) -> np.ndarray:
    rng = np.random.RandomState(seed)
    img = np.ones((size, size), dtype=np.uint8) * 240
    stem_x = size // 2
    stem_bottom = size - 25
    stem_top = 35
    cv2.line(img, (stem_x, stem_bottom), (stem_x, stem_top), 0, 3)
    n_pairs = rng.randint(2, 5)
    for i in range(n_pairs):
        y = stem_top + 20 + i * (stem_bottom - stem_top - 30) // max(n_pairs, 1)
        angle = rng.randint(20, 55)
        leaf_len = rng.randint(18, 32)
        _draw_leaf(img, stem_x - 5, y, -angle, leaf_len, rng)
        _draw_leaf(img, stem_x + 5, y, 180 - angle, leaf_len, rng)
    _draw_roots(img, stem_x, stem_bottom, rng)
    _draw_flower(img, stem_x, stem_top + 5, rng)
    return img


# -----------------------------------------------------------------------------
# Null control generators
# -----------------------------------------------------------------------------


def make_noise_image(size: int = IMG_SIZE, seed: int = 0) -> np.ndarray:
    rng = np.random.RandomState(seed)
    return rng.randint(0, 256, (size, size), dtype=np.uint8)


def make_scrambled_plant(size: int = IMG_SIZE, seed: int = 0) -> np.ndarray:
    """Shuffle pixel positions of a plant image — preserves histogram."""
    plant = make_plant_image(size, seed=seed)
    flat = plant.ravel()
    rng = np.random.RandomState(seed + 1000)
    rng.shuffle(flat)
    return flat.reshape(size, size)


def make_random_shapes(size: int = IMG_SIZE, seed: int = 0) -> np.ndarray:
    rng = np.random.RandomState(seed)
    img = np.ones((size, size), dtype=np.uint8) * 240
    n_shapes = rng.randint(8, 20)
    for _ in range(n_shapes):
        kind = rng.randint(0, 3)
        cx = rng.randint(20, size - 20)
        cy = rng.randint(20, size - 20)
        if kind == 0:
            radius = rng.randint(5, 25)
            cv2.circle(img, (cx, cy), radius, 0, -1)
        elif kind == 1:
            lx = rng.randint(10, 50)
            cv2.ellipse(
                img, (cx, cy), (lx // 2, lx), rng.randint(0, 180),
                0, 360, 0, -1,
            )
        else:
            x2 = rng.randint(10, size - 10)
            y2 = rng.randint(10, size - 10)
            cv2.line(img, (cx, cy), (x2, y2), 0, 2)
    return img


def make_plant_silhouette(size: int = IMG_SIZE, seed: int = 0) -> np.ndarray:
    """Convex hull silhouette of plant — preserves outline, removes internals."""
    plant = make_plant_image(size, seed=seed)
    binary = (plant < 128).astype(np.uint8) * 255
    pts = np.argwhere(binary > 0)
    if len(pts) < 3:
        return plant
    hull = cv2.convexHull(pts[:, ::-1])
    silhouette = np.ones((size, size), dtype=np.uint8) * 240
    cv2.fillPoly(silhouette, [hull], 0)
    return silhouette


# -----------------------------------------------------------------------------
# CCAT metrics runner
# -----------------------------------------------------------------------------

METRIC_LABELS: tuple[str, ...] = (
    "edge_pixel_ratio",
    "fractal_dimension",
    "lines_detected",
    "circles_detected",
    "mirror_symmetry",
    "rotational_symmetry_2fold",
)


def compute_ccat_metrics(gray: np.ndarray) -> dict[str, float]:
    ratio, edges = edge_ratio(gray)
    fd = box_counting_dimension(edges)
    lines = detect_lines(edges)
    circles = detect_circles(gray)
    mirror = mirror_symmetry_score(gray)
    rot2 = rotational_symmetry_score(gray, 2)
    return {
        "edge_pixel_ratio": round(float(ratio), 5),
        "fractal_dimension": round(float(fd), 4) if fd is not None else None,
        "lines_detected": int(lines),
        "circles_detected": int(circles),
        "mirror_symmetry": round(float(mirror), 4),
        "rotational_symmetry_2fold": round(float(rot2), 4),
    }


def generate_and_analyze(
    generator, n: int, label: str, seed_offset: int = 0,
) -> list[dict]:
    results: list[dict] = []
    for i in range(n):
        img = generator(seed=seed_offset + i)
        metrics = compute_ccat_metrics(img)
        metrics["sample_id"] = f"{label}_{i}"
        results.append(metrics)
    return results


# -----------------------------------------------------------------------------
# Statistical comparison
# -----------------------------------------------------------------------------


def metric_array(
    samples: list[dict], key: str,
) -> list[float]:
    return [s[key] for s in samples if s.get(key) is not None]


def compare_ka_vs_null(
    ka: list[dict], null: list[dict],
) -> dict:
    """For each metric, compute Cohen's d and z-score between KA and null.
    Positive d/z means KA > null on that metric."""
    comparisons: dict[str, dict] = {}
    for metric in METRIC_LABELS:
        ka_vals = metric_array(ka, metric)
        null_vals = metric_array(null, metric)
        if not ka_vals or not null_vals:
            comparisons[metric] = {
                "ka_mean": None, "null_mean": None,
                "ka_std": None, "null_std": None,
                "cohens_d": None, "z_score": None,
                "separates": None,
            }
            continue
        ka_mean = float(np.mean(ka_vals))
        null_mean = float(np.mean(null_vals))
        ka_std = float(np.std(ka_vals, ddof=1)) if len(ka_vals) > 1 else 0.0
        null_std = float(np.std(null_vals, ddof=1)) if len(null_vals) > 1 else 0.0
        pooled = math.sqrt(
            (ka_std ** 2 + null_std ** 2) / 2.0
        ) if (ka_std > 0 or null_std > 0) else 1.0
        cohens_d = (ka_mean - null_mean) / pooled if pooled > 1e-12 else 0.0
        se = math.sqrt(
            (ka_std ** 2 / len(ka_vals)) + (null_std ** 2 / len(null_vals))
        )
        if se < 1e-12:
            z_score = 999.0 if abs(ka_mean - null_mean) > 1e-12 else 0.0
        else:
            z_score = (ka_mean - null_mean) / se
        separates = abs(z_score) > 2.0
        comparisons[metric] = {
            "ka_mean": round(ka_mean, 4),
            "null_mean": round(null_mean, 4),
            "ka_std": round(ka_std, 4),
            "null_std": round(null_std, 4),
            "cohens_d": round(cohens_d, 4),
            "z_score": round(z_score, 2),
            "separates": separates,
        }
    return comparisons


# -----------------------------------------------------------------------------
# Verdict
# -----------------------------------------------------------------------------

SEPARATION_THRESHOLD = 2  # metrics needed with |z| > 2


def compute_verdict(
    comparisons: dict,
    plant_vs_noise: dict,
    plant_vs_scramble: dict,
    plant_vs_shapes: dict,
    plant_vs_silhouette: dict,
) -> dict:
    n_separate_noise = sum(
        1 for v in plant_vs_noise.values() if v.get("separates")
    )
    n_separate_scramble = sum(
        1 for v in plant_vs_scramble.values() if v.get("separates")
    )
    n_separate_shapes = sum(
        1 for v in plant_vs_shapes.values() if v.get("separates")
    )
    n_separate_silhouette = sum(
        1 for v in plant_vs_silhouette.values() if v.get("separates")
    )
    all_separations = [
        n_separate_noise, n_separate_scramble,
        n_separate_shapes, n_separate_silhouette,
    ]
    total_metrics = len(METRIC_LABELS)
    verdict_parts: list[str] = ["FIXTURE_ONLY"]
    notes: list[str] = []
    notes.append("All data is synthetic — no real IIIF or POWO images processed.")
    scores = {
        "noise": n_separate_noise,
        "scramble": n_separate_scramble,
        "random_shapes": n_separate_shapes,
        "silhouette": n_separate_silhouette,
    }
    if max(all_separations) >= SEPARATION_THRESHOLD:
        n_total = sum(all_separations)
        if n_total >= 8:
            verdict_parts.append("SHAPE_STRUCTURE")
            notes.append(
                f"Plants separate from controls on {n_total}/{4 * total_metrics} "
                f"metric×control pairs. Strong shape structure signal."
            )
        elif n_total >= 4:
            verdict_parts.append("SHAPE_STRUCTURE")
            notes.append(
                f"Plants separate from controls on {n_total}/{4 * total_metrics} "
                f"metric×control pairs. Moderate shape structure signal."
            )
        else:
            verdict_parts.append("UNDERDETERMINED")
            notes.append(
                f"Marginal separation — only {n_total}/{4 * total_metrics} "
                f"metric×control pairs separate."
            )
    else:
        verdict_parts.append("NO_SIGNAL")
        notes.append(
            "Synthetic botanical images do NOT separate from any null control "
            "on any CCAT shape metric. Pipeline may be insensitive or the "
            "synthetic generator too simple."
        )
    for ctrl_name, n_sep in [
        ("noise", n_separate_noise),
        ("scramble", n_separate_scramble),
        ("random_shapes", n_separate_shapes),
        ("silhouette", n_separate_silhouette),
    ]:
        notes.append(
            f"{ctrl_name}: {n_sep}/{total_metrics} metrics separate (|z|>2)."
        )
    verdict = " | ".join(verdict_parts)
    return {
        "verdict": verdict,
        "separation_counts": scores,
        "total_metrics": total_metrics,
        "threshold": SEPARATION_THRESHOLD,
        "notes": " ".join(notes),
    }


# -----------------------------------------------------------------------------
# Forbidden-phrase guard
# -----------------------------------------------------------------------------


def _walk_prose_strings(d: dict) -> list[str]:
    out: list[str] = []
    for path in PROSE_KEY_PATHS:
        node = d
        try:
            for k in path:
                node = node[k]
            if isinstance(node, str) and node:
                out.append(node)
        except (KeyError, TypeError):
            continue
    return out


def assert_no_forbidden_phrases_prose(report: dict, where: str) -> None:
    for prose in _walk_prose_strings(report):
        assert_no_forbidden_phrases(prose, where=where)


def assert_no_forbidden_phrases(text: str, where: str = "") -> None:
    if not text:
        return
    lower = text.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase.lower() in lower:
            raise ValueError(
                f"forbidden phrase {phrase!r} appeared in {where}; "
                f"this run must not contain {phrase!r}"
            )


# -----------------------------------------------------------------------------
# Main pipeline
# -----------------------------------------------------------------------------


def run_botany_probe(
    n_plants: int = 30,
    n_nulls: int = 30,
    seed: int = 0,
) -> dict:
    plant_samples = generate_and_analyze(
        make_plant_image, n_plants, "plant", seed_offset=seed,
    )
    noise_samples = generate_and_analyze(
        make_noise_image, n_nulls, "noise", seed_offset=seed + 100,
    )
    scramble_samples = generate_and_analyze(
        make_scrambled_plant, n_nulls, "scramble", seed_offset=seed + 200,
    )
    shapes_samples = generate_and_analyze(
        make_random_shapes, n_nulls, "shapes", seed_offset=seed + 300,
    )
    silhouette_samples = generate_and_analyze(
        make_plant_silhouette, n_nulls, "silhouette", seed_offset=seed + 400,
    )
    plant_vs_noise = compare_ka_vs_null(plant_samples, noise_samples)
    plant_vs_scramble = compare_ka_vs_null(plant_samples, scramble_samples)
    plant_vs_shapes = compare_ka_vs_null(plant_samples, shapes_samples)
    plant_vs_silhouette = compare_ka_vs_null(plant_samples, silhouette_samples)
    comparisons = {
        "vs_noise": plant_vs_noise,
        "vs_scramble": plant_vs_scramble,
        "vs_random_shapes": plant_vs_shapes,
        "vs_silhouette": plant_vs_silhouette,
    }
    verdict_block = compute_verdict(
        comparisons, plant_vs_noise, plant_vs_scramble,
        plant_vs_shapes, plant_vs_silhouette,
    )
    setup = {
        "n_plants": n_plants,
        "n_nulls_per_control": n_nulls,
        "image_size": IMG_SIZE,
        "control_types": [
            "noise", "scramble", "random_shapes", "silhouette",
        ],
        "iiif_fetch_attempted": False,
        "iiif_status": "NEVER_ATTEMPTED",
        "powo_fetch_attempted": False,
        "powo_status": "NEVER_ATTEMPTED",
        "generator_seed": seed,
    }
    report: dict = {
        "mission_id": "G10++",
        "probe": "tools/scripts/voynich_botany_probe.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_source": {
            "type": "synthetic",
            "path": "data/voynich_botany/",
            "note": (
                "All images generated programmatically. No real Beinecke IIIF "
                "or POWO data. Synthetic controls only."
            ),
        },
        "synthetic_setup": setup,
        "metrics_tested": list(METRIC_LABELS),
        "plant_samples": [
            {k: v for k, v in s.items() if k != "sample_id"}
            for s in plant_samples
        ],
        "nulls": {
            "noise": [
                {k: v for k, v in s.items() if k != "sample_id"}
                for s in noise_samples
            ],
            "scramble": [
                {k: v for k, v in s.items() if k != "sample_id"}
                for s in scramble_samples
            ],
            "random_shapes": [
                {k: v for k, v in s.items() if k != "sample_id"}
                for s in shapes_samples
            ],
            "silhouette": [
                {k: v for k, v in s.items() if k != "sample_id"}
                for s in silhouette_samples
            ],
        },
        "comparisons": comparisons,
        "verdict_block": verdict_block,
        "stance": BOTANY_STANCE,
        "forbidden_phrases": list(FORBIDDEN_PHRASES),
        "caveat": (
            "All results are on SYNTHETIC botanical images. Shape structure "
            "in synthetic plants vs null controls does NOT imply real plant "
            "pages contain similar structure. CCAT metrics may not transfer "
            "to ink-on-parchment botanical drawings. "
            "STRUCTURE != HERBAL ID / DECIPHERMENT. "
            "No real Beinecke IIIF or POWO data was processed (NEVER_ATTEMPTED)."
        ),
    }
    assert_no_forbidden_phrases_prose(
        report, where="run_botany_probe",
    )
    return report


# -----------------------------------------------------------------------------
# NOTES.md writer
# -----------------------------------------------------------------------------


def write_notes_md(report: dict) -> str:
    vb = report.get("verdict_block", {})
    verdict_str = vb.get("verdict", "NO_SIGNAL")
    if "SHAPE_STRUCTURE" in verdict_str:
        icon = "\U0001f7e2"
    elif "UNDERDETERMINED" in verdict_str:
        icon = "\U0001f7e1"
    else:
        icon = "\U0001f534"
    parts: list[str] = []
    parts.append(f"# G10++ — Voynich plant pages × CCAT shape metrics  {icon}")
    parts.append(f"Generated: {report.get('generated_at', '?')}")
    parts.append("")
    parts.append("## Stance")
    parts.append(report["stance"])
    parts.append("")
    parts.append(
        "**Motto:** *structure != herbal ID / decipherment.* "
        "No species identification, no medicinal claims, no alien botany."
    )
    parts.append("")
    parts.append("## Data")
    parts.append("")
    parts.append(f"- **Type:** SYNTHETIC (all images generated programmatically)")
    parts.append(f"- **Real IIIF fetch:** NEVER_ATTEMPTED")
    parts.append(f"- **POWO fetch:** NEVER_ATTEMPTED")
    parts.append(f"- **Path:** `data/voynich_botany/`")
    parts.append("")
    parts.append("## Synthetic setup")
    setup = report.get("synthetic_setup", {})
    parts.append(f"- N plants (KA): {setup.get('n_plants', '?')}")
    parts.append(f"- N per null control: {setup.get('n_nulls_per_control', '?')}")
    parts.append(f"- Image size: {setup.get('image_size', '?')}×{setup.get('image_size', '?')}")
    parts.append(f"- Controls: {', '.join(setup.get('control_types', []))}")
    parts.append(f"- Generator seed: {setup.get('generator_seed', '?')}")
    parts.append("")
    parts.append("## Metrics tested")
    for m in METRIC_LABELS:
        parts.append(f"- {m}")
    parts.append("")
    parts.append("## Comparisons (KA plants vs null)")
    comparisons = report.get("comparisons", {})
    for ctrl_name, comp in comparisons.items():
        parts.append(f"")
        parts.append(f"### {ctrl_name}")
        parts.append(f"| Metric | KA mean | Null mean | Cohen's d | z-score | Separates? |")
        parts.append(f"|--------|---------|-----------|-----------|---------|------------|")
        for metric, vals in comp.items():
            sep = "\u2713" if vals.get("separates") else "\u2717"
            d_str = str(vals.get("cohens_d", "N/A")) if vals.get("cohens_d") is not None else "N/A"
            z_str = str(vals.get("z_score", "N/A")) if vals.get("z_score") is not None else "N/A"
            parts.append(
                f"| {metric} | {vals.get('ka_mean', 'N/A')} | "
                f"{vals.get('null_mean', 'N/A')} | {d_str} | {z_str} | {sep} |"
            )
    parts.append("")
    parts.append("## Verdict")
    parts.append(f"**{verdict_str}**")
    parts.append("")
    parts.append(vb.get("notes", ""))
    parts.append("")
    parts.append("## Caveats")
    parts.append(report.get("caveat", ""))
    parts.append("")
    parts.append("### Forbidden phrases (logged so a code-reviewer catches drift)")
    for phrase in FORBIDDEN_PHRASES:
        parts.append(f"- `{phrase}`")
    parts.append("")
    parts.append("---")
    parts.append(
        "*G10++ — Synthetic botanical shape structure via CCAT. "
        "No real Voynich page images were processed.*"
    )
    return "\n".join(parts)


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="G10++ Voynich plant pages × CCAT shape metrics",
    )
    parser.add_argument(
        "--out-json", type=Path, default=OUT_DIR / "run.json",
    )
    parser.add_argument(
        "--out-md", type=Path, default=OUT_DIR / "NOTES.md",
    )
    parser.add_argument(
        "--n-plants", type=int, default=30,
        help="Number of synthetic plant images (default: 30)",
    )
    parser.add_argument(
        "--n-nulls", type=int, default=30,
        help="Number per null control (default: 30)",
    )
    parser.add_argument(
        "--seed", type=int, default=0,
        help="Random seed (default: 0)",
    )
    args = parser.parse_args()
    report = run_botany_probe(
        n_plants=args.n_plants,
        n_nulls=args.n_nulls,
        seed=args.seed,
    )
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2))
    print(f"Wrote {args.out_json}")
    md = write_notes_md(report)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(md)
    print(f"Wrote {args.out_md}")
    vb = report.get("verdict_block", {})
    print(f"\nVerdict: {vb.get('verdict', '?')}")
    sep = vb.get("separation_counts", {})
    print(f"  Separation: noise={sep.get('noise', '?')}  "
          f"scramble={sep.get('scramble', '?')}  "
          f"shapes={sep.get('random_shapes', '?')}  "
          f"silhouette={sep.get('silhouette', '?')}")


if __name__ == "__main__":
    main()
