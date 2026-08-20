#!/usr/bin/env python3
"""Attach physical normalization to the frozen MVA production by provenance."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/mva_semilep.yaml"),
    )

    parser.add_argument(
        "--samples",
        type=Path,
        default=Path("configs/mva_samples.yaml"),
    )

    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open() as stream:
        return yaml.safe_load(stream)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def decode(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")

    if isinstance(value, np.bytes_):
        return bytes(value).decode("utf-8")

    return str(value)


def unique_h5_string(
    h5: h5py.File,
    key: str,
) -> str:
    if key not in h5:
        raise RuntimeError(
            f"HDF5 missing dataset {key!r}"
        )

    values = {
        decode(value)
        for value in np.unique(
            h5[key][:]
        )
    }

    if len(values) != 1:
        raise RuntimeError(
            f"HDF5 dataset {key!r} is not constant: "
            f"{sorted(values)}"
        )

    return next(iter(values))


def load_manifest(
    path: Path,
) -> dict[str, dict[str, str]]:
    with path.open(newline="") as stream:
        rows = list(
            csv.DictReader(stream)
        )

    output = {}

    for row in rows:
        job_key = row[
            "job_key"
        ]

        if job_key in output:
            raise RuntimeError(
                f"Duplicate manifest job_key: {job_key}"
            )

        output[
            job_key
        ] = row

    return output


def unique_job_records(
    rows: list[dict[str, Any]],
    label: str,
) -> dict[str, dict[str, Any]]:
    output = {}

    for row in rows:
        job_key = str(row.get("job_key", ""))

        if not job_key:
            raise RuntimeError(f"{label}: empty job_key")

        if job_key in output:
            raise RuntimeError(
                f"{label}: duplicate job_key {job_key}"
            )

        output[job_key] = row

    return output


def require_equal_field(
    job_key: str,
    field: str,
    left: Any,
    right: Any,
) -> None:
    if str(left) != str(right):
        raise RuntimeError(
            f"{job_key}: {field} mismatch {left!r} != {right!r}"
        )


def build_normalization_lookup(
    inventory: dict[str, Any],
) -> dict[
    tuple[str, str, str],
    dict[str, Any],
]:
    output = {}

    for entry in inventory[
        "normalizations"
    ]:
        process_mask = canonical_process_mask(
            entry.get(
                "process_mask"
            )
        )

        key = (
            str(entry["sample_key"]),
            str(entry["polarization"]),
            process_mask,
        )

        if key in output:
            raise RuntimeError(
                f"Duplicate normalization lookup key: {key}"
            )

        output[
            key
        ] = entry

    return output

def canonical_process_mask(value: str | None) -> str:
    """Canonicalize Whizard process-mask naming across provenance sources."""

    if value is None:
        return ""

    value = str(value).strip()

    if value.startswith("P6f_"):
        return value[len("P6f_"):]

    return value

def main() -> None:
    args = parse_args()

    config_path = resolve_path(
        args.config
    )

    samples_path = resolve_path(
        args.samples
    )

    cfg = load_yaml(
        config_path
    )

    sample_cfg = load_yaml(
        samples_path
    )

    normalization_cfg = cfg[
        "normalization"
    ]

    inventory_path = resolve_path(
        normalization_cfg[
            "physical_inventory"
        ]
    )

    split_path = resolve_path(
        normalization_cfg[
            "split_assignment"
        ]
    )

    output_path = resolve_path(
        normalization_cfg[
            "weights_catalog"
        ]
    )

    manifest_path = resolve_path(
        cfg[
            "inputs"
        ][
            "manifest"
        ]
    )

    with inventory_path.open() as stream:
        inventory = json.load(
            stream
        )

    with split_path.open() as stream:
        split_artifact = json.load(
            stream
        )

    manifest = load_manifest(
        manifest_path
    )

    scenario_id = str(
        normalization_cfg["scenario_id"]
    )

    if inventory.get("scenario_id") != scenario_id:
        raise RuntimeError(
            "MVA config / physical inventory scenario mismatch"
        )

    split_source = split_artifact.get("source", {})

    if split_source.get("config_sha256") != sha256_file(config_path):
        raise RuntimeError(
            "Split assignment is stale relative to mva_semilep.yaml"
        )

    if split_source.get("manifest_sha256") != sha256_file(manifest_path):
        raise RuntimeError(
            "Split assignment is stale relative to the MVA manifest"
        )

    split_jobs = unique_job_records(
        split_artifact.get("jobs", []),
        "split assignment",
    )

    if set(split_jobs) != set(manifest):
        missing = sorted(set(manifest) - set(split_jobs))[:5]
        extra = sorted(set(split_jobs) - set(manifest))[:5]
        raise RuntimeError(
            "Manifest/split exact job-set mismatch: "
            f"missing={missing}, extra={extra}"
        )

    norm_lookup = build_normalization_lookup(
        inventory
    )

    sample_settings = sample_cfg[
        "samples"
    ]

    jobs = []

    selected_events_by_sample = Counter()
    expected_yield_by_sample = defaultdict(float)

    selected_events_by_category = Counter()
    expected_yield_by_category = defaultdict(float)

    selected_events_by_split = Counter()
    expected_yield_by_split = defaultdict(float)

    interference_abs_exposure = defaultdict(float)

    for job_key, split_job in split_jobs.items():

        row = manifest[
            job_key
        ]

        for field in (
            "sample_key",
            "polarization",
            "logical_shard",
            "physical_part",
            "split_group",
        ):
            require_equal_field(
                job_key,
                field,
                split_job.get(field),
                row.get(field),
            )

        sample_key = row[
            "sample_key"
        ]

        polarization = row[
            "polarization"
        ]

        split = split_job[
            "split"
        ]

        h5_path = resolve_path(
            split_job[
                "output_hdf5"
            ]
        )

        with h5py.File(
            h5_path,
            "r",
        ) as h5:

            n_events = int(
                h5.attrs[
                    "n_events"
                ]
            )

            require_equal_field(
                job_key,
                "n_events",
                n_events,
                split_job.get("n_events"),
            )

            identity_expectations = {
                "job_key": job_key,
                "sample_key": sample_key,
                "polarization": polarization,
                "logical_shard": split_job["logical_shard"],
                "physical_part": split_job["physical_part"],
                "split_group": split_job["split_group"],
            }

            for identity, expected in identity_expectations.items():
                observed = unique_h5_string(
                    h5,
                    identity,
                )

                require_equal_field(
                    job_key,
                    f"HDF5 {identity}",
                    observed,
                    expected,
                )

            for dataset_name, dataset in h5.items():
                if dataset.shape and int(dataset.shape[0]) != n_events:
                    raise RuntimeError(
                        f"{job_key}: dataset {dataset_name!r} has "
                        f"length {dataset.shape[0]}, expected {n_events}"
                    )

            # Frozen-provenance checks.
            if "sample_key" in h5:
                h5_sample = unique_h5_string(
                    h5,
                    "sample_key",
                )

                if h5_sample != sample_key:
                    raise RuntimeError(
                        f"{job_key}: sample_key mismatch "
                        f"{h5_sample!r} != {sample_key!r}"
                    )

            if "polarization" in h5:
                h5_pol = unique_h5_string(
                    h5,
                    "polarization",
                )

                if h5_pol != polarization:
                    raise RuntimeError(
                        f"{job_key}: polarization mismatch "
                        f"{h5_pol!r} != {polarization!r}"
                    )

            # Whizard weights are process-mask specific.
            process_mask = row.get(
                "process_mask",
                "",
            ).strip()

            if sample_key in {
                "6q",
                "4f2l",
            }:
                h5_process_mask = unique_h5_string(
                    h5,
                    "process_mask",
                )

                if not process_mask:
                    process_mask = h5_process_mask

                if canonical_process_mask(h5_process_mask) != (
                    canonical_process_mask(process_mask)
                ):
                    raise RuntimeError(
                        f"{job_key}: HDF5 process_mask mismatch"
                    )

            lookup_process_mask = (
                canonical_process_mask(process_mask)
                if sample_key
                in {"6q", "4f2l"}
                else ""
            )

            lookup_key = (
                sample_key,
                polarization,
                lookup_process_mask,
            )

            if lookup_key not in norm_lookup:
                raise RuntimeError(
                    f"{job_key}: no physical normalization "
                    f"for key={lookup_key}"
                )

            norm = norm_lookup[
                lookup_key
            ]

            normalization_type = norm[
                "normalization_type"
            ]

            categories, counts = np.unique(
                h5[
                    "analysis_category"
                ][:],
                return_counts=True,
            )

            category_counts = {
                decode(category): int(count)
                for category, count
                in zip(
                    categories,
                    counts,
                )
            }

        hdf5_sha256 = sha256_file(
            h5_path
        )

        settings = sample_settings[
            sample_key
        ]

        record = {
            "job_key": job_key,
            "split": split,
            "sample_key": sample_key,
            "polarization": polarization,
            "process_mask": (
                process_mask
                if process_mask
                else None
            ),
            "role": settings[
                "role"
            ],
            "use_for_training": bool(
                settings[
                    "use_for_training"
                ]
            ),
            "n_events": n_events,
            "logical_shard": split_job[
                "logical_shard"
            ],
            "physical_part": split_job[
                "physical_part"
            ],
            "split_group": split_job[
                "split_group"
            ],
            "hdf5_sha256": hdf5_sha256,
            "normalization_key": norm[
                "normalization_key"
            ],
            "normalization_type": normalization_type,
            "analysis_category_counts": (
                category_counts
            ),
            "output_hdf5": str(
                h5_path
            ),
        }

        selected_events_by_sample[
            sample_key
        ] += n_events

        selected_events_by_split[
            split
        ] += n_events

        if normalization_type == "positive_cross_section":
            weight_phys = float(
                norm[
                    "weight_phys"
                ]
            )

            record[
                "weight_phys"
            ] = weight_phys

            record[
                "weight_interference_magnitude"
            ] = None

            record[
                "requires_event_sign"
            ] = False

            expected_yield_by_sample[
                sample_key
            ] += (
                n_events
                * weight_phys
            )

            expected_yield_by_split[
                split
            ] += (
                n_events
                * weight_phys
            )

            for (
                category,
                count,
            ) in category_counts.items():

                selected_events_by_category[
                    category
                ] += count

                expected_yield_by_category[
                    category
                ] += (
                    count
                    * weight_phys
                )

        elif normalization_type == "signed_interference":
            magnitude = float(
                norm[
                    "weight_interference_magnitude"
                ]
            )

            record[
                "weight_phys"
            ] = None

            record[
                "weight_interference_magnitude"
            ] = magnitude

            record[
                "requires_event_sign"
            ] = True

            # This is NOT a signed physical yield.
            # It is only an absolute exposure diagnostic.
            interference_abs_exposure[
                polarization
            ] += (
                n_events
                * magnitude
            )

        else:
            raise RuntimeError(
                f"{job_key}: unsupported normalization type "
                f"{normalization_type!r}"
            )

        jobs.append(
            record
        )

    # -------------------------------------------------------------------------
    # Important ttH normalization invariant.
    #
    # No truth category appears anywhere in the normalization lookup key.
    # Therefore tth-hbb and tth-nonbb necessarily inherit the same inclusive
    # tth-sm production weight within a given helicity.
    # -------------------------------------------------------------------------

    catalog = {
        "schema_version": 1,

        "analysis_name": cfg[
            "meta"
        ][
            "analysis_name"
        ],

        "scenario_id": inventory[
            "scenario_id"
        ],

        "split_assignment_hash": (
            split_artifact[
                "assignment_hash"
            ]
        ),

        "inventory_content_hash": (
            inventory[
                "inventory_content_hash"
            ]
        ),

        "rules": {
            "hdf5_modified": False,
            "weight_phys_is_training_weight": False,
            "weight_train_status": "not_assigned",
            "tth_truth_categories_renormalized_separately": False,
            "cpv_signed_interference_kept_separate": True,
        },

        "source": {
            "mva_config": str(
                config_path
            ),
            "mva_config_sha256": (
                sha256_file(
                    config_path
                )
            ),
            "samples_config": str(
                samples_path
            ),
            "samples_config_sha256": (
                sha256_file(
                    samples_path
                )
            ),
            "manifest": str(
                manifest_path
            ),
            "manifest_sha256": (
                sha256_file(
                    manifest_path
                )
            ),
            "physical_inventory": str(
                inventory_path
            ),
            "physical_inventory_sha256": (
                sha256_file(
                    inventory_path
                )
            ),
            "split_assignment": str(
                split_path
            ),
            "split_assignment_sha256": (
                sha256_file(
                    split_path
                )
            ),
        },

        "audit": {
            "jobs_total": len(
                jobs
            ),

            "events_total": sum(
                selected_events_by_sample.values()
            ),

            "selected_events_by_sample": dict(
                sorted(
                    selected_events_by_sample.items()
                )
            ),

            "selected_events_by_split": dict(
                sorted(
                    selected_events_by_split.items()
                )
            ),

            "expected_selected_yield_by_sample": {
                key: value
                for key, value
                in sorted(
                    expected_yield_by_sample.items()
                )
            },

            "expected_selected_yield_by_split": {
                key: value
                for key, value
                in sorted(
                    expected_yield_by_split.items()
                )
            },

            "selected_events_by_analysis_category": dict(
                sorted(
                    selected_events_by_category.items()
                )
            ),

            "expected_selected_yield_by_analysis_category": {
                key: value
                for key, value
                in sorted(
                    expected_yield_by_category.items()
                )
            },

            "cpv_absolute_interference_exposure_diagnostic": {
                key: value
                for key, value
                in sorted(
                    interference_abs_exposure.items()
                )
            },
        },

        "jobs": sorted(
            jobs,
            key=lambda item: item[
                "job_key"
            ],
        ),
    }

    canonical = json.dumps(
        catalog,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    catalog_hash = hashlib.sha256(
        canonical
    ).hexdigest()

    catalog[
        "weights_catalog_hash"
    ] = catalog_hash

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            catalog,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print()
    print("=== MVA physical weights catalog ===")
    print(
        f"scenario: {inventory['scenario_id']}"
    )
    print(
        f"jobs: {len(jobs)}"
    )
    print(
        f"events: "
        f"{sum(selected_events_by_sample.values()):,}"
    )
    print(
        f"split hash: "
        f"{split_artifact['assignment_hash']}"
    )
    print(
        f"inventory hash: "
        f"{inventory['inventory_content_hash']}"
    )
    print(
        f"weights catalog hash: "
        f"{catalog_hash}"
    )
    print(
        f"output: {output_path}"
    )
    print()
    print(
        "HDF5 files modified: no"
    )
    print(
        "weight_train assigned: no"
    )
    print()
    print(
        "PHYSICAL WEIGHT AUDIT PASS"
    )


if __name__ == "__main__":
    main()
