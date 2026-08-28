#!/usr/bin/env python3
"""Train the CP classifier.

Labels are +1 / -1 from the sign of the interference weight. Internally the
XGBoost classifier uses {0, 1}; the mapping {-1 -> 0, +1 -> 1} is frozen and
stored in the model metadata.

Training features are selected from the named feature sets defined in the
analysis YAML.

Usage:
    python3 scripts/train_cpv_model.py \
        --config configs/analysis_ml_superdataset_lr.yaml \
        --features outputs/ml_superdataset/features/reco_cpv/features_reco_higgs_rest_chunk0.csv \
        --feature-set lD
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import numpy as np
import math
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import roc_curve, auc, precision_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.io import load_analysis_config, read_table, repo_root  # noqa: E402
from ilc_tth_cpv.validation import check_split_disjoint  # noqa: E402


def to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def feature_columns_from_config(cfg, feature_set_name: str):
    """Expand one YAML feature set into an ordered list of feature names."""
    features_cfg = cfg["features"]
    feature_sets = features_cfg["sets"]

    if feature_set_name not in feature_sets:
        raise SystemExit(
            f"Unknown feature set {feature_set_name!r}. "
            f"Available: {list(feature_sets)}"
        )

    feature_cfg = feature_sets[feature_set_name]
    feature_cols = []

    for object_name, variables in feature_cfg.get("objects", {}).items():
        for variable in variables:
            feature_cols.append(f"{object_name}_{variable}")

    feature_cols.extend(feature_cfg.get("auxiliary", []))

    return feature_cols


def resolve_feature_value(row, feature_name: str) -> float:
    """Extract feature value using direct lookup with dynamic fallback resolution
    for derived features (w_assignment_likelihood_selected, down_type_daughter_*, second_w_daughter_*).
    """

    # Try direct columl lookup first
    fval = to_float(row.get(feature_name))
    if math.isfinite(fval):
        return fval

    # Decide whther the selected down-type jet corresponds to wjet_quark or wjet_antiquark
    # then read the requested variable from that object

    # Candiate 1 (Down-type daughter jet)
    if feature_name.startswith("down_type_daughter_"):
        variable = feature_name.removeprefix("down_type_daughter_")

        idx_W_down_candidate = to_float(row.get("idx_W_down_candidate"))
        idx_W_quark          = to_float(row.get("idx_W_quark"))
        idx_W_antiquark      = to_float(row.get("idx_W_antiquark"))
    
        if idx_W_down_candidate not in (None, -1.0):
            if idx_W_down_candidate == idx_W_quark:
                # Down-type candidate is w_jet_quark
                selected_prefix = "wjet_quark"
            elif idx_W_down_candidate == idx_W_antiquark:
                # Down-type candidate is w_jet_antiquark
                selected_prefix = "wjet_antiquark"
            else:
                selected_prefix = None
        else:
            selected_prefix = None

        if selected_prefix is None:
            return float("nan")

        return to_float(row.get(f"{selected_prefix}_{variable}"))

    # Candidate 2 (Second W daugher jet - opposite for Candidate 1)
    if feature_name.startswith("second_w_daughter_"):
        variable = feature_name.removeprefix("second_w_daughter_")

        # Get the W-jet down type candidate
        idx_W_down_candidate = to_float(row.get("idx_W_down_candidate"))

        idx_W_quark     = to_float(row.get("idx_W_quark"))
        idx_W_antiquark = to_float(row.get("idx_W_antiquark"))

        if not (math.isfinite(idx_W_down_candidate) and math.isfinite(idx_W_quark) and math.isfinite(idx_W_antiquark)):
            return float("nan")

        if idx_W_down_candidate == idx_W_quark:
            # This means that candidate 1 was wjet_quark, so the candidate 2 is antiquark.
            prefix = "wjet_antiquark"
        elif idx_W_down_candidate == idx_W_antiquark:
            prefix = "wjet_quark"
        else:
            return float("nan")

        # Calculate pT from E, theta, mass if requested
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

    # Dynamic resolution for neutrino* features
    if feature_name.startswith("neutrino"):
        
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


    # Resolve w_assignment_likelihood_selected from L12/L21 preferene by the w_orientation_status
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

        if selected_L is None:
            return float("nan")

        return to_float(selected_L)

    return to_float(row.get(feature_name))


def prepare(
    rows,
    feature_cols,
    label_column: str,
    weight_column: str,
    balance_classes: bool,
):
    data = {
        "train": ([], [], []),
        "validation": ([], [], []),
        "test": ([], [], []),
    }

    for row in rows:
        feats = [
            resolve_feature_value(row, col)
            for col in feature_cols
        ]

        if any(f != f for f in feats):
            continue

        label = int(row[label_column])
        weight = to_float(row[weight_column])

        if weight != weight or weight <= 0.0:
            continue

        split = row["split"]
        if split not in data:
            continue

        x, y, w = data[split]
        x.append(feats)
        y.append(label)
        w.append(weight)

    if balance_classes:
        x, y, w = data["train"]

        pos = sum(wi for yi, wi in zip(y, w) if yi > 0)
        neg = sum(wi for yi, wi in zip(y, w) if yi < 0)

        if pos > 0 and neg > 0:
            scale = pos / neg
            data["train"] = (
                x,
                y,
                [
                    wi * scale if yi < 0 else wi
                    for yi, wi in zip(y, w)
                ],
            )

    # Normalise training weights to mean 1 independently in each split.
    # The absolute fb scale is irrelevant for classifier optimisation.
    for split, (x, y, w) in data.items():
        if w:
            mean_w = sum(w) / len(w)
            data[split] = (
                x,
                y,
                [wi / mean_w for wi in w],
            )

    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--config", required=True)
    parser.add_argument("--features", required=True)

    parser.add_argument(
        "--feature-set",
        default=None,
        help="Named feature set from features.sets in the YAML config",
    )
    parser.add_argument(
        "--version",
        choices=("v0", "v1", "v2"),
        default="v1",
        help="Dataset/model version (v0, v1 or v2)",
    )

    parser.add_argument(
        "--tag",
        default=None,
        help="Explicit folder tag for hyperparameter runs (e.g. trial1, depth_6, lr_005)",
    )

    parser.add_argument("--out-dir", default=None)

    args = parser.parse_args()

    cfg = load_analysis_config(Path(args.config)) # get the ML configuration file
    rows = read_table(Path(args.features))        # get the feacures.csv file

    split_report = check_split_disjoint(rows)
    if not split_report["ok"]:
        raise SystemExit(
            f"Split overlap detected: {split_report['problems']}"
        )

    features_cfg = cfg["features"] # get features from the config file

    feature_set_name = (
        args.feature_set
        if args.feature_set is not None
        else features_cfg["default_set"]
    )

    feature_cols = feature_columns_from_config(
        cfg,
        feature_set_name,
    )

    print(f"feature set: {feature_set_name}")
    print(f"features ({len(feature_cols)}):")
    for col in feature_cols:
        print(f"  {col}")

    training_cfg = cfg["training"] # get training from the config 

    label_column = training_cfg.get(
        "label_column",
        "label",
    )

    weight_column = training_cfg.get(
        "training_weight",
        "weight_training",
    )

    balance_classes = bool(
        training_cfg.get("balance_classes", True)
    )

    for lepton_flavor in training_cfg["lepton_flavors"]:
        flavor_rows = [row for row in rows if lepton_flavor == row.get("lepton_flavor")]  
        if not flavor_rows:
            raise SystemExit(f"No events with lepton flavor")

        
        data = prepare(
            flavor_rows,
            feature_cols,
            label_column,
            weight_column,
            balance_classes,
        )

        n_train = len(data["train"][0])
        n_val = len(data["validation"][0])
        n_test = len(data["test"][0])

        print(
            f"events: train={n_train} "
            f"validation={n_val} "
            f"test={n_test}"
        )

        if n_train == 0:
            raise SystemExit("No valid training events")

        if n_val == 0:
            raise SystemExit("No valid validation events")

        model_cfg = cfg["model"]
        model_type = model_cfg["type"]
        params = dict(model_cfg["params"])

        # Frozen label mapping:
        #     -1 -> class 0
        #     +1 -> class 1
        to_binary = {-1: 0, 1: 1}

        if model_type == "xgboost":
            try:
                from xgboost import XGBClassifier
            except ImportError:
                raise SystemExit(
                    "xgboost missing — run: source env/setup.sh "
                    "(it is part of the key4hep stack)"
                )

            model = XGBClassifier(
                n_estimators=int(params.get("n_estimators", 500)),
                max_depth=int(params.get("max_depth", 6)),
                learning_rate=float(params.get("learning_rate", 0.1)),
                random_state=int(params.get("random_seed", 20260720)),
                #early_stopping_rounds=int(params.get("early_stopping_rounds", 20)),
                eval_metric="logloss",
            )
            
            y_train_bin = [to_binary[y] for y in data["train"][1]]
            y_val_bin = [to_binary[y] for y in data["validation"][1]]

            eval_set = [
                (data["train"][0], y_train_bin),        # validation_0, train set
                (data["validation"][0], y_val_bin),     # validation_1, validation set
            ]

            model.fit(
                data["train"][0],
                [to_binary[y] for y in data["train"][1]],
                sample_weight=data["train"][2],
                eval_set=eval_set,
                verbose=100,
            )

            evals_result = model.evals_result()

            history = {
                "train_logloss": evals_result["validation_0"]["logloss"],
                "validation_logloss": evals_result["validation_1"]["logloss"],
            }


            classes = [-1, 1]
            model_file = "cpv_xgboost.json"

        elif model_type == "catboost":
            try:
                from catboost import CatBoostClassifier
            except ImportError:
                raise SystemExit(
                    "catboost is optional and needs a local venv "
                    "(env/environment_notes.md); "
                    "the default baseline is xgboost."
                )

            model = CatBoostClassifier(
                loss_function="Logloss",
                verbose=100,
                **params,
            )

            model.fit(
                data["train"][0],
                data["train"][1],
                sample_weight=data["train"][2],
                eval_set=(
                    data["validation"][0],
                    data["validation"][1],
                ),
            )

            evals = model.get_evals_result()
            history = {
                "train_logloss": evals["learn"]["Logloss"],
                "validation_logloss": evals["validation"]["Logloss"],
            }

            classes = [int(c) for c in model.classes_]
            model_file = "cpv_catboost.cbm"

        else:
            raise SystemExit(
                f"Unknown model.type {model_type!r} "
                "(xgboost | catboost)"
            )

        expected = [
            int(c)
            for c in model_cfg["class_order"]
        ]

        if sorted(classes) != sorted(expected):
            raise SystemExit(
                f"Class order mismatch: "
                f"model={classes} config={expected}"
            )

        # precision evaluation
        X_test = data["test"][0]
        y_test_raw = data["test"][1]

        if model_type == "xgboost":
            y_test = [to_binary[y] for y in y_test_raw]
        else:
            y_test = y_test_raw

        preds = model.predict(X_test)
        test_precision = precision_score(y_test, preds, pos_label=1, zero_division=0)
        
        print(f"[{lepton_flavor}] Test Precision: {test_precision:.4f}")

        version_dir = "model" if args.version == "v1" else f"model_{args.version}"

        base_out_dir = (
            Path(args.out_dir) / lepton_flavor
            if args.out_dir
            else repo_root()
            / cfg["outputs"]["base_dir"]
            / version_dir
            / feature_set_name
            / model_type
            / lepton_flavor
        )

        # Append tag only if provided by user
        out_dir = base_out_dir / args.tag if args.tag else base_out_dir
        

        out_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        model_path = out_dir / model_file
        model.save_model(str(model_path))

        history_path = out_dir / "training_history.json"
        with history_path.open("w") as f:
            json.dump(history, f, indent=2)

        # generate training_loss.png (Train vs Validation loss)
        epochs = len(history["train_logloss"])

        plt.figure(figsize=(8, 5))
        plt.plot(range(1, epochs + 1), history["train_logloss"], label="Train Loss", color="blue", lw=2)
        plt.plot(range(1, epochs + 1), history["validation_logloss"], label="Validation Loss", color="orange", lw=2)
        plt.xlabel("Boosting Iterations / Trees")
        plt.ylabel("Log Loss")
        plt.title(f"Training Loss Curve — {lepton_flavor}")
        plt.legend(frameon=False)
        plt.tick_params(direction="in", top=True, right=True)
        #plt.grid(True, linestyle="--", alpha=0.6)
        plt.tight_layout()
        plt.savefig(out_dir / "training_loss.png", dpi=300)
        plt.close()


        # Generate roc_curve.png (ROC Curves for Train/Val/Test)
        plt.figure(figsize=(7, 6))
        colors = {"train": "blue", "validation": "orange", "test": "green"}

        for split_name in ["train", "validation", "test"]:
            X_s, y_s, _ = data[split_name]
            y_s_bin = [to_binary[y] for y in y_s]
            
            # Predict probabilities for signal class (1)
            y_prob = model.predict_proba(X_s)[:, 1]
            fpr, tpr, _ = roc_curve(y_s_bin, y_prob)
            roc_auc = auc(fpr, tpr)
            
            plt.plot(
                fpr, tpr, 
                color=colors[split_name], 
                lw=2, 
                label=f"{split_name.capitalize()} (AUC = {roc_auc:.3f})"
            )

        plt.plot([0, 1], [0, 1], "k--", label="Random Guessing (AUC = 0.500)")
        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
        plt.title(f"ROC Curves — {lepton_flavor}")
        plt.legend(loc="lower right", frameon=False)
        plt.tick_params(direction="in", top=True, right=True)
        #plt.grid(True, linestyle="--", alpha=0.6)
        plt.tight_layout()
        plt.savefig(out_dir / "roc_curve.png", dpi=300)
        plt.close()


        # Generate feature_importance.png
        importances = model.feature_importances_
        indices = np.argsort(importances)

        plt.figure(figsize=(8, max(4, len(feature_cols) * 0.3)))
        plt.barh(range(len(indices)), importances[indices], color="teal", align="center")
        plt.yticks(range(len(indices)), [feature_cols[i] for i in indices])
        plt.xlabel("Feature Importance (Gain)")
        plt.title(f"Feature Importances — {lepton_flavor}")
        plt.tick_params(axis="x", direction="in", top=True)
        plt.tick_params(axis="y", left=False, right=False)
        plt.tight_layout()
        plt.savefig(out_dir / "feature_importance.png", dpi=300)
        plt.close()


        metadata = {
            "lepton_flavor": lepton_flavor,
            "model_file": model_path.name,
            "model_type": model_type,
            "hyperparameters": params,
            "seed": params.get("random_seed"),
            "feature_set": feature_set_name,
            "feature_list": feature_cols,
            "class_order_model": classes,
            "class_order_config": expected,
            "binary_mapping": "label -1 -> class 0, label +1 -> class 1",
            "weight_column": weight_column,
            "balance_classes": balance_classes,
            "n_train": n_train,
            "n_validation": n_val,
            "n_test": n_test,
            "features_table": str(args.features),
            "config": str(args.config),
            "created": datetime.datetime.now().isoformat(),
        }

        metadata_path = out_dir / "model_metadata.json"

        with metadata_path.open("w") as stream:
            json.dump(
                metadata,
                stream,
                indent=2,
            )

        print(f"model -> {model_path}")
        print(f"meta  -> {metadata_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
