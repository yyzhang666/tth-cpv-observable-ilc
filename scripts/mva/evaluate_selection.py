#!/usr/bin/env python3
"""Evaluate catalogued score shards and freeze a validation-only threshold."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import h5py
import numpy as np
from sklearn.metrics import log_loss, roc_auc_score

try:
    from .selection_mva_common import (
        CPV_SAMPLE,
        atomic_json,
        canonical_json_hash,
        choose_smoke_jobs,
        load_authority,
        load_job_arrays,
        require_finite_probability,
        selected_job_keys,
        sha256_file,
        validate_best_iteration,
        verify_implementation_identity,
    )
except ImportError:
    from selection_mva_common import (
        CPV_SAMPLE,
        atomic_json,
        canonical_json_hash,
        choose_smoke_jobs,
        load_authority,
        load_job_arrays,
        require_finite_probability,
        selected_job_keys,
        sha256_file,
        validate_best_iteration,
        verify_implementation_identity,
    )


THRESHOLD_STATUS = "provisional_incomplete_validation_normalization_coverage"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/mva_training.yaml"))
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--scores-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--cpv-signed", action="store_true")
    return parser.parse_args()


def choose_threshold(
    labels: np.ndarray,
    scores: np.ndarray,
    physical_weights: np.ndarray,
) -> tuple[float, list[dict[str, float]]]:
    if bool(np.any(~np.isfinite(physical_weights))) or bool(np.any(physical_weights <= 0)):
        raise RuntimeError("Threshold selection requires positive ordinary weight_phys")
    grid = np.linspace(0.0, 1.0, 1001)
    scan = []
    best_value = -np.inf
    best_threshold = 0.0
    for threshold in grid:
        selected = scores >= threshold
        signal = float(physical_weights[selected & (labels == 1)].sum())
        background = float(physical_weights[selected & (labels == 0)].sum())
        significance = signal / np.sqrt(signal + background) if signal + background > 0 else 0.0
        scan.append({
            "threshold": float(threshold),
            "signal": signal,
            "background": background,
            "signal_over_background": signal / background if background > 0 else None,
            "signal_over_sqrt_signal_plus_background": float(significance),
        })
        if significance > best_value + 1e-15:
            best_value = float(significance)
            best_threshold = float(threshold)
    return best_threshold, scan


def metric_block(
    labels: np.ndarray,
    scores: np.ndarray,
    training_weight: np.ndarray | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"events": int(len(labels))}
    if len(labels) == 0 or len(np.unique(labels)) < 2:
        result.update({"auc": None, "logloss": None})
        return result
    result["auc"] = float(roc_auc_score(labels, scores))
    result["logloss"] = float(log_loss(labels, scores, labels=[0, 1]))
    if training_weight is not None:
        result["auc_weight_train"] = float(
            roc_auc_score(labels, scores, sample_weight=training_weight)
        )
        result["logloss_weight_train"] = float(
            log_loss(labels, scores, sample_weight=training_weight, labels=[0, 1])
        )
    return result


def read_score(
    path: Path,
    arrays: dict[str, Any],
    *,
    model_hash: str,
    catalog_hash: str,
    provenance_hash: str,
    implementation_hash: str,
    apply_script_hash: str,
) -> np.ndarray:
    if not path.is_file():
        raise RuntimeError(f"Missing score shard: {path}")
    with h5py.File(path, "r") as source:
        if not bool(source.attrs.get("complete", False)):
            raise RuntimeError(f"Incomplete score shard: {path}")
        checks = {
            "job_key": arrays["job_key"],
            "source_hdf5_sha256": arrays["source_hdf5_sha256"],
            "model_sha256": model_hash,
            "weights_catalog_hash": catalog_hash,
            "provenance_sha256": provenance_hash,
            "implementation_hash": implementation_hash,
            "apply_script_sha256": apply_script_hash,
        }
        for key, expected in checks.items():
            if str(source.attrs.get(key, "")) != str(expected):
                raise RuntimeError(f"{path}: score provenance mismatch for {key}")
        event_index = np.asarray(source["event_index"][:], dtype=np.int64)
        if not np.array_equal(event_index, arrays["event_index"]):
            raise RuntimeError(f"{path}: score/source event_index order mismatch")
        score = np.asarray(source["score"][:], dtype=np.float64)
    if len(score) != len(arrays["y"]):
        raise RuntimeError(f"{path}: score/source row-count mismatch")
    require_finite_probability(score, str(path))
    return score


def concatenate_rows(rows: list[dict[str, np.ndarray]]) -> dict[str, np.ndarray]:
    if not rows:
        return {
            "y": np.empty(0, dtype=np.int8),
            "score": np.empty(0),
            "weight_phys": np.empty(0),
            "polarization": np.empty(0, dtype="U5"),
            "sample_key": np.empty(0, dtype="U8"),
            "analysis_category": np.empty(0, dtype=object),
        }
    return {key: np.concatenate([row[key] for row in rows]) for key in rows[0]}


def selected_yields(data: dict[str, np.ndarray], threshold: float) -> dict[str, Any]:
    selected = data["score"] >= threshold
    output: dict[str, Any] = {}
    for field in ("analysis_category", "polarization", "sample_key"):
        values: dict[str, dict[str, float]] = {}
        for value in sorted(set(data[field].tolist())):
            mask = selected & (data[field] == value)
            values[str(value)] = {
                "events": int(mask.sum()),
                "expected_yield": float(data["weight_phys"][mask].sum()),
            }
        output[field] = values
    return output


def main() -> None:
    args = parse_args()
    if args.cpv_signed:
        raise RuntimeError(
            "CPV_EVENT_SIGN_JOIN_UNAVAILABLE: signed CPV evaluation is not implemented"
        )
    authority = load_authority(args.config)
    model_path = args.model if args.model.is_absolute() else authority.root / args.model
    provenance = json.loads((model_path.parent / "provenance.json").read_text())
    provenance_path = model_path.parent / "provenance.json"
    provenance_hash = sha256_file(provenance_path)
    model_hash = sha256_file(model_path)
    if provenance.get("model_sha256") != model_hash:
        raise RuntimeError("Model/provenance SHA256 mismatch")
    if provenance.get("weights_catalog_hash") != authority.catalog_hash:
        raise RuntimeError("Model/catalog mismatch")
    verify_implementation_identity(authority.root, provenance.get("implementation"))
    implementation_hash = canonical_json_hash(provenance["implementation"])
    apply_script_hash = provenance["implementation"]["script_sha256"][
        "scripts/mva/apply_selection.py"
    ]
    try:
        import xgboost as xgb
    except ImportError as exc:
        raise RuntimeError("xgboost is required; run: source env/setup.sh") from exc
    booster = xgb.Booster()
    booster.load_model(model_path)
    validate_best_iteration(booster, provenance)
    coefficient_map = {
        tuple([int(key.split(":", 1)[0]), key.split(":", 1)[1]]): float(value)
        for key, value in provenance["training_weight_coefficients"].items()
    }

    ordinary_rows: dict[str, list[dict[str, np.ndarray]]] = defaultdict(list)
    cpv_rows: list[dict[str, np.ndarray]] = []
    keys = selected_job_keys(authority, include_cpv=True)
    if args.smoke:
        keys = choose_smoke_jobs(authority, keys)

    for key in keys:
        arrays = load_job_arrays(authority, key)
        score = read_score(
            args.scores_dir / f"{key}.scores.h5",
            arrays,
            model_hash=model_hash,
            catalog_hash=authority.catalog_hash,
            provenance_hash=provenance_hash,
            implementation_hash=implementation_hash,
            apply_script_hash=apply_script_hash,
        )
        row = {
            "y": arrays["y"],
            "score": score,
            "weight_phys": arrays["weight_phys"],
            "polarization": arrays["polarization"],
            "sample_key": arrays["sample_key"],
            "analysis_category": arrays["analysis_category"],
        }
        if str(arrays["sample_key"][0]) == CPV_SAMPLE:
            cpv_rows.append(row)
        else:
            ordinary_rows[arrays["split"]].append(row)

    data = {split: concatenate_rows(rows) for split, rows in ordinary_rows.items()}
    for required in ("train", "validation", "test"):
        if required not in data:
            raise RuntimeError(f"Missing ordinary {required} scores")
    threshold, scan = choose_threshold(
        data["validation"]["y"],
        data["validation"]["score"],
        data["validation"]["weight_phys"],
    )
    metrics = {}
    for split, values in data.items():
        train_weight = np.asarray([
            coefficient_map[(int(label), str(pol))]
            for label, pol in zip(values["y"], values["polarization"])
        ], dtype=np.float64)
        metrics[split] = metric_block(values["y"], values["score"], train_weight)

    strata: dict[str, Any] = {}
    for split, values in data.items():
        strata[split] = {}
        for field in ("analysis_category", "polarization", "sample_key"):
            strata[split][field] = {}
            for value in sorted(set(values[field].tolist())):
                mask = values[field] == value
                strata[split][field][str(value)] = metric_block(
                    values["y"][mask], values["score"][mask]
                )

    cpv = concatenate_rows(cpv_rows)
    cpv_safety: dict[str, Any] = {
        "signed_interference_available": False,
        "signed_interference_failure_code": "CPV_EVENT_SIGN_JOIN_UNAVAILABLE",
        "events": int(len(cpv["score"])),
        "unweighted_efficiency_by_polarization": {},
    }
    for polarization in sorted(set(cpv["polarization"].tolist())):
        mask = cpv["polarization"] == polarization
        cpv_safety["unweighted_efficiency_by_polarization"][polarization] = float(
            np.mean(cpv["score"][mask] >= threshold)
        )

    report = {
        "schema_version": 1,
        "analysis_name": authority.config["analysis_name"],
        "threshold_status": THRESHOLD_STATUS,
        "threshold_selection_split": "validation",
        "threshold_statistic": "S/sqrt(S+B), ordinary weight_phys, no systematics",
        "threshold": threshold,
        "threshold_scan": scan,
        "metrics": metrics,
        "strata": strata,
        "validation_selected_yields": selected_yields(data["validation"], threshold),
        "test_selected_yields": selected_yields(data["test"], threshold),
        "cpv_safety": cpv_safety,
        "model_sha256": model_hash,
        "provenance_sha256": provenance_hash,
        "implementation_hash": implementation_hash,
        "apply_script_sha256": apply_script_hash,
        "weights_catalog_hash": authority.catalog_hash,
        "test_used_for_threshold_selection": False,
    }
    atomic_json(args.output, report)
    print(json.dumps({
        "output": str(args.output),
        "threshold": threshold,
        "threshold_status": THRESHOLD_STATUS,
        "test_auc": metrics["test"]["auc"],
        "cpv_events": cpv_safety["events"],
    }, indent=2))


if __name__ == "__main__":
    main()
