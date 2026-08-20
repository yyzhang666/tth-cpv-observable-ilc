from __future__ import annotations

import csv
import json
from pathlib import Path

import h5py
import numpy as np
import yaml

from scripts.mva.selection_mva_common import (
    BASELINE_FEATURES,
    canonical_json_hash,
    sha256_file,
)


def write_h5(
    path: Path,
    *,
    job_key: str = "job-a",
    sample_key: str = "ttbb",
    polarization: str = "eL.pR",
    split_group: str = "group-a",
    logical_shard: str = "shard-a",
    physical_part: str = "full",
    categories: tuple[str, ...] = ("ttbb", "ttbb", "ttbb", "ttbb"),
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    string_dtype = h5py.string_dtype("utf-8")
    n_events = len(categories)
    with h5py.File(path, "w") as target:
        for index, name in enumerate(BASELINE_FEATURES):
            target.create_dataset(
                name,
                data=np.linspace(0.1 + index, 0.4 + index, n_events),
            )
        identities = {
            "job_key": job_key,
            "sample_key": sample_key,
            "polarization": polarization,
            "logical_shard": logical_shard,
            "physical_part": physical_part,
            "split_group": split_group,
            "process_mask": "P6f_eexxxx" if sample_key == "4f2l" else "",
        }
        for name, value in identities.items():
            target.create_dataset(name, data=np.asarray([value] * n_events, dtype=object), dtype=string_dtype)
        target.create_dataset(
            "analysis_category",
            data=np.asarray(categories, dtype=object),
            dtype=string_dtype,
        )
        target.create_dataset("event_index", data=np.arange(n_events, dtype=np.int64))
        target.attrs["n_events"] = n_events
        target.attrs["baseline_features"] = json.dumps(BASELINE_FEATURES)


def write_authority(
    root: Path,
    *,
    sample_key: str = "ttbb",
    polarization: str = "eL.pR",
    split_name: str = "train",
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    h5_path = root / "job-a.h5"
    categories = ("tth-hbb", "tth-nonbb", "tth-hbb", "tth-nonbb") if sample_key == "tth-sm" else (sample_key,) * 4
    write_h5(
        h5_path,
        sample_key=sample_key,
        polarization=polarization,
        categories=categories,
    )
    mva_config = root / "mva.yaml"
    mva_config.write_text("meta: {analysis_name: test}\n")
    manifest = root / "manifest.csv"
    with manifest.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["job_key"])
        writer.writeheader()
        writer.writerow({"job_key": "job-a"})
    inventory = root / "inventory.json"
    inventory.write_text(json.dumps({
        "scenario_id": "scenario",
        "inventory_content_hash": "inventory-hash",
    }))
    split_path = root / "split.json"
    split_job = {
        "job_key": "job-a",
        "sample_key": sample_key,
        "polarization": polarization,
        "split": split_name,
        "n_events": 4,
        "output_hdf5": str(h5_path),
        "logical_shard": "shard-a",
        "physical_part": "full",
        "split_group": "group-a",
    }
    split = {
        "assignment_hash": "assignment-hash",
        "source": {
            "config_sha256": sha256_file(mva_config),
            "manifest_sha256": sha256_file(manifest),
        },
        "jobs": [split_job],
    }
    split_path.write_text(json.dumps(split))
    catalog_path = root / "weights.json"
    catalog_job = {
        **split_job,
        "analysis_category_counts": (
            {"tth-hbb": 2, "tth-nonbb": 2}
            if sample_key == "tth-sm" else {sample_key: 4}
        ),
        "process_mask": None,
        "use_for_training": sample_key != "tth-cpv",
        "normalization_type": (
            "signed_interference" if sample_key == "tth-cpv" else "positive_cross_section"
        ),
        "weight_phys": None if sample_key == "tth-cpv" else 0.25,
        "hdf5_sha256": sha256_file(h5_path),
    }
    catalog = {
        "scenario_id": "scenario",
        "inventory_content_hash": "inventory-hash",
        "split_assignment_hash": "assignment-hash",
        "source": {
            "mva_config_sha256": sha256_file(mva_config),
            "manifest_sha256": sha256_file(manifest),
            "physical_inventory_sha256": sha256_file(inventory),
            "split_assignment_sha256": sha256_file(split_path),
        },
        "audit": {"jobs_total": 1, "events_total": 4},
        "jobs": [catalog_job],
    }
    catalog["weights_catalog_hash"] = canonical_json_hash(catalog)
    catalog_path.write_text(json.dumps(catalog))
    training_config = root / "training.yaml"
    training_config.write_text(yaml.safe_dump({
        "scenario_id": "scenario",
        "features": BASELINE_FEATURES,
        "paths": {
            "mva_config": str(mva_config),
            "manifest": str(manifest),
            "split_assignment": str(split_path),
            "physical_inventory": str(inventory),
            "weights_catalog": str(catalog_path),
        },
        "smoke": {
            "jobs_per_sample_polarization_split": 1,
            "max_events_per_job": 4,
        },
    }, sort_keys=False))
    return training_config


def rehash_catalog(config_path: Path) -> None:
    config = yaml.safe_load(config_path.read_text())
    catalog_path = Path(config["paths"]["weights_catalog"])
    split_path = Path(config["paths"]["split_assignment"])
    catalog = json.loads(catalog_path.read_text())
    catalog["source"]["split_assignment_sha256"] = sha256_file(split_path)
    catalog["weights_catalog_hash"] = canonical_json_hash(catalog, "weights_catalog_hash")
    catalog_path.write_text(json.dumps(catalog))


def write_cpv_sidecar(path: Path, *, n: int = 4, bad_row: int | None = None) -> None:
    sigma = 0.4
    error = 0.01
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "event", "sign", "n_generated", "sigma_absint",
            "sigma_absint_error", "event_weight_signed",
        ])
        writer.writeheader()
        for event in range(1, n + 1):
            sign = 1 if event % 2 else -1
            writer.writerow({
                "event": event,
                "sign": 0 if event == bad_row else sign,
                "n_generated": n,
                "sigma_absint": sigma,
                "sigma_absint_error": error,
                "event_weight_signed": sign * sigma / n,
            })
