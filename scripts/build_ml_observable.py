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


def to_float(val) -> float:
    """Safely convert values to finite floats or NaN."""
    if val is None or val == "":
        return float("nan")
    try:
        fval = float(val)
        return fval if math.isfinite(fval) else float("nan")
    except (TypeError, ValueError):
        return float("nan")
    

def extract_feature_value(row: dict, feature_name: str) -> float:
    """Extract feature value using direct lookup with dynamic fallback resolution
    for derived features (w_assignment_likelihood_selected, down_type_daughter_*, second_w_daughter_*).
    """
    # Try direct column lookup (works for v2 and all standard features)
    fval = to_float(row.get(feature_name))
    if math.isfinite(fval):
        return fval

    # Dynamic resolution for w_assignment_likelihood_selected
    if feature_name == "w_assignment_likelihood_selected":
        preference = row.get("w_orientation_status")
        L12 = row.get("L12")
        L21 = row.get("L21")

        if preference == "L12_preferred":
            selected_L = L12
        elif preference == "L21_preferred":
            selected_L = L21
        else:
            selected_L = None

        return to_float(selected_L)

    # Fallback dynamic resolution for missing v1 down_type_daughter_* columns
    if feature_name.startswith("down_type_daughter_"):
        variable = feature_name.removeprefix("down_type_daughter_")
        try:
            idx_down = float(row.get("idx_W_down_candidate", -1.0))
            idx_q = float(row.get("idx_W_quark", -1.0))
            idx_qbar = float(row.get("idx_W_antiquark", -1.0))
        except (TypeError, ValueError):
            return float("nan")

        if idx_down != -1.0 and math.isfinite(idx_down):
            if idx_down == idx_q:
                prefix = "wjet_quark"
            elif idx_down == idx_qbar:
                prefix = "wjet_antiquark"
            else:
                return float("nan")
        else:
            return float("nan")

        val = row.get(f"{prefix}_{variable}")
        return float(val) if val is not None else float("nan")

    # Fallback dynamic resolution for second_w_daughter_* features
    if feature_name.startswith("second_w_daughter_"):
        variable = feature_name.removeprefix("second_w_daughter_")

        idx_W_down_candidate = to_float(row.get("idx_W_down_candidate"))
        idx_W_quark          = to_float(row.get("idx_W_quark"))
        idx_W_antiquark      = to_float(row.get("idx_W_antiquark"))

        if not (math.isfinite(idx_W_down_candidate) and math.isfinite(idx_W_quark) and math.isfinite(idx_W_antiquark)):
            return float("nan")

        if idx_W_down_candidate == idx_W_quark:
            prefix = "wjet_antiquark"
        elif idx_W_down_candidate == idx_W_antiquark:
            prefix = "wjet_quark"
        else:
            return float("nan")

        # Calculate pT from E, theta, mass
        if variable == "pt":
            E     = to_float(row.get(f"{prefix}_E"))
            theta = to_float(row.get(f"{prefix}_theta"))
            m     = to_float(row.get(f"{prefix}_mass"))

            if not (math.isfinite(E) and math.isfinite(theta)):
                return float("nan")

            m_val = m if math.isfinite(m) else 0.0

            p = math.sqrt(max(0.0, E**2 - m_val**2))
            return p * math.sin(theta)

        return to_float(row.get(f"{prefix}_{variable}"))

    # Dynamic resolution for neutrino_* features
    if feature_name.startswith("neutrino_"):
        
        # 1. Try to read the column directly from the CSV
        val = row.get(feature_name)
        if val is not None:
            parsed_val = to_float(val)
            if math.isfinite(parsed_val):
                return parsed_val

        # 2. Safety fallback: calculate pt from E and theta if neutrino_pt is missing
        if feature_name == "neutrino_pt":
            E     = to_float(row.get("neutrino_E"))
            theta = to_float(row.get("neutrino_theta"))
            if math.isfinite(E) and math.isfinite(theta):
                return E * math.sin(theta)

        return float("nan")
        
    return to_float(row.get(feature_name))

        
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
    parser.add_argument("--out-dir", default="", help="custom output directory path") 
    parser.add_argument("--version", default="", choices=("", "v0", "v1", "v2"),
                        help="explicit version tag (v0, v1, v2); auto-detected if omitted")
    parser.add_argument("--logit", action="store_true", help="also compute log(P+/P-)")
    args = parser.parse_args()

    output_tag = args.output_tag
    if not output_tag:
        features_parent = Path(args.features).parent.name
        if features_parent and not features_parent.startswith("features"):
            output_tag = features_parent

    cfg = load_analysis_config(Path(args.config))
    meta_path = Path(args.model).parent / "model_metadata.json"

    with meta_path.open() as stream:
        model_meta = json.load(stream)

    feature_cols = model_meta["feature_list"]
    classes = [int(c) for c in model_meta["class_order_model"]]
    model_type = model_meta.get("model_type", "xgboost")
    feature_set_name = model_meta.get("feature_set", "lD")

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

    # Determine if sm or cpv
    is_sm = "sm" in output_tag.lower() or args.weight_column == "weight_sm"

    # Select cross section based on process (SM vs CPV)
    if is_sm:
        # Default LR SM cross section (eL pR: 2.96055 fb)
        sigma_total_fb = float(samples_cfg.get("sm_cross_section_fb", 2.96055))
    else:
        # CPV interference cross section magnitude
        sigma_total_fb = float(samples_cfg.get("cpv_cross_section_fb", 0.395666999328))

    n_chunks           = int(samples_cfg.get("n_chunks", 79))
    event_per_chunk    = int(samples_cfg.get("events_per_chunk", 12500))
    split_fraction  = float(split_cfg.get(args.split, 0.2)) if args.split != "all" else 1.0

    n_gen_total = n_chunks * event_per_chunk
    n_gen_test  = n_gen_total * split_fraction

    base_weight_scale = sigma_total_fb / n_gen_test


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
            value = extract_feature_value(row, col)
            if not math.isfinite(value):
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
        sign = 1.0 if is_sm else float(row["label"])
        w_scaled = sign * base_weight_scale
        
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

    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        out_dir = repo_root() / cfg["outputs"]["base_dir"] / obs_folder / feature_set_name / model_type

    out_dir.mkdir(parents=True, exist_ok=True)

    if not score_rows:
        raise SystemExit(
            f"No finite {args.weight_column} values for split {args.split}. "
            "For SM physical templates, check cross_section_fb in samples.yaml."
        )

    tag = f"_{output_tag}" if output_tag else ""   
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
        "output_tag": output_tag,
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
            "output_tag": output_tag,
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

    stem = f"template_{args.split}{lepton_flavor_tag}{tag}"
    observable = "O_ML"
    frame = "score"

    try:
        from ilc_tth_cpv.plotting import plot_signed_histogram

        png = plot_signed_histogram(
            hist,
            out_dir / f"{stem}.png",
            title=f"{observable} [{frame}] split={args.split}",
            xlabel=f"ML Score O_ML = P(+) - P(-)",
        )
        print(f"plot   -> {png}")
    except Exception as exc:  # matplotlib may be absent in minimal envs
        print(f"plot skipped ({exc})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
