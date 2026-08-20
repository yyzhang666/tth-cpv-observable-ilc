#!/usr/bin/env python3
"""
Assign deterministic train / validation / test splits to the frozen
semileptonic ttH selection-MVA dataset.

Important design rules
----------------------

1. Splitting is performed at split_group level, never event-by-event.

2. split_group is taken from the canonical MVA manifest. In the current
   production it identifies all physical parts belonging to the same logical
   production shard.

3. The split is determined only from:
       split_group
       configured seed
       configured fractions

   It does NOT depend on:
       sample label
       analysis category
       event count
       feature values
       physics weight

4. Frozen HDF5 files are NOT modified. The split assignment is written to
   a separate persistent JSON artifact.

5. All samples receive a split assignment, including tth-cpv. Whether a
   sample is used in baseline training is a separate decision controlled by
   mva_samples.yaml / downstream training configuration.

6. With method=deterministic_hash, fractions are target probabilities at
   split-group level. Event fractions are not forced to exactly 70/15/15.

The output JSON is deterministic: rerunning with unchanged inputs and
configuration produces the same assignment and assignment hash.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import yaml


# =============================================================================
# Repository paths
# =============================================================================

REPO_ROOT = Path(__file__).resolve().parents[2]


# =============================================================================
# Basic utilities
# =============================================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Assign deterministic split-group-level train/validation/test "
            "splits for the frozen semileptonic MVA dataset."
        )
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/mva_semilep.yaml"),
        help="Semileptonic MVA configuration YAML.",
    )

    return parser.parse_args()


def resolve_path(path_like: str | Path) -> Path:
    """
    Resolve a path relative to the repository root unless it is absolute.
    """
    path = Path(path_like)

    if path.is_absolute():
        return path

    return REPO_ROOT / path


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open() as stream:
        data = yaml.safe_load(stream)

    if not isinstance(data, dict):
        raise RuntimeError(
            f"Expected mapping at top level of YAML: {path}"
        )

    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()

    if text in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }:
        return True

    if text in {
        "0",
        "false",
        "no",
        "n",
        "off",
        "",
    }:
        return False

    raise ValueError(
        f"Cannot interpret as boolean: {value!r}"
    )


def decode_scalar(value: Any) -> str:
    """
    Convert HDF5 string-like values to ordinary Python strings.
    """
    if isinstance(value, bytes):
        return value.decode("utf-8")

    if isinstance(value, np.bytes_):
        return bytes(value).decode("utf-8")

    return str(value)


# =============================================================================
# Configuration
# =============================================================================


def validate_split_config(
    cfg: dict[str, Any],
) -> dict[str, Any]:
    if "inputs" not in cfg:
        raise RuntimeError(
            "Missing 'inputs' section in MVA config."
        )

    if "manifest" not in cfg["inputs"]:
        raise RuntimeError(
            "Missing inputs.manifest in MVA config."
        )

    if "split" not in cfg:
        raise RuntimeError(
            "Missing 'split' section in MVA config."
        )

    split_cfg = cfg["split"]

    required = [
        "grouping_field",
        "fractions",
        "method",
        "hash_algorithm",
        "seed",
        "production_summary",
        "output_json",
    ]

    missing = [
        key
        for key in required
        if key not in split_cfg
    ]

    if missing:
        raise RuntimeError(
            "Missing split configuration field(s): "
            + ", ".join(missing)
        )

    grouping_field = str(
        split_cfg["grouping_field"]
    )

    if not grouping_field:
        raise RuntimeError(
            "split.grouping_field must not be empty."
        )

    method = str(
        split_cfg["method"]
    )

    if method != "deterministic_hash":
        raise RuntimeError(
            "Only split.method=deterministic_hash "
            f"is currently supported, got {method!r}."
        )

    algorithm = str(
        split_cfg["hash_algorithm"]
    ).lower()

    if algorithm != "sha256":
        raise RuntimeError(
            "Only split.hash_algorithm=sha256 "
            f"is currently supported, got {algorithm!r}."
        )

    fractions = split_cfg["fractions"]

    expected_names = [
        "train",
        "validation",
        "test",
    ]

    if set(fractions) != set(expected_names):
        raise RuntimeError(
            "split.fractions must contain exactly "
            "'train', 'validation', and 'test'."
        )

    values = {
        name: float(fractions[name])
        for name in expected_names
    }

    if any(
        value <= 0.0
        for value in values.values()
    ):
        raise RuntimeError(
            "Every split fraction must be positive."
        )

    total = sum(
        values.values()
    )

    if not math.isclose(
        total,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise RuntimeError(
            "Split fractions must sum to 1.0; "
            f"got {total:.16g}."
        )

    return split_cfg


# =============================================================================
# Manifest
# =============================================================================


def load_manifest(
    path: Path,
    grouping_field: str,
) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Manifest does not exist: {path}"
        )

    with path.open(
        newline="",
    ) as stream:
        reader = csv.DictReader(
            stream
        )

        if reader.fieldnames is None:
            raise RuntimeError(
                f"Manifest has no header: {path}"
            )

        required_fields = {
            "job_key",
            "sample_key",
            "polarization",
            "logical_shard",
            "physical_part",
            grouping_field,
        }

        missing = sorted(
            required_fields
            - set(reader.fieldnames)
        )

        if missing:
            raise RuntimeError(
                "Manifest is missing required field(s): "
                + ", ".join(missing)
            )

        rows = []

        for row in reader:
            # build_mva_manifest currently writes all 1150 included jobs,
            # but retain support for an explicit include column.
            if "include" in row:
                if not parse_bool(
                    row["include"]
                ):
                    continue

            rows.append(
                dict(row)
            )

    if not rows:
        raise RuntimeError(
            "No included rows found in manifest."
        )

    seen_job_keys: set[str] = set()

    for row in rows:
        job_key = row[
            "job_key"
        ].strip()

        group = row[
            grouping_field
        ].strip()

        if not job_key:
            raise RuntimeError(
                "Encountered empty job_key in manifest."
            )

        if not group:
            raise RuntimeError(
                f"{job_key}: empty {grouping_field}"
            )

        if job_key in seen_job_keys:
            raise RuntimeError(
                f"Duplicate job_key in manifest: {job_key}"
            )

        seen_job_keys.add(
            job_key
        )

    return rows


# =============================================================================
# Production summary
# =============================================================================


def load_production_summary(
    path: Path,
) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Production summary does not exist: {path}"
        )

    with path.open() as stream:
        summary = json.load(
            stream
        )

    required = [
        "requested_jobs",
        "completed_jobs",
        "failed_jobs",
        "total_exported_events",
        "jobs",
    ]

    missing = [
        key
        for key in required
        if key not in summary
    ]

    if missing:
        raise RuntimeError(
            "Production summary is missing field(s): "
            + ", ".join(missing)
        )

    requested = int(
        summary["requested_jobs"]
    )

    completed = int(
        summary["completed_jobs"]
    )

    failed = int(
        summary["failed_jobs"]
    )

    if failed != 0:
        raise RuntimeError(
            "Frozen production is not clean: "
            f"failed_jobs={failed}"
        )

    if completed != requested:
        raise RuntimeError(
            "Frozen production is incomplete: "
            f"completed_jobs={completed}, "
            f"requested_jobs={requested}"
        )

    jobs = summary["jobs"]

    if len(jobs) != requested:
        raise RuntimeError(
            "production_summary jobs length mismatch: "
            f"len(jobs)={len(jobs)}, "
            f"requested_jobs={requested}"
        )

    return summary


def get_job_event_count(
    job: dict[str, Any],
) -> int:
    """
    Retrieve exported event count from the production summary.

    Several names are supported to avoid coupling this script unnecessarily
    to a presentation-level field name.
    """
    for key in [
        "exported_events",
        "n_exported",
        "n_events",
    ]:
        if key in job:
            return int(
                job[key]
            )

    if "metadata_path" not in job:
        raise RuntimeError(
            f"{job.get('job_key', '<unknown>')}: "
            "cannot determine exported event count."
        )

    meta_path = resolve_path(
        job["metadata_path"]
    )

    with meta_path.open() as stream:
        meta = json.load(
            stream
        )

    for key in [
        "n_exported",
        "n_events",
    ]:
        if key in meta:
            return int(
                meta[key]
            )

    raise RuntimeError(
        f"{job.get('job_key', '<unknown>')}: "
        "event count not found in production summary "
        "or metadata."
    )


# =============================================================================
# Deterministic split
# =============================================================================


def deterministic_uniform(
    grouping_value: str,
    seed: str,
) -> tuple[float, str]:
    """
    Map one grouping value deterministically onto [0, 1).

    Only the configured seed and grouping value enter the mapping.
    """
    payload = (
        seed
        + "\0"
        + grouping_value
    ).encode("utf-8")

    digest = hashlib.sha256(
        payload
    ).digest()

    # Use the first 64 bits.
    integer = int.from_bytes(
        digest[:8],
        byteorder="big",
        signed=False,
    )

    value = integer / float(
        1 << 64
    )

    return (
        value,
        digest.hex(),
    )


def choose_split(
    value: float,
    fractions: dict[str, float],
) -> str:
    train_end = fractions[
        "train"
    ]

    validation_end = (
        train_end
        + fractions[
            "validation"
        ]
    )

    if value < train_end:
        return "train"

    if value < validation_end:
        return "validation"

    return "test"


def build_group_assignments(
    groups: list[str],
    fractions: dict[str, float],
    seed: str,
) -> dict[str, dict[str, Any]]:
    assignments: dict[
        str,
        dict[str, Any],
    ] = {}

    for group in sorted(
        groups
    ):
        value, digest = deterministic_uniform(
            group,
            seed,
        )

        assignments[group] = {
            "split": choose_split(
                value,
                fractions,
            ),
            "hash_uniform": value,
            "sha256": digest,
        }

    return assignments


def compute_assignment_hash(
    grouping_field: str,
    fractions: dict[str, float],
    seed: str,
    assignments: dict[
        str,
        dict[str, Any],
    ],
) -> str:
    """
    Hash only scientifically relevant assignment information.
    """
    payload = {
        "grouping_field":
            grouping_field,
        "method":
            "deterministic_hash",
        "hash_algorithm":
            "sha256",
        "seed":
            seed,
        "fractions":
            fractions,
        "assignments": {
            group:
                assignments[
                    group
                ]["split"]
            for group
            in sorted(assignments)
        },
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    ).encode("utf-8")

    return hashlib.sha256(
        encoded
    ).hexdigest()


# =============================================================================
# HDF5 audit
# =============================================================================


def audit_hdf5_file(
    h5_path: Path,
    expected_group: str,
    expected_job_key: str,
    grouping_field: str,
) -> tuple[
    int,
    Counter[str],
]:
    """
    Validate one frozen HDF5 shard without modifying it.

    Returns
    -------
    n_events
        Number of exported events.

    category_counts
        Counts of analysis_category values.
    """
    if not h5_path.exists():
        raise FileNotFoundError(
            f"{expected_job_key}: missing HDF5: {h5_path}"
        )

    category_counts: Counter[
        str
    ] = Counter()

    with h5py.File(
        h5_path,
        "r",
    ) as h5:
        if "n_events" not in h5.attrs:
            raise RuntimeError(
                f"{expected_job_key}: HDF5 missing "
                "n_events attribute."
            )

        n_events = int(
            h5.attrs[
                "n_events"
            ]
        )

        if grouping_field not in h5:
            raise RuntimeError(
                f"{expected_job_key}: HDF5 missing "
                f"{grouping_field!r} dataset."
            )

        group_values = h5[
            grouping_field
        ][:]

        if len(
            group_values
        ) != n_events:
            raise RuntimeError(
                f"{expected_job_key}: "
                f"{grouping_field}.shape[0]="
                f"{len(group_values)} != "
                f"n_events={n_events}"
            )

        unique_groups = {
            decode_scalar(
                value
            )
            for value
            in np.unique(
                group_values
            )
        }

        if unique_groups != {
            expected_group
        }:
            raise RuntimeError(
                f"{expected_job_key}: HDF5 "
                f"{grouping_field} mismatch: "
                f"expected={expected_group!r}, "
                f"observed={sorted(unique_groups)!r}"
            )

        # The frozen dataset should still be explicitly unassigned.
        # The split artifact, not the HDF5, owns downstream split state.
        if "split" in h5:
            split_values = {
                decode_scalar(
                    value
                )
                for value
                in np.unique(
                    h5["split"][:]
                )
            }

            if split_values != {
                "unassigned"
            }:
                raise RuntimeError(
                    f"{expected_job_key}: frozen HDF5 "
                    "split dataset is no longer "
                    f"unassigned: {sorted(split_values)}"
                )

        if "analysis_category" not in h5:
            raise RuntimeError(
                f"{expected_job_key}: HDF5 missing "
                "analysis_category dataset."
            )

        values, counts = np.unique(
            h5[
                "analysis_category"
            ][:],
            return_counts=True,
        )

        for value, count in zip(
            values,
            counts,
        ):
            category_counts[
                decode_scalar(
                    value
                )
            ] += int(
                count
            )

    return (
        n_events,
        category_counts,
    )


# =============================================================================
# Artifact construction
# =============================================================================


def counter_dict(
    counter: Counter[str],
) -> dict[str, int]:
    return {
        key: int(
            counter[key]
        )
        for key in sorted(
            counter
        )
    }


def nested_counter_dict(
    mapping: dict[
        str,
        Counter[str],
    ],
) -> dict[
    str,
    dict[str, int],
    ]:
    return {
        split: counter_dict(
            mapping[split]
        )
        for split in [
            "train",
            "validation",
            "test",
        ]
    }


def main() -> None:
    args = parse_args()

    config_path = resolve_path(
        args.config
    )

    cfg = load_yaml(
        config_path
    )

    split_cfg = validate_split_config(
        cfg
    )

    analysis_name = (
        cfg.get(
            "meta",
            {},
        ).get(
            "analysis_name",
            "unknown",
        )
    )

    manifest_path = resolve_path(
        cfg[
            "inputs"
        ][
            "manifest"
        ]
    )

    production_summary_path = resolve_path(
        split_cfg[
            "production_summary"
        ]
    )

    output_path = resolve_path(
        split_cfg[
            "output_json"
        ]
    )

    grouping_field = str(
        split_cfg[
            "grouping_field"
        ]
    )

    fractions = {
        "train":
            float(
                split_cfg[
                    "fractions"
                ][
                    "train"
                ]
            ),
        "validation":
            float(
                split_cfg[
                    "fractions"
                ][
                    "validation"
                ]
            ),
        "test":
            float(
                split_cfg[
                    "fractions"
                ][
                    "test"
                ]
            ),
    }

    seed = str(
        split_cfg[
            "seed"
        ]
    )

    audit_hdf5 = bool(
        split_cfg.get(
            "audit_hdf5",
            True,
        )
    )

    # -------------------------------------------------------------------------
    # Load frozen production state.
    # -------------------------------------------------------------------------

    manifest_rows = load_manifest(
        manifest_path,
        grouping_field,
    )

    production_summary = (
        load_production_summary(
            production_summary_path
        )
    )

    manifest_by_job: dict[
        str,
        dict[str, str],
    ] = {
        row["job_key"]:
            row
        for row
        in manifest_rows
    }

    production_jobs = (
        production_summary[
            "jobs"
        ]
    )

    production_by_job: dict[
        str,
        dict[str, Any],
    ] = {}

    for job in production_jobs:
        job_key = str(
            job[
                "job_key"
            ]
        )

        if (
            job_key
            in production_by_job
        ):
            raise RuntimeError(
                "Duplicate job_key in production summary: "
                f"{job_key}"
            )

        production_by_job[
            job_key
        ] = job

    manifest_keys = set(
        manifest_by_job
    )

    production_keys = set(
        production_by_job
    )

    missing_from_manifest = sorted(
        production_keys
        - manifest_keys
    )

    missing_from_production = sorted(
        manifest_keys
        - production_keys
    )

    if missing_from_manifest:
        raise RuntimeError(
            "Production job(s) missing from manifest: "
            + ", ".join(
                missing_from_manifest[
                    :20
                ]
            )
        )

    if missing_from_production:
        raise RuntimeError(
            "Manifest job(s) missing from production: "
            + ", ".join(
                missing_from_production[
                    :20
                ]
            )
        )

    # -------------------------------------------------------------------------
    # Build canonical group assignment.
    # -------------------------------------------------------------------------

    groups = sorted(
        {
            row[
                grouping_field
            ].strip()
            for row
            in manifest_rows
        }
    )

    group_assignments = (
        build_group_assignments(
            groups,
            fractions,
            seed,
        )
    )

    assignment_hash = (
        compute_assignment_hash(
            grouping_field,
            fractions,
            seed,
            group_assignments,
        )
    )

    # -------------------------------------------------------------------------
    # Audits and job-level artifact records.
    # -------------------------------------------------------------------------

    group_counts: Counter[
        str
    ] = Counter()

    for group in groups:
        group_counts[
            group_assignments[
                group
            ][
                "split"
            ]
        ] += 1

    job_counts: Counter[
        str
    ] = Counter()

    event_counts: Counter[
        str
    ] = Counter()

    jobs_by_sample: dict[
        str,
        Counter[str],
    ] = defaultdict(
        Counter
    )

    events_by_sample: dict[
        str,
        Counter[str],
    ] = defaultdict(
        Counter
    )

    jobs_by_polarization: dict[
        str,
        Counter[str],
    ] = defaultdict(
        Counter
    )

    events_by_polarization: dict[
        str,
        Counter[str],
    ] = defaultdict(
        Counter
    )

    events_by_analysis_category: dict[
        str,
        Counter[str],
    ] = defaultdict(
        Counter
    )

    artifact_jobs: list[
        dict[str, Any]
    ] = []

    total_events = 0

    for job_key in sorted(
        production_by_job
    ):
        job = production_by_job[
            job_key
        ]

        row = manifest_by_job[
            job_key
        ]

        group = row[
            grouping_field
        ].strip()

        split = group_assignments[
            group
        ][
            "split"
        ]

        sample_key = row[
            "sample_key"
        ].strip()

        polarization = row[
            "polarization"
        ].strip()

        logical_shard = row[
            "logical_shard"
        ].strip()

        physical_part = row[
            "physical_part"
        ].strip()

        summary_n_events = (
            get_job_event_count(
                job
            )
        )

        category_counts: Counter[
            str
        ] = Counter()

        if audit_hdf5:
            if "output_hdf5" not in job:
                raise RuntimeError(
                    f"{job_key}: production summary "
                    "does not contain output_hdf5."
                )

            h5_path = resolve_path(
                job[
                    "output_hdf5"
                ]
            )

            (
                h5_n_events,
                category_counts,
            ) = audit_hdf5_file(
                h5_path=h5_path,
                expected_group=group,
                expected_job_key=job_key,
                grouping_field=grouping_field,
            )

            if (
                h5_n_events
                != summary_n_events
            ):
                raise RuntimeError(
                    f"{job_key}: event-count mismatch: "
                    f"summary={summary_n_events}, "
                    f"HDF5={h5_n_events}"
                )

        n_events = summary_n_events

        total_events += n_events

        job_counts[
            split
        ] += 1

        event_counts[
            split
        ] += n_events

        jobs_by_sample[
            split
        ][
            sample_key
        ] += 1

        events_by_sample[
            split
        ][
            sample_key
        ] += n_events

        jobs_by_polarization[
            split
        ][
            polarization
        ] += 1

        events_by_polarization[
            split
        ][
            polarization
        ] += n_events

        if audit_hdf5:
            for (
                category,
                count,
            ) in category_counts.items():
                events_by_analysis_category[
                    split
                ][
                    category
                ] += count

        artifact_jobs.append(
            {
                "job_key":
                    job_key,
                "sample_key":
                    sample_key,
                "polarization":
                    polarization,
                "logical_shard":
                    logical_shard,
                "physical_part":
                    physical_part,
                grouping_field:
                    group,
                "split":
                    split,
                "n_events":
                    n_events,
                "output_hdf5":
                    job.get(
                        "output_hdf5"
                    ),
            }
        )

    expected_total_events = int(
        production_summary[
            "total_exported_events"
        ]
    )

    if (
        total_events
        != expected_total_events
    ):
        raise RuntimeError(
            "Total exported-event accounting mismatch: "
            f"split audit={total_events}, "
            f"production summary={expected_total_events}"
        )

    if sum(
        job_counts.values()
    ) != len(
        production_jobs
    ):
        raise RuntimeError(
            "Job accounting mismatch."
        )

    if sum(
        group_counts.values()
    ) != len(
        groups
    ):
        raise RuntimeError(
            "Split-group accounting mismatch."
        )

    # -------------------------------------------------------------------------
    # Persistent artifact.
    # -------------------------------------------------------------------------

    artifact: dict[
        str,
        Any,
    ] = {
        "schema_version":
            1,

        "analysis_name":
            analysis_name,

        "purpose":
            "train_validation_test_split_assignment",

        "source": {
            "config_path":
                str(
                    config_path
                ),
            "config_sha256":
                sha256_file(
                    config_path
                ),
            "manifest_path":
                str(
                    manifest_path
                ),
            "manifest_sha256":
                sha256_file(
                    manifest_path
                ),
            "production_summary":
                str(
                    production_summary_path
                ),
            "production_summary_sha256":
                sha256_file(
                    production_summary_path
                ),
        },

        "split_definition": {
            "grouping_field":
                grouping_field,
            "method":
                "deterministic_hash",
            "hash_algorithm":
                "sha256",
            "seed":
                seed,
            "fractions":
                fractions,
            "uses_event_labels":
                False,
            "uses_analysis_category":
                False,
            "uses_event_counts":
                False,
            "uses_feature_values":
                False,
            "modifies_hdf5":
                False,
        },

        "assignment_hash":
            assignment_hash,

        "group_assignments": {
            group: {
                "split":
                    group_assignments[
                        group
                    ][
                        "split"
                    ],
                "hash_uniform":
                    group_assignments[
                        group
                    ][
                        "hash_uniform"
                    ],
                "sha256":
                    group_assignments[
                        group
                    ][
                        "sha256"
                    ],
            }
            for group
            in sorted(
                group_assignments
            )
        },

        "jobs":
            artifact_jobs,

        "audit": {
            "groups_total":
                len(
                    groups
                ),

            "jobs_total":
                len(
                    production_jobs
                ),

            "events_total":
                total_events,

            "groups_by_split":
                counter_dict(
                    group_counts
                ),

            "jobs_by_split":
                counter_dict(
                    job_counts
                ),

            "events_by_split":
                counter_dict(
                    event_counts
                ),

            "jobs_by_sample":
                nested_counter_dict(
                    jobs_by_sample
                ),

            "events_by_sample":
                nested_counter_dict(
                    events_by_sample
                ),

            "jobs_by_polarization":
                nested_counter_dict(
                    jobs_by_polarization
                ),

            "events_by_polarization":
                nested_counter_dict(
                    events_by_polarization
                ),

            "events_by_analysis_category":
                (
                    nested_counter_dict(
                        events_by_analysis_category
                    )
                    if audit_hdf5
                    else None
                ),

            "hdf5_audited":
                audit_hdf5,
        },
    }

    # Deterministic JSON output: no creation timestamp is deliberately stored.
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    encoded = json.dumps(
        artifact,
        indent=2,
        sort_keys=True,
    ) + "\n"

    # If the artifact already exists, check whether the assignment changed.
    if output_path.exists():
        with output_path.open() as stream:
            old_artifact = json.load(
                stream
            )

        old_hash = old_artifact.get(
            "assignment_hash"
        )

        if (
            old_hash is not None
            and old_hash
            != assignment_hash
        ):
            raise RuntimeError(
                "Existing split artifact has a different "
                "assignment hash.\n"
                f"existing: {old_hash}\n"
                f"new:      {assignment_hash}\n"
                "Refusing to silently replace a frozen "
                "split assignment."
            )

    output_path.write_text(
        encoded
    )

    # -------------------------------------------------------------------------
    # Human-readable summary.
    # -------------------------------------------------------------------------

    print()
    print(
        "=== MVA deterministic split assignment ==="
    )
    print(
        f"analysis:        {analysis_name}"
    )
    print(
        f"manifest:        {manifest_path}"
    )
    print(
        f"production:      {production_summary_path}"
    )
    print(
        f"grouping field:  {grouping_field}"
    )
    print(
        f"seed:            {seed}"
    )
    print(
        f"output:          {output_path}"
    )

    print()
    print(
        f"{'split':<14}"
        f"{'groups':>10}"
        f"{'jobs':>10}"
        f"{'events':>15}"
        f"{'event fraction':>18}"
    )

    print(
        "-" * 67
    )

    for split in [
        "train",
        "validation",
        "test",
    ]:
        n_events = event_counts[
            split
        ]

        event_fraction = (
            n_events
            / total_events
            if total_events
            else 0.0
        )

        print(
            f"{split:<14}"
            f"{group_counts[split]:>10}"
            f"{job_counts[split]:>10}"
            f"{n_events:>15,}"
            f"{event_fraction:>18.4%}"
        )

    print(
        "-" * 67
    )

    print(
        f"{'total':<14}"
        f"{len(groups):>10}"
        f"{len(production_jobs):>10}"
        f"{total_events:>15,}"
        f"{1.0:>18.4%}"
    )

    print()
    print(
        "Events by sample and split:"
    )

    sample_names = sorted(
        {
            sample
            for counter
            in events_by_sample.values()
            for sample
            in counter
        }
    )

    print(
        f"{'sample':<16}"
        f"{'train':>14}"
        f"{'validation':>14}"
        f"{'test':>14}"
        f"{'total':>14}"
    )

    for sample in sample_names:
        values = [
            events_by_sample[
                split
            ][
                sample
            ]
            for split
            in [
                "train",
                "validation",
                "test",
            ]
        ]

        print(
            f"{sample:<16}"
            f"{values[0]:>14,}"
            f"{values[1]:>14,}"
            f"{values[2]:>14,}"
            f"{sum(values):>14,}"
        )

    if audit_hdf5:
        print()
        print(
            "Events by analysis category and split:"
        )

        categories = sorted(
            {
                category
                for counter
                in events_by_analysis_category.values()
                for category
                in counter
            }
        )

        print(
            f"{'category':<20}"
            f"{'train':>14}"
            f"{'validation':>14}"
            f"{'test':>14}"
            f"{'total':>14}"
        )

        for category in categories:
            values = [
                events_by_analysis_category[
                    split
                ][
                    category
                ]
                for split
                in [
                    "train",
                    "validation",
                    "test",
                ]
            ]

            print(
                f"{category:<20}"
                f"{values[0]:>14,}"
                f"{values[1]:>14,}"
                f"{values[2]:>14,}"
                f"{sum(values):>14,}"
            )

    print()
    print(
        f"assignment hash: {assignment_hash}"
    )
    print(
        "HDF5 files modified: no"
    )
    print()
    print(
        "SPLIT AUDIT PASS"
    )


if __name__ == "__main__":
    main()