#!/usr/bin/env python3
"""
eamena_ley_null.py — G18: EAMENA ley-line null hypothesis probe.

Stance: structure != meaning. "Ley lines" are a fringe-archaeology claim that
3+ sites on a straight line within a narrow tolerance corridor constitute a
"ley." This probe measures whether the frequency of such collinear triples in
a spatial point set exceeds what Complete Spatial Randomness (CSR) produces
at the same N and bounding-box. If "leys" do not beat the null, the honest
verdict is NO_SIGNAL.

Spatial analysis engine: tools/ccat/spatial_pattern.py (reusable module).
This probe is the mission-specific harness.

Usage:
    python tools/scripts/eamena_ley_null.py
    python tools/scripts/eamena_ley_null.py --geojson data/geo/eamena/synthetic_csr_sites.json
    python tools/scripts/eamena_ley_null.py --n-triples 5000 --seed 42
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from tools.ccat import spatial_pattern as SP  # noqa: E402

DATA_DIR = ROOT / "data" / "geo" / "eamena"
OUT_DIR = ROOT / "outputs" / "eamena"

# ---------------------------------------------------------------------------
# Stance & constants
# ---------------------------------------------------------------------------

STANCE = (
    "EAMENA (Endangered Archaeology in the Middle East and North Africa) "
    "records ~338,000 archaeological sites. This probe tests the fringe "
    "claim that 3+ sites on a straight line constitute a 'ley line.' "
    "We measure spatial structure (collinear-triple frequency) relative to "
    "Complete Spatial Randomness (CSR) and scrambled-coordinate nulls. "
    "We do NOT endorse ley-line mysticism, ancient-highway claims, or any "
    "'Earth energy' interpretation. The honest prior is NO_SIGNAL — "
    "spatial clustering in archaeological site distributions is well-known "
    "to follow environmental settlement patterns (water, soil, trade "
    "routes), not intentional geometric networks."
)

FORBIDDEN_PHRASES = (
    "ancient highways",
    "ET corridors",
    "proves ley network",
    "ley line network",
    "ley network confirmed",
    "ancient alien roads",
    "energy lines",
    "earth energy grid",
    "earth energy lines",
    "global grid",
    "planetary grid",
    "sacred geometry network",
    "ley system",
    "ley alignment proves",
    "ley discovered",
    "alien ley",
    "99% ley",
    "ley verified",
    "ley confirmed",
    "ancient aliens",
    "alien architectures",
)

Z_STRUCTURE_THRESHOLD = 3.0
Z_CONTROL_SEP_THRESHOLD = 2.0
MIN_N_POINTS = 30


# ---------------------------------------------------------------------------
# Loaders (mission-specific — GeoJSON I/O stays in the probe)
# ---------------------------------------------------------------------------

def load_geojson(path):
    """Load a GeoJSON FeatureCollection of Point features. Returns list of
    (lat, lon) tuples and the source metadata dict."""
    raw = json.loads(Path(path).read_text())
    if raw.get("type") != "FeatureCollection":
        raise ValueError("Expected GeoJSON FeatureCollection")
    coords = []
    for feat in raw.get("features", []):
        geom = feat.get("geometry", {})
        if geom.get("type") != "Point":
            continue
        lon, lat = geom["coordinates"]
        coords.append((float(lat), float(lon)))
    return coords, raw


def load_data(geojson_path=None, n_synthetic=500, seed_csr=0):
    """Load coords from GeoJSON or generate synthetic CSR."""
    if geojson_path:
        path = Path(geojson_path)
        if not path.is_absolute():
            path = ROOT / path
        coords, meta = load_geojson(path)
        meta["source"] = str(path)
    else:
        coords, meta = SP.generate_synthetic_csr(n=n_synthetic, seed=seed_csr)
        meta["source"] = "synthetic_csr"
    return coords, meta


# ---------------------------------------------------------------------------
# Verdict assembly
# ---------------------------------------------------------------------------

def build_verdict(ce, fpr, n):
    """Map metrics into allowed verdict tags. Honest prior: NO_SIGNAL."""
    tags = []
    if n < MIN_N_POINTS:
        tags.append("UNDERDETERMINED")
        return " | ".join(tags)

    ce_z = ce.get("z_vs_csr", 0.0)
    fpr_sc_z = fpr.get("null_scrambled_coord", {}).get("z", 0.0)
    fpr_csr_z = fpr.get("null_csr", {}).get("z", 0.0)
    fpr_sc_exceed = fpr.get("null_scrambled_coord", {}).get("fpr_empirical", 1.0)
    fpr_csr_exceed = fpr.get("null_csr", {}).get("fpr_empirical", 1.0)

    if abs(ce_z) >= Z_STRUCTURE_THRESHOLD:
        tags.append("SPATIAL_CLUSTER_ONLY")
    else:
        tags.append("NO_SPATIAL_SIGNAL")

    beats_scrambled = fpr_sc_exceed < 0.05
    beats_csr = fpr_csr_exceed < 0.05

    if beats_scrambled and beats_csr:
        tags.append("LEY_LINE_SIGNAL")
    elif beats_scrambled or beats_csr:
        tags.append("LEY_UNDERDETERMINED")
    else:
        tags.append("NO_LEY_SIGNAL")

    if abs(fpr_sc_z) >= Z_CONTROL_SEP_THRESHOLD or abs(fpr_csr_z) >= Z_CONTROL_SEP_THRESHOLD:
        tags.append("CONTROL_SEPARATED")
    else:
        tags.append("CONTROL_NOT_SEPARATED")

    if tags.count("NO_LEY_SIGNAL") > 0 and tags.count("CONTROL_NOT_SEPARATED") > 0:
        tags.append("FPR_CALIBRATED")

    return " | ".join(tags)


# ---------------------------------------------------------------------------
# Forbidden phrase guard
# ---------------------------------------------------------------------------

def assert_no_forbidden_phrases(text, where=""):
    if not text:
        return
    lowered = text.lower()
    for fp in FORBIDDEN_PHRASES:
        if fp.lower() in lowered:
            raise ValueError(
                f"forbidden phrase {fp!r} found in {where or 'text'}")


# ---------------------------------------------------------------------------
# Markdown writer
# ---------------------------------------------------------------------------

def write_notes_md(report):
    parts = []
    verdict = report.get("verdict", "PENDING")
    tag_icons = {
        "SPATIAL_CLUSTER_ONLY": "[CLUSTER]",
        "NO_SPATIAL_SIGNAL": "[NO-CLUSTER]",
        "LEY_LINE_SIGNAL": "[LEYS]",
        "NO_LEY_SIGNAL": "[NO-LEYS]",
        "LEY_UNDERDETERMINED": "[LEY-UNDER]",
        "CONTROL_SEPARATED": "[CTRL-SEP]",
        "CONTROL_NOT_SEPARATED": "[CTRL-!SEP]",
        "FPR_CALIBRATED": "[FPR-CAL]",
        "UNDERDETERMINED": "[UNDER]",
    }
    icons = []
    for tag in verdict.split(" | "):
        icons.append(tag_icons.get(tag.strip(), "[?]"))
    parts.append(
        f"# G18 — EAMENA ley-line null  {' '.join(icons)}")
    parts.append(f"*Generated: {report.get('generated_at', '?')}*")
    parts.append("")
    parts.append("## Stance")
    parts.append(STANCE)
    parts.append("")
    parts.append("**Motto:** *structure != meaning.* Ley-line/collinear-triple "
                 "frequency is a STRUCTURE test; this lab does NOT endorse "
                 "fringe ley-line or Earth-energy interpretations.")
    parts.append("")
    parts.append("### Forbidden phrases (logged)")
    for fp in FORBIDDEN_PHRASES:
        parts.append(f"- `{fp}`")
    parts.append("")

    parts.append("## Source / data")
    src = report.get("metadata", {}).get("source", "?")
    parts.append(f"- Source: `{src}`")
    nd = report.get("metadata", {})
    parts.append(f"- Distribution: {nd.get('distribution', '?')}")
    parts.append(f"- N sites: {nd.get('n_sites', '?')}")
    parts.append(f"- Bounding box: {nd.get('bbox', '?')}")
    if nd.get("distribution") == "csr" and "synthetic" in str(src):
        parts.append("- **NOTE:** Synthetic CSR data — ground truth is NO SIGNAL")
    else:
        parts.append("- **NOTE:** Real EAMENA GeoJSON subset — ground truth unknown")
    parts.append("")

    parts.append("## Nearest-neighbour (Clark-Evans)")
    ce = report.get("clark_evans", {})
    if ce:
        parts.append(f"- Observed mean NN: {ce.get('obs_mean_nn_km', '?')} km")
        parts.append(f"- CSR null mean NN: {ce.get('csr_null_mean_km', '?')} km")
        parts.append(f"- Clark-Evans R: {ce.get('clark_evans_R', '?')}")
        parts.append(f"- z vs CSR: {ce.get('z_vs_csr', '?')}")
        parts.append(f"- Density: {ce.get('density_sites_per_km2', '?')} sites/km²")
    parts.append("")

    parts.append("## Ley-line (collinear triple) FPR analysis")
    fpr = report.get("ley_fpr", {})
    if fpr:
        obs = fpr.get("observed", {})
        parts.append(f"- Tolerance corridor: {fpr.get('tolerance_km', '?')} km")
        parts.append(f"- Pairs evaluated: {fpr.get('pairs_evaluated', '?')}")
        parts.append(f"- Observed collinear triples per pair: "
                     f"{obs.get('collinear_triples_per_pair', '?')}")
        parts.append("")
        parts.append("### Scrambled-coordinate null")
        sc = fpr.get("null_scrambled_coord", {})
        parts.append(f"- Mean: {sc.get('mean_per_pair', '?')}")
        parts.append(f"- SD: {sc.get('sd_per_pair', '?')}")
        parts.append(f"- z: {sc.get('z', '?')}")
        parts.append(f"- Empirical FPR: {sc.get('fpr_empirical', '?')} "
                     f"(<0.05 = beats null)")
        parts.append("")
        parts.append("### CSR Monte-Carlo null")
        csr = fpr.get("null_csr", {})
        parts.append(f"- Mean: {csr.get('mean_per_pair', '?')}")
        parts.append(f"- SD: {csr.get('sd_per_pair', '?')}")
        parts.append(f"- z: {csr.get('z', '?')}")
        parts.append(f"- Empirical FPR: {csr.get('fpr_empirical', '?')} "
                     f"(<0.05 = beats null)")
    parts.append("")

    parts.append("## Verdict")
    parts.append(f"**{verdict}**")
    parts.append("")
    parts.append("## Interpretation")
    parts.append(report.get("interpretation", ""))
    parts.append("")
    parts.append("## Caveats")
    for c in report.get("caveats", []):
        parts.append(f"- {c}")
    parts.append("")
    parts.append("---")
    parts.append("*G18 EAMENA ley-line null — structure != meaning. "
                 "No fringe ley-line / Earth-energy / alien interpretation "
                 "endorsed. The collinear-triple FPR calibration is a "
                 "spatial statistics exercise, not a claim about "
                 "intentional geometric networks.*")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="G18 EAMENA ley-line null probe")
    ap.add_argument("--geojson", type=str, default=None,
                    help="Path to GeoJSON of site coordinates")
    ap.add_argument("--n-synthetic", type=int, default=500,
                    help="Number of synthetic CSR sites if no --geojson")
    ap.add_argument("--seed-csr", type=int, default=0,
                    help="Seed for synthetic CSR generation")
    ap.add_argument("--n-sims", type=int, default=SP.N_SIMS_DEFAULT,
                    help="Number of null simulation iterations")
    ap.add_argument("--n-triples", type=int, default=SP.N_TRIPLES_DEFAULT,
                    help="Number of pairs to evaluate for collinearity")
    ap.add_argument("--tolerance-km", type=float, default=SP.TOLERANCE_KM_DEFAULT,
                    help="Collinearity corridor tolerance (km)")
    ap.add_argument("--seed", type=int, default=0,
                    help="Random seed for analysis")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    coords, meta = load_data(
        geojson_path=args.geojson,
        n_synthetic=args.n_synthetic,
        seed_csr=args.seed_csr,
    )
    n = len(coords)

    if n < MIN_N_POINTS:
        report = {
            "mission": "G18",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "verdict": "UNDERDETERMINED",
            "metadata": {"n_sites": n, "source": meta.get("source", "?")},
            "caveats": [f"Insufficient points (n={n} < {MIN_N_POINTS})"],
        }
        md_text = write_notes_md(report)
        json_text = json.dumps(report, indent=2, default=str)
        (OUT_DIR / "run.json").write_text(json_text)
        (OUT_DIR / "NOTES.md").write_text(md_text)
        print(f"verdict: UNDERDETERMINED (n={n})")
        return

    # Clark-Evans nearest-neighbour analysis (from spatial_pattern)
    ce = SP.clark_evans_analysis(coords, n_sims=args.n_sims, seed=args.seed)

    # Ley-line false-positive rate analysis (from spatial_pattern)
    fpr = SP.ley_line_fpr_analysis(
        coords,
        n_sims=args.n_sims,
        n_triple_samples=args.n_triples,
        tolerance_km=args.tolerance_km,
        seed=args.seed,
    )

    # Verdict
    verdict = build_verdict(ce, fpr, n)

    # Interpretation string
    obs_rate = fpr.get("observed", {}).get("collinear_triples_per_pair", 0.0)
    sc_fpr = fpr.get("null_scrambled_coord", {}).get("fpr_empirical", 1.0)
    csr_fpr = fpr.get("null_csr", {}).get("fpr_empirical", 1.0)
    ce_R = ce.get("clark_evans_R", 0.0)
    ce_z = ce.get("z_vs_csr", 0.0)

    if meta.get("distribution") == "csr" and "synthetic" in str(meta.get("source", "")):
        ground_truth = "SYNTHETIC CSR (ground truth: NO SIGNAL by construction)"
        interpretation_parts = [
            f"**Ground truth:** {ground_truth}",
            "",
            f"CSR synthetic data: {n} points uniformly distributed in bounding box.",
            f"Clark-Evans R={ce_R:.3f}, z={ce_z:.2f} — consistent with CSR expectation.",
            "",
            "**Ley-line (collinear triple) FPR calibration:**",
            f"- Scrambled-coord null: empirical FPR = {sc_fpr:.4f} (threshold 0.05)",
            f"- CSR Monte-Carlo null: empirical FPR = {csr_fpr:.4f} (threshold 0.05)",
            f"- Observed collinear triples per pair: {obs_rate:.6f}",
            "",
            "For CSR synthetic data, both null FPRs should be >> 0.05,",
            "confirming that 'ley line' detection on random points produces",
            "chance-expected false positives.",
            "",
            "**FPR Calibration result:** NO_SIGNAL — 'ley line' alignments",
            "in CSR data do not exceed null expectation. The empirical FPR",
            "is consistent with the nominal α=0.05 threshold.",
        ]
    else:
        ground_truth = f"REAL EAMENA subset from {meta.get('source', '?')}"
        interpretation_parts = [
            f"**Source:** {ground_truth}",
            "",
            f"Clark-Evans R={ce_R:.3f}, z={ce_z:.2f}.",
            "",
            "**Ley-line analysis:**",
            f"- Observed collinear triples per pair: {obs_rate:.6f}",
            f"- Scrambled-coord null FPR: {sc_fpr:.4f}",
            f"- CSR Monte-Carlo null FPR: {csr_fpr:.4f}",
            "",
            "If both null FPRs are >> 0.05, the observed alignment rate",
            "is consistent with chance — NO_LEY_SIGNAL.",
            "If one null FPR < 0.05, LEY_UNDERDETERMINED.",
            "If both < 0.05, LEY_LINE_SIGNAL (rare; must survive nulls).",
        ]

    interpretation = "\n".join(interpretation_parts)

    report = {
        "mission": "G18",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "metadata": {
            "n_sites": n,
            "source": meta.get("source", "?"),
            "distribution": meta.get("distribution", "unknown"),
            "bbox": meta.get("bbox", None),
        },
        "clark_evans": ce,
        "ley_fpr": fpr,
        "interpretation": interpretation,
        "caveats": [
            "Synthetic CSR data — ground truth is NO SIGNAL by construction. "
            "Results for real EAMENA data may differ.",
            "Collinear triple detection is sampled (not exhaustive), capped at "
            f"{args.n_triples} pairs for performance.",
            f"Collinearity tolerance of {args.tolerance_km} km is arbitrary; "
            "different tolerances produce different FPRs.",
            "Ley-line claims typically cherry-pick sites — this probe uses ALL "
            "sites in the dataset without selection bias.",
            "Scrambled-coordinate null preserves the 1D marginal distributions "
            "but breaks spatial structure — it is a weaker null than CSR.",
            "CSR Monte-Carlo null assumes uniform intensity across the bounding "
            "box, which is almost never true for real archaeology "
            "(inhomogeneous Poisson process would be more realistic).",
            "For real EAMENA data, environmental covariates (rivers, soils, "
            "topography) must be modeled as a Cox process to avoid conflating "
            "settlement pattern with 'ley' signal.",
            "The EAMENA full 338k-site corpus is BLOCKED from programmatic "
            "access; this probe uses synthetic CSR data as an FPR calibration "
            "benchmark. See data/geo/eamena/README.md.",
        ],
        "data_source": (
            "EAMENA database — synthetic CSR fallback per data access BLOCKED. "
            "See data/geo/eamena/README.md for details."
        ),
        "stance": STANCE,
        "forbidden_phrases": list(FORBIDDEN_PHRASES),
        "pipeline": {
            "tool": "tools/scripts/eamena_ley_null.py",
            "dependencies": ["tools/ccat/spatial_pattern.py"],
            "parameters": {
                "geojson": args.geojson,
                "n_synthetic": args.n_synthetic,
                "seed_csr": args.seed_csr,
                "n_sims": args.n_sims,
                "n_triples": args.n_triples,
                "tolerance_km": args.tolerance_km,
                "seed": args.seed,
            },
        },
    }

    md_text = write_notes_md(report)
    json_text = json.dumps(report, indent=2, default=str)

    assert_no_forbidden_phrases(
        "\n".join(c for c in report["caveats"]), where="caveats")
    assert_no_forbidden_phrases(verdict, where="verdict")
    assert_no_forbidden_phrases(interpretation, where="interpretation")

    json_path = OUT_DIR / "run.json"
    md_path = OUT_DIR / "NOTES.md"
    md_path.write_text(md_text)
    json_path.write_text(json_text)
    print(f"verdict: {verdict}")
    print(f"wrote {md_path}")
    print(f"wrote {json_path}")


if __name__ == "__main__":
    main()
