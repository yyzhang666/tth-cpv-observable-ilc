#!/usr/bin/env python3
"""Train the frozen baseline-v1 signal/background selection MVA."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
from pathlib import Path
from typing import Any

import numpy as np

try:
    from .selection_mva_common import (
        BASELINE_FEATURES,
        apply_training_weights,
        atomic_json,
        atomic_npz,
        choose_smoke_jobs,
        feature_hash,
        implementation_identity,
        load_authority,
        load_matrix,
        selected_job_keys,
        sha256_file,
        training_weight_coefficients,
    )
except ImportError:
    from selection_mva_common import (
        BASELINE_FEATURES,
        apply_training_weights,
        atomic_json,
        atomic_npz,
        choose_smoke_jobs,
        feature_hash,
        implementation_identity,
        load_authority,
        load_matrix,
        selected_job_keys,
        sha256_file,
        training_weight_coefficients,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/mva_training.yaml"))
    parser.add_argument("--run-id", help="Override the immutable run ID")
    parser.add_argument("--smoke", action="store_true", help="Bounded six-sample smoke")
    return parser.parse_args()


def train_booster(
    train_x: np.ndarray,
    train_y: np.ndarray,
    train_weight: np.ndarray,
    validation_x: np.ndarray,
    validation_y: np.ndarray,
    validation_weight: np.ndarray,
    model_config: dict[str, Any],
):
    try:
        import xgboost as xgb
    except ImportError as exc:
        raise RuntimeError("xgboost is required; run: source env/setup.sh") from exc

    parameters = {
        "objective": "binary:logistic",
        "tree_method": str(model_config["tree_method"]),
        "max_depth": int(model_config["max_depth"]),
        "eta": float(model_config["learning_rate"]),
        "min_child_weight": float(model_config["min_child_weight"]),
        "lambda": float(model_config["reg_lambda"]),
        "subsample": float(model_config["subsample"]),
        "colsample_bytree": float(model_config["colsample_bytree"]),
        "max_bin": int(model_config["max_bin"]),
        "eval_metric": str(model_config["eval_metric"]),
        "seed": int(model_config["seed"]),
        "nthread": int(model_config["nthread"]),
    }
    train_matrix = xgb.DMatrix(
        train_x,
        label=train_y,
        weight=train_weight,
        feature_names=BASELINE_FEATURES,
    )
    validation_matrix = xgb.DMatrix(
        validation_x,
        label=validation_y,
        weight=validation_weight,
        feature_names=BASELINE_FEATURES,
    )
    history: dict[str, Any] = {}
    booster = xgb.train(
        parameters,
        train_matrix,
        num_boost_round=int(model_config["num_boost_round"]),
        evals=[(train_matrix, "train"), (validation_matrix, "validation")],
        early_stopping_rounds=int(model_config["early_stopping_rounds"]),
        evals_result=history,
        verbose_eval=False,
    )
    validation_score = booster.predict(
        validation_matrix,
        iteration_range=(0, booster.best_iteration + 1),
    )
    return booster, history, validation_score


def main() -> None:
    args = parse_args()
    authority = load_authority(args.config)
    implementation = implementation_identity(authority.root)
    config = authority.config
    run_id = args.run_id or str(config["output"]["run_id"])
    if args.smoke:
        run_id = f"{run_id}-smoke"
    output_root = authority.root / config["output"]["root"]
    final_dir = output_root / run_id
    temporary_dir = output_root / f".{run_id}.tmp.{os.getpid()}"
    if final_dir.exists() or temporary_dir.exists():
        raise RuntimeError(f"Refusing to overwrite MVA run: {final_dir}")
    temporary_dir.mkdir(parents=True)

    try:
        train_keys = selected_job_keys(authority, splits={"train"})
        validation_keys = selected_job_keys(authority, splits={"validation"})
        max_events = None
        if args.smoke:
            train_keys = choose_smoke_jobs(authority, train_keys)
            validation_keys = choose_smoke_jobs(authority, validation_keys)
            max_events = int(config["smoke"]["max_events_per_job"])

        train = load_matrix(authority, train_keys, max_events_per_job=max_events)
        validation = load_matrix(authority, validation_keys, max_events_per_job=max_events)
        if bool(np.any(train["y"] < 0)) or bool(np.any(validation["y"] < 0)):
            raise RuntimeError("CPV or unknown labels reached fitting data")
        coefficients = training_weight_coefficients(train["y"], train["polarization"])
        train_weight = apply_training_weights(
            train["y"], train["polarization"], coefficients
        )
        validation_weight = apply_training_weights(
            validation["y"], validation["polarization"], coefficients
        )
        booster, history, validation_score = train_booster(
            train["X"],
            train["y"],
            train_weight,
            validation["X"],
            validation["y"],
            validation_weight,
            config["model"],
        )
        if not bool(np.isfinite(validation_score).all()):
            raise RuntimeError("Non-finite validation predictions")
        if float(np.ptp(validation_score)) == 0.0:
            raise RuntimeError("Constant validation predictions")

        model_path = temporary_dir / "model.json"
        booster.save_model(model_path)
        atomic_npz(
            temporary_dir / "validation_predictions.npz",
            score=np.asarray(validation_score, dtype=np.float32),
            label=validation["y"],
            weight_train=validation_weight,
            polarization=validation["polarization"],
            job_key=validation["job_key"],
            event_index=validation["event_index"],
        )
        atomic_json(temporary_dir / "training_history.json", history)
        coefficient_json = {
            f"{label}:{helicity}": value
            for (label, helicity), value in sorted(coefficients.items())
        }
        provenance = {
            "schema_version": 1,
            "analysis_name": config["analysis_name"],
            "run_id": run_id,
            "formal_use_allowed": not args.smoke,
            "features": BASELINE_FEATURES,
            "feature_hash": feature_hash(),
            "training_config": str(authority.config_path),
            "training_config_sha256": sha256_file(authority.config_path),
            "mva_config_sha256": sha256_file(authority.mva_config_path),
            "split_assignment_sha256": sha256_file(authority.split_path),
            "weights_catalog_sha256": sha256_file(authority.catalog_path),
            "weights_catalog_hash": authority.catalog_hash,
            "inventory_content_hash": authority.catalog["inventory_content_hash"],
            "implementation": implementation,
            "model_sha256": sha256_file(model_path),
            "model_parameters": config["model"],
            "best_iteration": int(booster.best_iteration),
            "best_score": float(booster.best_score),
            "train_jobs": len(train_keys),
            "validation_jobs": len(validation_keys),
            "n_train": int(len(train["y"])),
            "n_validation": int(len(validation["y"])),
            "training_weight_coefficients": coefficient_json,
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
            "xgboost_version": __import__("xgboost").__version__,
            "seed": int(config["model"]["seed"]),
            "cpv_used_for_training": False,
            "hdf5_modified": False,
        }
        atomic_json(temporary_dir / "provenance.json", provenance)
        temporary_dir.replace(final_dir)
    except Exception:
        if temporary_dir.exists():
            shutil.rmtree(temporary_dir)
        raise

    print(json.dumps({
        "run_dir": str(final_dir),
        "model": str(final_dir / "model.json"),
        "n_train": provenance["n_train"],
        "n_validation": provenance["n_validation"],
        "best_iteration": provenance["best_iteration"],
        "formal_use_allowed": provenance["formal_use_allowed"],
    }, indent=2))


if __name__ == "__main__":
    main()
