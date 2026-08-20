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
        --features outputs/ml_superdataset/features.csv \
        --feature-set lD
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

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
    """Resolve one configured feature for one event."""

    # TODO: down_type_daughter is a virtual object.
    #
    # For features such as:
    #     down_type_daughter_E
    #     down_type_daughter_theta
    #     down_type_daughter_phi
    #     down_type_daughter_mass
    #
    # use:
    #     idx_W_down_candidate
    #     idx_W_quark
    #     idx_W_antiquark
    #
    # to decide whether the selected down-type jet corresponds to
    # wjet_quark or wjet_antiquark, then read the requested variable
    # from that object.
    #
    # Example logic:
    #
    # if feature_name.startswith("down_type_daughter_"):
    #     variable = feature_name.removeprefix("down_type_daughter_")
    #     ...
    #     return to_float(row[f"{selected_prefix}_{variable}"])

    # TODO: virtual auxiliary feature.
    #
    # w_assignment_likelihood_selected does not exist directly in the CSV.
    # Resolve it from L12 preference or L21 preference by the w_orientation_status
    # If it is L12 preference then return to L12
    # if feature_name == "w_assignment_likelihood_selected":
    #     ...
    #     return selected_L

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

    parser.add_argument("--out-dir", default=None)

    args = parser.parse_args()

    cfg = load_analysis_config(Path(args.config))
    rows = read_table(Path(args.features))

    split_report = check_split_disjoint(rows)
    if not split_report["ok"]:
        raise SystemExit(
            f"Split overlap detected: {split_report['problems']}"
        )

    features_cfg = cfg["features"]

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

    training_cfg = cfg["training"]

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

    # TODO: electron / muon must be trained separately.
    # Do the next uncommented code under this for loop with two lepton flavors
    # for lepton_flavor in training_cfg["lepton_flavors"]:
    #     flavor_rows = [...] Judge if the lepton is muon or electron.
    #
    # Each category must produce an independent model and metadata file.

    data = prepare(
        rows,
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
            eval_metric="logloss",
        )

        # Frozen label mapping:
        #     -1 -> class 0
        #     +1 -> class 1
        to_binary = {-1: 0, 1: 1}

        model.fit(
            data["train"][0],
            [to_binary[y] for y in data["train"][1]],
            sample_weight=data["train"][2],
            eval_set=[
                (
                    data["validation"][0],
                    [
                        to_binary[y]
                        for y in data["validation"][1]
                    ],
                )
            ],
            verbose=False,
        )

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

    out_dir = (
        Path(args.out_dir)
        if args.out_dir
        else repo_root()
        / cfg["outputs"]["base_dir"]
        / "model"
        / feature_set_name
    )

    # TODO: after electron/muon category splitting is implemented,
    # add the lepton flavor to the output path, for example:
    #
    #     model/lD/electron/
    #     model/lD/muon/
    # Also the meta data path also need to change later

    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    model_path = out_dir / model_file
    model.save_model(str(model_path))

    metadata = {
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
