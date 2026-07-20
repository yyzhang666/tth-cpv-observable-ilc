#!/usr/bin/env python3
"""Train the CP classifier (XGBoost baseline; runs on the cvmfs stack alone).

Labels: +1 / -1 by the sign of the interference weight. Internally the
booster uses {0, 1}; the mapping {-1 -> 0, +1 -> 1} is frozen and stored in
the model metadata. Training uses |w_int| with class balancing; physics
templates keep the signed weights (separate column).

Model choice: XGBoost is the default because it ships with the key4hep
stack on cvmfs — a fresh NAF account needs zero pip installs. CatBoost is
supported as an optional alternative when a local venv provides it.

Usage:
    python3 scripts/train_cpv_model.py --config configs/analysis_ow_lr.yaml \
        --features outputs/ow_lr/features/features_gen_higgs_rest_chunk0.csv
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.features import minimal_feature_columns  # noqa: E402
from ilc_tth_cpv.io import load_analysis_config, read_table, repo_root  # noqa: E402
from ilc_tth_cpv.validation import check_split_disjoint  # noqa: E402


def to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def prepare(rows, feature_cols, balance_classes: bool):
    data = {"train": ([], [], []), "validation": ([], [], []), "test": ([], [], [])}
    for row in rows:
        feats = [to_float(row.get(col)) for col in feature_cols]
        if any(f != f for f in feats):
            continue  # invalid objects are excluded from training pools
        label = int(row["label"])
        weight = to_float(row["weight_training"])
        if weight != weight or weight <= 0.0:
            continue
        x, y, w = data[row["split"]]
        x.append(feats)
        y.append(label)
        w.append(weight)
    if balance_classes:
        x, y, w = data["train"]
        pos = sum(wi for yi, wi in zip(y, w) if yi > 0)
        neg = sum(wi for yi, wi in zip(y, w) if yi < 0)
        if pos > 0 and neg > 0:
            scale = pos / neg
            data["train"] = (x, y, [wi * scale if yi < 0 else wi
                                    for yi, wi in zip(y, w)])
    # normalise TRAINING weights to mean 1 per split: the raw |w_int| values
    # are at the fb scale (~1e-5) and would defeat tree-growth criteria such
    # as min_child_weight. Physics template weights stay untouched.
    for split, (x, y, w) in data.items():
        if w:
            mean_w = sum(w) / len(w)
            data[split] = (x, y, [wi / mean_w for wi in w])
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--features", required=True)
    parser.add_argument("--objects", nargs="*", default=["wjet_quark", "wjet_antiquark"])
    parser.add_argument("--balance-classes", action="store_true", default=True)
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    cfg = load_analysis_config(Path(args.config))
    rows = read_table(Path(args.features))
    split_report = check_split_disjoint(rows)
    if not split_report["ok"]:
        raise SystemExit(f"Split overlap detected: {split_report['problems']}")

    feature_cols = minimal_feature_columns(args.objects)
    data = prepare(rows, feature_cols, args.balance_classes)
    n_train = len(data["train"][0])
    n_val = len(data["validation"][0])
    n_test = len(data["test"][0])
    print(f"events: train={n_train} validation={n_val} test={n_test}")
    if n_train == 0:
        raise SystemExit("No valid training events")

    model_cfg = cfg["model"]
    model_type = model_cfg["type"]
    params = dict(model_cfg["params"])

    if model_type == "xgboost":
        try:
            from xgboost import XGBClassifier
        except ImportError:
            raise SystemExit("xgboost missing — run: source env/setup.sh "
                             "(it is part of the key4hep stack)")
        model = XGBClassifier(
            n_estimators=int(params.get("n_estimators", 500)),
            max_depth=int(params.get("max_depth", 6)),
            learning_rate=float(params.get("learning_rate", 0.1)),
            random_state=int(params.get("random_seed", 20260720)),
            eval_metric="logloss",
        )
        # frozen mapping: label -1 -> class 0, label +1 -> class 1
        to_binary = {-1: 0, 1: 1}
        model.fit(
            data["train"][0], [to_binary[y] for y in data["train"][1]],
            sample_weight=data["train"][2],
            eval_set=[(data["validation"][0],
                       [to_binary[y] for y in data["validation"][1]])],
            verbose=False,
        )
        classes = [-1, 1]                      # column 0 -> P(-1), column 1 -> P(+1)
        model_file = "cpv_xgboost.json"
    elif model_type == "catboost":
        try:
            from catboost import CatBoostClassifier
        except ImportError:
            raise SystemExit("catboost is optional and needs a local venv "
                             "(env/environment_notes.md); the default "
                             "baseline is xgboost.")
        model = CatBoostClassifier(loss_function="Logloss", verbose=100, **params)
        model.fit(
            data["train"][0], data["train"][1],
            sample_weight=data["train"][2],
            eval_set=(data["validation"][0], data["validation"][1]),
        )
        classes = [int(c) for c in model.classes_]
        model_file = "cpv_catboost.cbm"
    else:
        raise SystemExit(f"Unknown model.type {model_type!r} (xgboost | catboost)")

    expected = [int(c) for c in model_cfg["class_order"]]
    if sorted(classes) != sorted(expected):
        raise SystemExit(f"Class order mismatch: model={classes} config={expected}")

    out_dir = Path(args.out_dir) if args.out_dir else (
        repo_root() / cfg["outputs"]["base_dir"] / "model"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / model_file
    model.save_model(str(model_path))

    def separation(x, y, w):
        """Simple separation metric on P(+)-P(-); full metrics in notebooks."""
        if not x:
            return None
        proba = model.predict_proba(x)
        plus_idx = classes.index(1)
        minus_idx = classes.index(-1)
        scores = [p[plus_idx] - p[minus_idx] for p in proba]
        pos = [s for s, yi in zip(scores, y) if yi > 0]
        neg = [s for s, yi in zip(scores, y) if yi < 0]
        if not pos or not neg:
            return None
        mean_p = sum(pos) / len(pos)
        mean_n = sum(neg) / len(neg)
        var_p = sum((s - mean_p) ** 2 for s in pos) / len(pos)
        var_n = sum((s - mean_n) ** 2 for s in neg) / len(neg)
        denom = math.sqrt(0.5 * (var_p + var_n)) or float("inf")
        return (mean_p - mean_n) / denom

    metadata = {
        "model_file": model_path.name,
        "model_type": model_type,
        "hyperparameters": params,
        "seed": params.get("random_seed"),
        "feature_list": feature_cols,
        "objects": args.objects,
        "class_order_model": classes,
        "class_order_config": expected,
        "binary_mapping": "label -1 -> class 0, label +1 -> class 1",
        "score_definition": model_cfg["score"],
        "weight_convention": "training=|w_int| (class-balanced), templates=signed w_int",
        "n_train": n_train,
        "n_validation": n_val,
        "n_test": n_test,
        "separation_train": separation(*data["train"]),
        "separation_validation": separation(*data["validation"]),
        "features_table": str(args.features),
        "config": str(args.config),
        "created": datetime.datetime.now().isoformat(),
    }
    with (out_dir / "model_metadata.json").open("w") as stream:
        json.dump(metadata, stream, indent=2)
    print(f"model  -> {model_path}")
    print(f"meta   -> {out_dir / 'model_metadata.json'}")
    print(f"separation train={metadata['separation_train']} "
          f"validation={metadata['separation_validation']} (watch overtraining)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
