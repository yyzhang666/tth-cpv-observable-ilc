#!/usr/bin/env python3
"""Build the ML observable template from a trained model.

Evaluates the requested independent split (default: test) — final templates
always come from events the model has never seen. Score convention:
O_ML = P(+) - P(-) (frozen; PHYSICS_CONVENTIONS.md §9). Templates use the
signed physics weights.

Usage:
    python3 scripts/build_ml_observable.py \
        --config configs/analysis_ml_superdataset_lr_v2.yaml \
        --features outputs/ml_superdataset/features_v2/reco_cpv/features_reco_higgs_rest_chunk1_79.csv \
        --model outputs/ml_superdataset/model_v2/lD/xgboost/electron/cpv_xgboost.json \
        --lepton-flavor electron \
        --version v2
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.histograms import SignedHistogram, linear_edges  # noqa: E402
from ilc_tth_cpv.io import load_analysis_config, read_table, repo_root, write_table  # noqa: E402
from ilc_tth_cpv.validation import check_phi_wrapping, check_signed_weight_sums

def filter_rows(rows: list, split: str = "all", lepton_flavor: str = "all") -> list:
    """Helps to filter dataset based on two optinal criteria:
       data split (train, val, test) and lepton flavor (e, mu)"""
    if split != "all":
        rows = [row for row in rows if row["split"] == split]
    if lepton_flavor != "all":
        rows = [row for row in rows if row["lepton_flavor"] == lepton_flavor]
    return rows

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--features", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--split", default="test", choices=("validation", "test"))
    parser.add_argument("--n-bins", type=int, default=20)
    parser.add_argument("--lepton-flavor", default="all", choices=("all", "electron", "muon"))
    parser.add_argument("--weight-column", default="weight_template")
    parser.add_argument("--output-tag", default="",
                        help="optional filename tag, e.g. sm")
    parser.add_argument("--version", default="", choices=("", "v0", "v1", "v2"),
                        help="explicit version tag (v0, v1, v2); auto-detected if omitted")
    parser.add_argument("--logit", action="store_true", help="also compute log(P+/P-)")
    args = parser.parse_args()

    cfg = load_analysis_config(Path(args.config))
    meta_path = Path(args.model).parent / "model_metadata.json"

    with meta_path.open() as stream:
        model_meta = json.load(stream)

    feature_cols = model_meta["feature_list"]
    classes = [int(c) for c in model_meta["class_order_model"]]
    model_type = model_meta.get("model_type", "xgboost")

    # Identify the ML model type (XGBoost/caboost)
    if model_type == "xgboost":
        from xgboost import XGBClassifier

        model = XGBClassifier()
        model.load_model(args.model)
    elif model_type == "catboost":
        from catboost import CatBoostClassifier

        model = CatBoostClassifier()
        model.load_model(args.model)
    else:
        raise SystemExit(f"Unknown model_type {model_type!r} in metadata")

    rows = read_table(Path(args.features))


    # == Scaling weights == #
    samples_cfg = cfg.get("samples", {})
    split_cfg   = cfg.get("split", {})

    sigma_total_fb_cpv = float(samples_cfg.get("cpv_cross_section_fb", 0.395666999328)) #fb, value for total cross-section for CPV
    n_chunks           = int(samples_cfg.get("n_chunks", 79))
    event_per_chunk    = int(samples_cfg.get("events_per_chunk", 12500))
    if args.split != "all":
        split_fraction = float(split_cfg.get(args.split, 0.2))
    else:
        split_fraction = 1.0

    n_gen_total = n_chunks * event_per_chunk
    n_gen_test  = n_gen_total * split_fraction

    # Normalization factor per event to convert raw weights to physical fb
    gen_weight_scale = sigma_total_fb_cpv / n_gen_test


    # All events for the specified lepton flavor
    flavor_rows = filter_rows(rows, split="all", lepton_flavor=args.lepton_flavor) 

    # Split by validation/test (in default, take only the test)
    eval_rows = filter_rows(flavor_rows, split=args.split)

    if not eval_rows:
        raise SystemExit(f"No events in split='{args.split}' and lepton_flavor='{args.lepton_flavor}'")
    
    x, kept = [], []
    for row in eval_rows:
        feats = []
        valid = True
        for col in feature_cols:
            try:
                value = float(row[col])
            except (KeyError, TypeError, ValueError):
                valid = False
                break
            if value != value:
                valid = False
                break
            feats.append(value)
        if valid:
            x.append(feats)
            kept.append(row)

    proba = model.predict_proba(x)
    plus_idx = classes.index(1)
    minus_idx = classes.index(-1)

    hist = SignedHistogram(edges=linear_edges(-1.0, 1.0, args.n_bins))
    score_rows = []

    for row, p in zip(kept, proba):
        p_plus, p_minus = float(p[plus_idx]), float(p[minus_idx])
        score = p_plus - p_minus

        w_template = float(row[args.weight_column]) # weight_raw
        if not math.isfinite(w_template):
            continue

        # Scale weight with scale factor 
        w_scaled = w_template * gen_weight_scale
        row[args.weight_column] = w_scaled    # Updated row dict

        hist.fill(score, w_scaled)
        out = {
            "event_id": row["event_id"],
            "split": row["split"],
            "helicity": row["helicity"],
            "p_plus": p_plus,
            "p_minus": p_minus,
            "score": score,
            "weight_column": args.weight_column,
            "template_weight": w_scaled,
        }
        if args.logit:
            out["logit"] = math.log(p_plus / p_minus) if p_minus > 0 else float("inf")
        score_rows.append(out)

    weight_report = check_signed_weight_sums(kept, args.weight_column)

    # Version detection for output folder
    version_tag = args.version
    if not version_tag:
        for p in (args.config, args.features, args.model):
            if "v2" in p:
                version_tag = "v2"
                break
            elif "v0" in p:
                version_tag = "v0"
                break
            elif "v1" in p:
                version_tag = "v1"
                break

    if version_tag == "v2":
        obs_folder = "ml_observable_v2"
    elif version_tag == "v0":
        obs_folder = "ml_observable_v0"
    else:
        obs_folder = "ml_observable"  # Default for v1


    out_dir = repo_root() / cfg["outputs"]["base_dir"] / obs_folder / model_type
    out_dir.mkdir(parents=True, exist_ok=True)
    if not score_rows:
        raise SystemExit(
            f"No finite {args.weight_column} values for split {args.split}. "
            "For SM physical templates, check cross_section_fb in samples.yaml."
        )
    tag = f"_{args.output_tag}" if args.output_tag else ""
    lepton_flavor_tag = f"_{args.lepton_flavor}" if args.lepton_flavor != "all" else ""

    write_table(
        out_dir / f"scores_{args.split}{lepton_flavor_tag}{tag}.csv", score_rows, metadata={
        "config": cfg["analysis"]["name"],
        "model": str(args.model),
        "model_metadata": model_meta,
        "split": args.split,
        "lepton_flavor": args.lepton_flavor,
        "n_evaluated": len(kept),
        "n_dropped_invalid": len(eval_rows) - len(kept),
        "score_definition": "P(+) - P(-)",
        "weight_column": args.weight_column,
        "output_tag": args.output_tag,
        "created": datetime.datetime.now().isoformat(),
    })
    write_table(
        out_dir / f"template_{args.split}{lepton_flavor_tag}{tag}_bins.csv",
        hist.as_rows(frame="score", observable="O_ML"),
        metadata={
            "config": cfg["analysis"]["name"],
            "model": str(args.model),
            "split": args.split,
            "lepton_flavor": args.lepton_flavor,
            "weight_column": args.weight_column,
            "output_tag": args.output_tag,
            "n_events_filled": len(score_rows),
            "integral_signed_fb": hist.integral_signed(),
            "integral_abs_fb": hist.integral_abs(),
            "weight_report": {k: v for k, v in weight_report.items() if k != "problems"},
            "created": datetime.datetime.now().isoformat(),
        },
    )
    print(f"scores   -> {out_dir / f'scores_{args.split}{lepton_flavor_tag}{tag}.csv'} ({len(score_rows)} events)")
    print(f"template -> {out_dir / f'template_{args.split}{lepton_flavor_tag}{tag}_bins.csv'}")
    weight_unit = "shape fraction" if args.weight_column == "weight_sm_shape" else "fb"
    print(f"signed integral = {hist.integral_signed():+.6g} {weight_unit} "
          f"z_signed={weight_report['z_signed']:+.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
