#!/usr/bin/env python3
"""Apply one frozen selection-MVA model to catalogued HDF5 jobs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import h5py
import numpy as np

try:
    from .selection_mva_common import (
        BASELINE_FEATURES,
        atomic_json,
        canonical_json_hash,
        choose_smoke_jobs,
        feature_hash,
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
        BASELINE_FEATURES,
        atomic_json,
        canonical_json_hash,
        choose_smoke_jobs,
        feature_hash,
        load_authority,
        load_job_arrays,
        require_finite_probability,
        selected_job_keys,
        sha256_file,
        validate_best_iteration,
        verify_implementation_identity,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/mva_training.yaml"))
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--job-list", type=Path, help="One canonical job_key per line")
    parser.add_argument("--batch-id", default="all")
    parser.add_argument("--include-cpv", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    return parser.parse_args()


def read_job_list(path: Path | None) -> list[str] | None:
    if path is None:
        return None
    values = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if len(values) != len(set(values)):
        raise RuntimeError(f"Duplicate job_key in {path}")
    if not values:
        raise RuntimeError(f"Empty job list: {path}")
    return values


def write_score_file(
    output_path: Path,
    arrays: dict,
    score: np.ndarray,
    *,
    model_hash: str,
    catalog_hash: str,
    provenance_hash: str,
    implementation_hash: str,
    apply_script_hash: str,
) -> None:
    if output_path.exists():
        raise RuntimeError(f"Refusing to overwrite score shard: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp.{os.getpid()}")
    with h5py.File(temporary, "w") as target:
        target.create_dataset("event_index", data=arrays["event_index"], compression="gzip")
        target.create_dataset("score", data=score.astype(np.float32), compression="gzip")
        target.attrs["schema_version"] = 2
        target.attrs["complete"] = True
        target.attrs["n_events"] = len(score)
        target.attrs["job_key"] = arrays["job_key"]
        target.attrs["sample_key"] = str(arrays["sample_key"][0])
        target.attrs["polarization"] = str(arrays["polarization"][0])
        target.attrs["source_hdf5"] = str(arrays["source_hdf5"])
        target.attrs["source_hdf5_sha256"] = arrays["source_hdf5_sha256"]
        target.attrs["model_sha256"] = model_hash
        target.attrs["weights_catalog_hash"] = catalog_hash
        target.attrs["provenance_sha256"] = provenance_hash
        target.attrs["implementation_hash"] = implementation_hash
        target.attrs["apply_script_sha256"] = apply_script_hash
        target.attrs["feature_hash"] = feature_hash()
        target.flush()
    temporary.replace(output_path)


def validate_score_file(
    output_path: Path,
    arrays: dict,
    *,
    model_hash: str,
    catalog_hash: str,
    provenance_hash: str,
    implementation_hash: str,
    apply_script_hash: str,
) -> int:
    with h5py.File(output_path, "r") as source:
        checks = {
            "complete": True,
            "n_events": len(arrays["event_index"]),
            "job_key": arrays["job_key"],
            "sample_key": str(arrays["sample_key"][0]),
            "polarization": str(arrays["polarization"][0]),
            "source_hdf5": str(arrays["source_hdf5"]),
            "source_hdf5_sha256": arrays["source_hdf5_sha256"],
            "model_sha256": model_hash,
            "weights_catalog_hash": catalog_hash,
            "provenance_sha256": provenance_hash,
            "implementation_hash": implementation_hash,
            "apply_script_sha256": apply_script_hash,
            "feature_hash": feature_hash(),
        }
        for key, expected in checks.items():
            if str(source.attrs.get(key, "")) != str(expected):
                raise RuntimeError(f"{output_path}: existing score mismatch for {key}")
        event_index = np.asarray(source["event_index"][:], dtype=np.int64)
        if not np.array_equal(event_index, arrays["event_index"]):
            raise RuntimeError(f"{output_path}: existing score event order mismatch")
        score = np.asarray(source["score"][:], dtype=np.float64)
    if len(score) != len(arrays["event_index"]):
        raise RuntimeError(f"{output_path}: existing score row-count mismatch")
    require_finite_probability(score, str(output_path))
    return len(score)


def reusable_score_file(output_path: Path, arrays: dict, **provenance: str) -> bool:
    if not output_path.exists():
        return False
    validate_score_file(output_path, arrays, **provenance)
    return True


def main() -> None:
    args = parse_args()
    authority = load_authority(args.config)
    model_path = args.model if args.model.is_absolute() else authority.root / args.model
    if not model_path.is_file():
        raise RuntimeError(f"Missing model: {model_path}")
    provenance_path = model_path.parent / "provenance.json"
    provenance = json.loads(provenance_path.read_text())
    provenance_hash = sha256_file(provenance_path)
    model_hash = sha256_file(model_path)
    if provenance.get("model_sha256") != model_hash:
        raise RuntimeError("Model/provenance SHA256 mismatch")
    if provenance.get("features") != BASELINE_FEATURES:
        raise RuntimeError("Model feature contract mismatch")
    if provenance.get("weights_catalog_hash") != authority.catalog_hash:
        raise RuntimeError("Model was trained against a different weights catalog")
    verify_implementation_identity(authority.root, provenance.get("implementation"))
    implementation_hash = canonical_json_hash(provenance["implementation"])
    apply_script_hash = sha256_file(Path(__file__).resolve())

    try:
        import xgboost as xgb
    except ImportError as exc:
        raise RuntimeError("xgboost is required; run: source env/setup.sh") from exc
    booster = xgb.Booster()
    booster.load_model(model_path)
    best_iteration = validate_best_iteration(booster, provenance)

    requested = read_job_list(args.job_list)
    keys = selected_job_keys(
        authority,
        include_cpv=args.include_cpv,
        requested=requested,
    )
    if args.smoke:
        keys = choose_smoke_jobs(authority, keys)
    completed = []
    reused = 0
    for key in keys:
        arrays = load_job_arrays(authority, key)
        output_path = args.output_dir / f"{key}.scores.h5"
        score_provenance = {
            "model_hash": model_hash,
            "catalog_hash": authority.catalog_hash,
            "provenance_hash": provenance_hash,
            "implementation_hash": implementation_hash,
            "apply_script_hash": apply_script_hash,
        }
        if reusable_score_file(output_path, arrays, **score_provenance):
            completed.append({"job_key": key, "n_events": len(arrays["event_index"])})
            reused += 1
            continue
        matrix = xgb.DMatrix(arrays["X"], feature_names=BASELINE_FEATURES)
        score = booster.predict(matrix, iteration_range=(0, best_iteration + 1))
        require_finite_probability(score, key)
        write_score_file(
            output_path,
            arrays,
            score,
            model_hash=model_hash,
            catalog_hash=authority.catalog_hash,
            provenance_hash=provenance_hash,
            implementation_hash=implementation_hash,
            apply_script_hash=apply_script_hash,
        )
        completed.append({"job_key": key, "n_events": len(score)})

    completion_path = args.output_dir / f"completion-{args.batch_id}.json"
    atomic_json(completion_path, {
        "schema_version": 1,
        "complete": True,
        "batch_id": args.batch_id,
        "jobs": completed,
        "events": sum(item["n_events"] for item in completed),
        "model_sha256": model_hash,
        "provenance_sha256": provenance_hash,
        "implementation_hash": implementation_hash,
        "apply_script_sha256": apply_script_hash,
        "weights_catalog_hash": authority.catalog_hash,
        "include_cpv": args.include_cpv,
        "reused_score_shards": reused,
        "written_score_shards": len(completed) - reused,
    })
    print(json.dumps({
        "completion": str(completion_path),
        "jobs": len(completed),
        "events": sum(item["n_events"] for item in completed),
    }, indent=2))


if __name__ == "__main__":
    main()
