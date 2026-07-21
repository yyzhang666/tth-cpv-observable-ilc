#!/usr/bin/env python3
"""Build the ML observable template from a trained model.

Evaluates the requested independent split (default: test) — final templates
always come from events the model has never seen. Score convention:
O_ML = P(+) - P(-) (frozen; PHYSICS_CONVENTIONS.md §9). Templates use the
signed physics weights.

Usage:
    python3 scripts/build_ml_observable.py \
        --config configs/analysis_ow_lr.yaml \
        --features outputs/ow_lr/features/features_gen_higgs_rest_chunk0.csv \
        --model outputs/ow_lr/model/cpv_xgboost.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.histograms import SignedHistogram, linear_edges  # noqa: E402
from ilc_tth_cpv.io import load_analysis_config, read_table, repo_root, write_table  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--features", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--split", default="test", choices=("validation", "test"))
    parser.add_argument("--n-bins", type=int, default=20)
    parser.add_argument("--weight-column", default="weight_template")
    parser.add_argument("--output-tag", default="",
                        help="optional filename tag, e.g. sm")
    parser.add_argument("--logit", action="store_true", help="also compute log(P+/P-)")
    args = parser.parse_args()

    cfg = load_analysis_config(Path(args.config))
    meta_path = Path(args.model).parent / "model_metadata.json"
    with meta_path.open() as stream:
        model_meta = json.load(stream)
    feature_cols = model_meta["feature_list"]
    classes = [int(c) for c in model_meta["class_order_model"]]
    model_type = model_meta.get("model_type", "xgboost")

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
    eval_rows = [row for row in rows if row["split"] == args.split]
    if not eval_rows:
        raise SystemExit(f"No events in split {args.split}")

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
    import math

    for row, p in zip(kept, proba):
        p_plus, p_minus = float(p[plus_idx]), float(p[minus_idx])
        score = p_plus - p_minus
        w_template = float(row[args.weight_column])
        if not math.isfinite(w_template):
            continue
        hist.fill(score, w_template)
        out = {
            "event_id": row["event_id"],
            "split": row["split"],
            "helicity": row["helicity"],
            "p_plus": p_plus,
            "p_minus": p_minus,
            "score": score,
            "weight_column": args.weight_column,
            "template_weight": w_template,
        }
        if args.logit:
            out["logit"] = math.log(p_plus / p_minus) if p_minus > 0 else float("inf")
        score_rows.append(out)

    out_dir = repo_root() / cfg["outputs"]["base_dir"] / "ml_observable"
    out_dir.mkdir(parents=True, exist_ok=True)
    if not score_rows:
        raise SystemExit(
            f"No finite {args.weight_column} values for split {args.split}. "
            "For SM physical templates, check cross_section_fb in samples.yaml."
        )
    tag = f"_{args.output_tag}" if args.output_tag else ""
    write_table(out_dir / f"scores_{args.split}{tag}.csv", score_rows, metadata={
        "config": cfg["analysis"]["name"],
        "model": str(args.model),
        "model_metadata": model_meta,
        "split": args.split,
        "n_evaluated": len(kept),
        "n_dropped_invalid": len(eval_rows) - len(kept),
        "score_definition": "P(+) - P(-)",
        "weight_column": args.weight_column,
        "output_tag": args.output_tag,
        "created": datetime.datetime.now().isoformat(),
    })
    write_table(
        out_dir / f"template_{args.split}{tag}_bins.csv",
        hist.as_rows(frame="score", observable="O_ML"),
        metadata={
            "config": cfg["analysis"]["name"],
            "model": str(args.model),
            "split": args.split,
            "weight_column": args.weight_column,
            "output_tag": args.output_tag,
            "n_events_filled": len(score_rows),
            "created": datetime.datetime.now().isoformat(),
        },
    )
    print(f"scores   -> {out_dir / f'scores_{args.split}{tag}.csv'} ({len(score_rows)} events)")
    print(f"template -> {out_dir / f'template_{args.split}{tag}_bins.csv'}")
    weight_unit = "shape fraction" if args.weight_column == "weight_sm_shape" else "fb"
    print(f"signed integral = {hist.integral_signed():+.6g} {weight_unit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
