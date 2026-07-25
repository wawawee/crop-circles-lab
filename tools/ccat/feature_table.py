"""B6 — exploratory feature table + lightweight known-hoax vs candidate probe.

Builds outputs/feature_table.csv over a curated free corpus (priority formations
+ Chualar control). Uses CCAT metrics + B3 stubble fraction + B4 mask-first
blob count. Optional sklearn logistic / RF is reported as exploratory only
(tiny N — do not treat as authenticity oracle).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "forensics"))

from ccat import analyze_image  # noqa: E402
from circle_extract import extract_from_image  # noqa: E402
from preprocess import crop_stubble_mask, morphological_cleanup  # noqa: E402


# Free on-disk set: known control + priority aerials that exist locally.
DEFAULT_CORPUS = [
    {"id": "chualar-2013-nvidia", "label": "known_hoax", "file": "chualar_2013_nvidia_hoax.png"},
    {"id": "stonehenge-julia-1996", "label": "candidate", "file": "julia_set_1996_tt_oh.jpg"},
    {"id": "edmonton-1999", "label": "candidate", "file": "edmonton_1999.png"},
    {"id": "eltopia-1998", "label": "candidate", "file": "eltopia_1998_iccra.png"},
    {"id": "allington-cube-1999", "label": "candidate", "file": "allington_cube_1999_tt.jpg"},
    {"id": "milk-hill-2001", "label": "candidate", "file": "milk_hill_galaxy_2001_tt_oh.jpg"},
    {"id": "chilbolton-message-2001", "label": "candidate", "file": "chilbolton_message_2001_tt.jpg"},
    {"id": "crabwood-2002", "label": "candidate", "file": "crabwood_2002_tt_oh2.jpg"},
    {"id": "crabwood-disc-crop", "label": "candidate", "file": "crabwood_2002_disc_crop.png"},
    {"id": "dna-1996", "label": "candidate", "file": "dna_alton_barnes_1996_tt.jpg"},
    {"id": "barbury-pi-2008", "label": "candidate", "file": "barbury_pi_2008.jpg"},
    {"id": "diessenhofen-2008", "label": "candidate", "file": "aerial_view_of_the_crop_circle_in_diessenhofen_15.07.2008_16-44-41.jpg"},
]


def shannon_entropy(gray: np.ndarray) -> float:
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel()
    p = hist / max(hist.sum(), 1.0)
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def features_for(path: Path, formation_id: str, label: str) -> dict:
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        return {"id": formation_id, "file": path.name, "label": label, "error": "unreadable"}
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    res = analyze_image(path)
    # B4 mask-first blobs (adaptive tends to recover Julia better)
    blobs_otsu, _ = extract_from_image(path, method="otsu", min_circularity=0.45, min_radius=2.0)
    blobs_ad, _ = extract_from_image(path, method="adaptive", min_circularity=0.35, min_radius=3.0)
    stubble = morphological_cleanup(crop_stubble_mask(bgr), 1, 1)
    circ_mean = float(np.mean([c["circularity"] for c in blobs_ad])) if blobs_ad else float("nan")
    lines = max(res.lines_detected, 1)
    return {
        "id": formation_id,
        "file": path.name,
        "label": label,
        "width": res.width,
        "height": res.height,
        "edge_ratio": round(res.edge_pixel_ratio, 5),
        "entropy": round(shannon_entropy(gray), 4),
        "fractal_dim": None if res.fractal_dimension is None else round(res.fractal_dimension, 4),
        "hough_circles": res.circles_detected,
        "blob_circles_otsu": len(blobs_otsu),
        "blob_circles_adaptive": len(blobs_ad),
        "blob_circularity_mean": None if math.isnan(circ_mean) else round(circ_mean, 4),
        "lines": res.lines_detected,
        "circle_line_ratio": round(len(blobs_ad) / lines, 4),
        "stubble_fraction": round(float(stubble.mean()), 4),
        "rot_best": round(max(v for k, v in res.symmetry.items() if k.startswith("rot_")), 4),
        "mirror": None if res.symmetry.get("mirror") is None else round(res.symmetry["mirror"], 4),
        "mean_intensity": round(res.mean_intensity, 2),
    }


def run_classifier(df: pd.DataFrame) -> dict:
    """Exploratory only — N is tiny."""
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import LeaveOneOut
        from sklearn.metrics import accuracy_score
    except ImportError as e:
        return {"error": f"sklearn unavailable: {e}"}

    feat_cols = [
        "edge_ratio",
        "entropy",
        "fractal_dim",
        "blob_circles_adaptive",
        "circle_line_ratio",
        "stubble_fraction",
        "rot_best",
        "mirror",
    ]
    work = df.dropna(subset=feat_cols + ["label"]).copy()
    if len(work) < 4 or work["label"].nunique() < 2:
        return {"error": "not enough labeled rows", "n": len(work)}

    X = work[feat_cols].to_numpy(dtype=float)
    y = (work["label"] == "known_hoax").astype(int).to_numpy()
    # Only one known_hoax → LOO will be fragile; still report train-fit + LOO if possible
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    out: dict = {
        "n_rows": int(len(work)),
        "n_hoax": int(y.sum()),
        "n_candidate": int((y == 0).sum()),
        "features": feat_cols,
        "caveat": (
            "Exploratory only. One known-hoax control and tiny N — "
            "accuracies are anecdotal, not an authenticity test."
        ),
    }

    lr = LogisticRegression(max_iter=500, class_weight="balanced")
    rf = RandomForestClassifier(n_estimators=100, random_state=0, class_weight="balanced")
    lr.fit(Xs, y)
    rf.fit(Xs, y)
    out["train_acc_logistic"] = round(float(accuracy_score(y, lr.predict(Xs))), 3)
    out["train_acc_rf"] = round(float(accuracy_score(y, rf.predict(Xs))), 3)
    out["logistic_coef"] = {f: round(float(c), 4) for f, c in zip(feat_cols, lr.coef_[0])}
    out["rf_feature_importance"] = {
        f: round(float(v), 4) for f, v in zip(feat_cols, rf.feature_importances_)
    }

    # Per-row RF probability of known_hoax (in-sample — biased upward)
    proba = rf.predict_proba(Xs)[:, 1]
    out["in_sample_hoax_proba"] = {
        row_id: round(float(p), 3) for row_id, p in zip(work["id"], proba)
    }

    if len(work) >= 5 and y.sum() >= 1:
        loo = LeaveOneOut()
        preds = []
        ok = True
        for train, test in loo.split(Xs):
            if len(np.unique(y[train])) < 2:
                # Can't LOO the sole hoax row — skip that fold
                preds.append(int(y[test][0]))  # trivial: no learning signal
                continue
            clf = LogisticRegression(max_iter=500, class_weight="balanced")
            clf.fit(Xs[train], y[train])
            preds.append(int(clf.predict(Xs[test])[0]))
        out["loo_acc_logistic"] = round(float(accuracy_score(y, preds)), 3)
        out["loo_note"] = "LOO folds that drop the sole hoax class are unscored (copied label); treat as anecdotal."

    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", type=Path, default=Path("data/images"))
    ap.add_argument("--out", type=Path, default=Path("outputs/feature_table.csv"))
    ap.add_argument("--summary", type=Path, default=Path("outputs/feature_classifier_summary.md"))
    args = ap.parse_args()

    rows = []
    for item in DEFAULT_CORPUS:
        path = args.images / item["file"]
        if not path.exists():
            print(f"skip missing {path.name}")
            continue
        print(f"features {path.name}…")
        rows.append(features_for(path, item["id"], item["label"]))

    df = pd.DataFrame(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    df.to_json(args.out.with_suffix(".json"), orient="records", indent=2)
    clf = run_classifier(df[df["error"].isna()] if "error" in df.columns else df)

    lines = [
        "# B6 — Feature table + exploratory classifier",
        "",
        clf.get("caveat", "Exploratory only."),
        "",
        f"- Rows: `{args.out}` ({len(df)} formations)",
        f"- Known-hoax control: Chualar 2013 NVIDIA",
        "",
        "## Classifier snapshot",
        "",
        "```json",
        json.dumps({k: v for k, v in clf.items() if k != "caveat"}, indent=2),
        "```",
        "",
        "## Table preview",
        "",
        df.to_markdown(index=False) if hasattr(df, "to_markdown") else df.to_string(index=False),
        "",
    ]
    args.summary.write_text("\n".join(lines), encoding="utf-8")
    print(df.to_string(index=False))
    print("classifier:", json.dumps(clf, indent=2)[:800])
    print(f"wrote {args.out} and {args.summary}")


if __name__ == "__main__":
    main()
