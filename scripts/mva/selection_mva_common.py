#!/usr/bin/env python3
"""Strict, catalog-driven I/O shared by selection-MVA commands.

The frozen HDF5 directory is never used for discovery. Every consumer starts
from the split and physical-weights catalogs and proves that each HDF5 is the
catalogued object before reading model features.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import h5py
import numpy as np
import yaml


BASELINE_FEATURES = [
    "y45", "y56", "y67",
    "btag_1", "btag_2", "btag_3", "btag_4",
    "ctag_1", "ctag_2", "ctag_3", "ctag_4",
    "mH_postfit", "mW_had_postfit", "mt_had_postfit", "mt_lep_postfit",
    "fitchi2", "chi2_over_ndof", "fitprob",
    "final_selection_score", "final_fit_score", "final_flavor_score",
    "lepton_E", "lepton_theta", "lepton_pt", "lepton_charge",
]

LEAKAGE_EXACT = {
    "analysis_category", "class_label", "event_category", "manifest_class_label",
    "sample_key", "sample_name", "generator", "process", "process_mask",
    "polarization", "helicity", "source", "job_key", "logical_shard",
    "physical_part", "split", "split_group", "event", "event_id",
    "event_index", "event_number", "run_number", "weight_phys", "weight_train",
    "sign", "event_weight_signed", "lepton_flavor", "best_combo_id",
}
LEAKAGE_PREFIXES = ("truth_", "weight_interference", "idx_", "nu_fit_")
TRAINING_SAMPLES = {"tth-sm", "ttz", "ttbb", "6q", "4f2l"}
CPV_SAMPLE = "tth-cpv"
IMPLEMENTATION_FILES = (
    "scripts/mva/selection_mva_common.py",
    "scripts/mva/train_selection_mva.py",
    "scripts/mva/apply_selection.py",
    "scripts/mva/evaluate_selection.py",
    "scripts/mva/prepare_selection_mva_condor.py",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def implementation_identity(root: Path) -> dict[str, Any]:
    script_hashes = {}
    for relative in IMPLEMENTATION_FILES:
        path = root / relative
        if not path.is_file():
            raise RuntimeError(f"Missing MVA implementation file: {path}")
        script_hashes[relative] = sha256_file(path)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip())
    return {
        "git_commit": revision,
        "git_tracked_changes_present": dirty,
        "script_sha256": script_hashes,
    }


def verify_implementation_identity(
    root: Path,
    expected: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(expected, dict):
        raise RuntimeError("Model provenance lacks implementation identity")
    expected_hashes = expected.get("script_sha256")
    if not isinstance(expected_hashes, dict) or set(expected_hashes) != set(IMPLEMENTATION_FILES):
        raise RuntimeError("Model provenance has incomplete implementation hashes")
    observed = implementation_identity(root)
    for relative in IMPLEMENTATION_FILES:
        if observed["script_sha256"][relative] != expected_hashes[relative]:
            raise RuntimeError(f"MVA implementation hash mismatch: {relative}")
    return observed


def validate_best_iteration(booster: Any, provenance: dict[str, Any]) -> int:
    embedded = booster.attr("best_iteration")
    if embedded is None:
        raise RuntimeError("Model lacks embedded best_iteration")
    declared = int(provenance.get("best_iteration", -1))
    if int(embedded) != declared:
        raise RuntimeError("Model/provenance best_iteration mismatch")
    return declared


def canonical_json_hash(payload: dict[str, Any], excluded_key: str | None = None) -> str:
    content = dict(payload)
    if excluded_key is not None:
        content.pop(excluded_key, None)
    encoded = json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def decode(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, np.bytes_):
        return bytes(value).decode("utf-8")
    return str(value)


def load_json(path: Path) -> dict[str, Any]:
    with path.open() as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return value


def load_training_config(path: Path) -> tuple[dict[str, Any], Path, Path]:
    root = repo_root()
    resolved = resolve_path(root, path)
    with resolved.open() as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise RuntimeError(f"Invalid training config: {resolved}")
    validate_feature_list(list(config.get("features", [])))
    return config, resolved, root


def validate_feature_list(features: Sequence[str]) -> None:
    if list(features) != BASELINE_FEATURES:
        raise RuntimeError(
            "baseline-v1 features must exactly match the frozen 25-feature order"
        )
    forbidden = [
        name for name in features
        if name in LEAKAGE_EXACT or name.startswith(LEAKAGE_PREFIXES)
    ]
    if forbidden:
        raise RuntimeError(f"Forbidden leakage features: {forbidden}")


def unique_records(records: Sequence[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for record in records:
        key = str(record.get("job_key", ""))
        if not key:
            raise RuntimeError(f"{label}: empty job_key")
        if key in output:
            raise RuntimeError(f"{label}: duplicate job_key {key}")
        output[key] = record
    return output


@dataclass(frozen=True)
class CatalogAuthority:
    config: dict[str, Any]
    config_path: Path
    root: Path
    split_path: Path
    catalog_path: Path
    inventory_path: Path
    mva_config_path: Path
    manifest_path: Path
    split: dict[str, Any]
    catalog: dict[str, Any]
    split_jobs: dict[str, dict[str, Any]]
    catalog_jobs: dict[str, dict[str, Any]]

    @property
    def catalog_hash(self) -> str:
        return str(self.catalog["weights_catalog_hash"])


def load_authority(config_path: Path) -> CatalogAuthority:
    config, resolved_config, root = load_training_config(config_path)
    paths = config["paths"]
    split_path = resolve_path(root, paths["split_assignment"])
    catalog_path = resolve_path(root, paths["weights_catalog"])
    inventory_path = resolve_path(root, paths["physical_inventory"])
    mva_config_path = resolve_path(root, paths["mva_config"])
    manifest_path = resolve_path(root, paths["manifest"])
    for path in (split_path, catalog_path, inventory_path, mva_config_path, manifest_path):
        if not path.is_file():
            raise RuntimeError(f"Missing authority file: {path}")

    split = load_json(split_path)
    catalog = load_json(catalog_path)
    scenario = str(config["scenario_id"])
    if catalog.get("scenario_id") != scenario:
        raise RuntimeError("training config / weights catalog scenario mismatch")
    inventory = load_json(inventory_path)
    if inventory.get("scenario_id") != scenario:
        raise RuntimeError("training config / inventory scenario mismatch")
    if catalog.get("inventory_content_hash") != inventory.get("inventory_content_hash"):
        raise RuntimeError("weights catalog references a different inventory content hash")
    observed_catalog_hash = canonical_json_hash(catalog, "weights_catalog_hash")
    if observed_catalog_hash != catalog.get("weights_catalog_hash"):
        raise RuntimeError("weights catalog internal content hash mismatch")

    source = catalog.get("source", {})
    expected_sources = {
        "mva_config_sha256": mva_config_path,
        "manifest_sha256": manifest_path,
        "physical_inventory_sha256": inventory_path,
        "split_assignment_sha256": split_path,
    }
    for key, path in expected_sources.items():
        if source.get(key) != sha256_file(path):
            raise RuntimeError(f"stale weights catalog source hash: {key}")
    split_source = split.get("source", {})
    if split_source.get("config_sha256") != sha256_file(mva_config_path):
        raise RuntimeError("stale split assignment config hash")
    if split_source.get("manifest_sha256") != sha256_file(manifest_path):
        raise RuntimeError("stale split assignment manifest hash")
    if catalog.get("split_assignment_hash") != split.get("assignment_hash"):
        raise RuntimeError("split assignment semantic hash mismatch")

    split_jobs = unique_records(split.get("jobs", []), "split assignment")
    catalog_jobs = unique_records(catalog.get("jobs", []), "weights catalog")
    if set(split_jobs) != set(catalog_jobs):
        missing = sorted(set(split_jobs) - set(catalog_jobs))[:5]
        extra = sorted(set(catalog_jobs) - set(split_jobs))[:5]
        raise RuntimeError(f"split/catalog exact job-set mismatch: missing={missing} extra={extra}")
    expected_jobs = int(catalog.get("audit", {}).get("jobs_total", -1))
    if expected_jobs != len(catalog_jobs):
        raise RuntimeError("weights catalog jobs_total does not close")
    expected_events = int(catalog.get("audit", {}).get("events_total", -1))
    if expected_events != sum(int(row["n_events"]) for row in catalog_jobs.values()):
        raise RuntimeError("weights catalog events_total does not close")

    return CatalogAuthority(
        config=config,
        config_path=resolved_config,
        root=root,
        split_path=split_path,
        catalog_path=catalog_path,
        inventory_path=inventory_path,
        mva_config_path=mva_config_path,
        manifest_path=manifest_path,
        split=split,
        catalog=catalog,
        split_jobs=split_jobs,
        catalog_jobs=catalog_jobs,
    )


def unique_h5_string(h5: h5py.File, key: str) -> str:
    if key not in h5:
        raise RuntimeError(f"HDF5 missing identity dataset {key!r}")
    values = {decode(value) for value in np.unique(h5[key][:])}
    if len(values) != 1:
        raise RuntimeError(f"HDF5 dataset {key!r} is not constant: {sorted(values)}")
    return next(iter(values))


def validate_job_hdf5(
    authority: CatalogAuthority,
    job_key: str,
    *,
    verify_hash: bool = True,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    catalog_row = authority.catalog_jobs[job_key]
    split_row = authority.split_jobs[job_key]
    for field in (
        "job_key", "sample_key", "polarization", "split", "n_events", "output_hdf5"
    ):
        left = catalog_row.get(field)
        right = split_row.get(field)
        if str(left) != str(right):
            raise RuntimeError(f"{job_key}: split/catalog {field} mismatch {left!r} != {right!r}")
    h5_path = resolve_path(authority.root, catalog_row["output_hdf5"])
    if not h5_path.is_file():
        raise RuntimeError(f"{job_key}: missing catalog HDF5 {h5_path}")
    expected_hash = catalog_row.get("hdf5_sha256")
    if not expected_hash:
        raise RuntimeError(f"{job_key}: weights catalog lacks hdf5_sha256; rerun prepare_mva_weights.py")
    if verify_hash and sha256_file(h5_path) != expected_hash:
        raise RuntimeError(f"{job_key}: HDF5 content hash mismatch")

    with h5py.File(h5_path, "r") as h5:
        n_events = int(catalog_row["n_events"])
        if int(h5.attrs.get("n_events", -1)) != n_events:
            raise RuntimeError(f"{job_key}: HDF5 n_events attribute mismatch")
        identities = {
            "job_key": job_key,
            "sample_key": catalog_row["sample_key"],
            "polarization": catalog_row["polarization"],
            "logical_shard": split_row["logical_shard"],
            "physical_part": split_row["physical_part"],
            "split_group": split_row["split_group"],
        }
        for key, expected in identities.items():
            if unique_h5_string(h5, key) != str(expected):
                raise RuntimeError(f"{job_key}: HDF5 {key} mismatch")
        declared = json.loads(decode(h5.attrs.get("baseline_features", "[]")))
        if declared != BASELINE_FEATURES:
            raise RuntimeError(f"{job_key}: frozen baseline feature order mismatch")
        required = set(BASELINE_FEATURES) | {
            "analysis_category", "event_index", "process_mask", "sample_key",
            "polarization", "job_key", "logical_shard", "physical_part", "split_group",
        }
        missing = sorted(required - set(h5.keys()))
        if missing:
            raise RuntimeError(f"{job_key}: HDF5 missing datasets {missing}")
        for name, dataset in h5.items():
            if dataset.shape and int(dataset.shape[0]) != n_events:
                raise RuntimeError(f"{job_key}: dataset {name} length mismatch")
        categories, counts = np.unique(h5["analysis_category"][:], return_counts=True)
        observed_categories = {decode(k): int(v) for k, v in zip(categories, counts)}
        if observed_categories != catalog_row.get("analysis_category_counts"):
            raise RuntimeError(f"{job_key}: analysis-category counts mismatch")
        if catalog_row["sample_key"] in {"6q", "4f2l"}:
            observed_mask = unique_h5_string(h5, "process_mask")
            expected_mask = str(catalog_row.get("process_mask") or "")
            if observed_mask.removeprefix("P6f_") != expected_mask.removeprefix("P6f_"):
                raise RuntimeError(f"{job_key}: process-mask mismatch")
    return h5_path, catalog_row, split_row


def selected_job_keys(
    authority: CatalogAuthority,
    *,
    splits: set[str] | None = None,
    include_cpv: bool = False,
    requested: Iterable[str] | None = None,
) -> list[str]:
    requested_set = set(requested) if requested is not None else None
    if requested_set is not None:
        unknown = sorted(requested_set - set(authority.catalog_jobs))
        if unknown:
            raise RuntimeError(f"Requested jobs absent from catalog: {unknown[:5]}")
    output = []
    for key in sorted(authority.catalog_jobs):
        row = authority.catalog_jobs[key]
        if requested_set is not None and key not in requested_set:
            continue
        if splits is not None and row["split"] not in splits:
            continue
        if row["sample_key"] == CPV_SAMPLE and not include_cpv:
            continue
        if row["sample_key"] != CPV_SAMPLE and not bool(row.get("use_for_training")):
            continue
        output.append(key)
    if requested_set is not None and set(output) != requested_set:
        excluded = sorted(requested_set - set(output))[:5]
        raise RuntimeError(
            "Requested jobs are excluded by the training/CPV contract; "
            f"use the explicit CPV option where appropriate: {excluded}"
        )
    return output


def binary_labels(analysis_category: np.ndarray, sample_key: str) -> np.ndarray:
    categories = np.asarray([decode(x) for x in analysis_category], dtype=object)
    if sample_key == CPV_SAMPLE:
        return np.full(len(categories), -1, dtype=np.int8)
    if sample_key == "tth-sm":
        allowed = np.isin(categories, ["tth-hbb", "tth-nonbb"])
        if not bool(np.all(allowed)):
            raise RuntimeError("tth-sm contains an unexpected analysis_category")
        return (categories == "tth-hbb").astype(np.int8)
    if sample_key in TRAINING_SAMPLES:
        return np.zeros(len(categories), dtype=np.int8)
    raise RuntimeError(f"Unsupported sample for binary labels: {sample_key}")


def load_job_arrays(
    authority: CatalogAuthority,
    job_key: str,
    *,
    max_events: int | None = None,
    verify_hash: bool = True,
) -> dict[str, Any]:
    path, row, split_row = validate_job_hdf5(authority, job_key, verify_hash=verify_hash)
    count = int(row["n_events"])
    stop = count if max_events is None else min(count, max_events)
    with h5py.File(path, "r") as h5:
        features = np.empty((stop, len(BASELINE_FEATURES)), dtype=np.float32)
        for index, name in enumerate(BASELINE_FEATURES):
            features[:, index] = np.asarray(h5[name][:stop], dtype=np.float32)
        if not bool(np.isfinite(features).all()):
            raise RuntimeError(f"{job_key}: non-finite model feature")
        categories_raw = h5["analysis_category"][:stop]
        categories = np.asarray([decode(x) for x in categories_raw], dtype=object)
        labels = binary_labels(categories_raw, str(row["sample_key"]))
        event_index = np.asarray(h5["event_index"][:stop], dtype=np.int64)
    weight_phys_value = row.get("weight_phys")
    weight_phys = np.full(
        stop,
        np.nan if weight_phys_value is None else float(weight_phys_value),
        dtype=np.float64,
    )
    return {
        "X": features,
        "y": labels,
        "analysis_category": categories,
        "event_index": event_index,
        "weight_phys": weight_phys,
        "polarization": np.full(stop, str(row["polarization"]), dtype="U5"),
        "sample_key": np.full(stop, str(row["sample_key"]), dtype="U8"),
        "split": str(row["split"]),
        "job_key": job_key,
        "source_hdf5": path,
        "source_hdf5_sha256": str(row["hdf5_sha256"]),
        "normalization_type": str(row["normalization_type"]),
        "split_group": str(split_row["split_group"]),
    }


def choose_smoke_jobs(authority: CatalogAuthority, keys: Sequence[str]) -> list[str]:
    per_cell: Counter[tuple[str, str, str]] = Counter()
    output = []
    limit = int(
        authority.config["smoke"]["jobs_per_sample_polarization_split"]
    )
    for key in keys:
        row = authority.catalog_jobs[key]
        cell = (
            str(row["sample_key"]),
            str(row["polarization"]),
            str(row["split"]),
        )
        if per_cell[cell] >= limit:
            continue
        output.append(key)
        per_cell[cell] += 1
    return output


def load_matrix(
    authority: CatalogAuthority,
    keys: Sequence[str],
    *,
    max_events_per_job: int | None = None,
    verify_hash: bool = True,
) -> dict[str, np.ndarray]:
    chunks = [
        load_job_arrays(
            authority,
            key,
            max_events=max_events_per_job,
            verify_hash=verify_hash,
        )
        for key in keys
    ]
    if not chunks:
        raise RuntimeError("No catalog jobs selected")
    total = sum(len(chunk["y"]) for chunk in chunks)
    output: dict[str, np.ndarray] = {
        "X": np.empty((total, len(BASELINE_FEATURES)), dtype=np.float32),
        "y": np.empty(total, dtype=np.int8),
        "weight_phys": np.empty(total, dtype=np.float64),
        "polarization": np.empty(total, dtype="U5"),
        "sample_key": np.empty(total, dtype="U8"),
        "analysis_category": np.empty(total, dtype=object),
        "job_key": np.empty(total, dtype=object),
        "event_index": np.empty(total, dtype=np.int64),
    }
    offset = 0
    for chunk in chunks:
        stop = offset + len(chunk["y"])
        for name in (
            "X", "y", "weight_phys", "polarization", "sample_key",
            "analysis_category", "event_index",
        ):
            output[name][offset:stop] = chunk[name]
        output["job_key"][offset:stop] = chunk["job_key"]
        offset = stop
    return output


def training_weight_coefficients(
    labels: np.ndarray,
    polarizations: np.ndarray,
) -> dict[tuple[int, str], float]:
    labels = np.asarray(labels)
    polarizations = np.asarray(polarizations)
    if set(np.unique(labels)) != {0, 1}:
        raise RuntimeError("Training split must contain both binary classes")
    total = len(labels)
    coefficients: dict[tuple[int, str], float] = {}
    expected = {0: {"eL.pL", "eL.pR", "eR.pL", "eR.pR"}, 1: {"eL.pR", "eR.pL"}}
    for label, helicities in expected.items():
        observed = set(polarizations[labels == label].tolist())
        if observed != helicities:
            raise RuntimeError(
                f"Training class {label} helicities {sorted(observed)} != {sorted(helicities)}"
            )
        for helicity in sorted(helicities):
            count = int(np.sum((labels == label) & (polarizations == helicity)))
            coefficients[(label, helicity)] = total / (2.0 * len(helicities) * count)
    return coefficients


def apply_training_weights(
    labels: np.ndarray,
    polarizations: np.ndarray,
    coefficients: dict[tuple[int, str], float],
) -> np.ndarray:
    output = np.empty(len(labels), dtype=np.float32)
    for index, (label, helicity) in enumerate(zip(labels, polarizations)):
        key = (int(label), str(helicity))
        if key not in coefficients:
            raise RuntimeError(f"No training-weight coefficient for {key}")
        output[index] = coefficients[key]
    if not bool(np.isfinite(output).all()) or bool(np.any(output <= 0)):
        raise RuntimeError("Training weights must be finite and positive")
    return output


def feature_hash(features: Sequence[str] = BASELINE_FEATURES) -> str:
    encoded = json.dumps(list(features), separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def atomic_npz(path: Path, **arrays: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}.npz")
    np.savez_compressed(temporary, **arrays)
    temporary.replace(path)


def require_finite_probability(values: np.ndarray, label: str) -> None:
    if not bool(np.isfinite(values).all()):
        raise RuntimeError(f"{label}: non-finite score")
    if bool(np.any((values < 0) | (values > 1))):
        raise RuntimeError(f"{label}: score outside [0,1]")
    if len(values) > 1 and math.isclose(float(np.min(values)), float(np.max(values))):
        raise RuntimeError(f"{label}: constant score")
