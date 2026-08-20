#!/usr/bin/env python3
"""Export a small manifest-driven MVA HDF5 dataset.

This exporter processes one physical manifest row, joins selected KinFit ROOT
rows to the original SLCIO events, extracts the frozen baseline feature schema,
classifies inclusive ttH events using MC truth, and writes one HDF5 table.

For ttH samples:
  - truth H->bb is labelled as signal;
  - truth H->non-bb is retained and labelled as background.

For all other samples, the manifest class label is retained.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(
    0,
    str(REPO_ROOT / "src"),
)
sys.path.insert(
    0,
    str(REPO_ROOT / "scripts" / "mva"),
)

from ilc_tth_cpv.io import load_yaml  # noqa: E402
from mva_common import (  # noqa: E402
    ROOT_EXPORT_BRANCHES,
    extract_mva_feature_rows,
    find_smoke_row,
    load_manifest_rows,
    read_selected_kinfit_rows,
    validate_hdf5_table,
    write_hdf5_table,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export one manifest row into a test MVA HDF5 dataset."
        )
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=Path(
            "configs/mva_semilep.yaml"
        ),
    )

    parser.add_argument(
        "--sample-key",
        default=None,
        help=(
            "Select the first usable manifest row for this sample. "
            "Default comes from export_test.default_sample_key."
        ),
    )

    parser.add_argument(
        "--job-key",
        default=None,
        help=(
            "Export this exact manifest job instead of selecting "
            "one by sample_key."
        ),
    )

    parser.add_argument(
        "--max-events",
        type=int,
        default=None,
        help=(
            "Maximum selected events to export. "
            "Use 0 for all selected events in the physical file."
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Override the default HDF5 output path.",
    )

    return parser.parse_args()


def resolve_repo_path(
    value: str | Path,
) -> Path:
    """Resolve repository-relative paths."""
    path = Path(value)

    return (
        path
        if path.is_absolute()
        else REPO_ROOT / path
    )


def unique_preserving_order(
    values: list[str],
) -> list[str]:
    """Remove duplicates while preserving order."""
    return list(
        dict.fromkeys(values)
    )


def select_manifest_row(
    rows: list[dict[str, str]],
    *,
    job_key: str | None,
    sample_key: str,
    tree_name: str,
    required_branches: list[str],
) -> dict[str, str]:
    """Select one exact or sample-based physical manifest row."""
    if job_key is not None:
        matches = [
            row
            for row in rows
            if row["job_key"] == job_key
        ]

        if len(matches) != 1:
            raise RuntimeError(
                f"Expected exactly one row for "
                f"job_key={job_key!r}, found {len(matches)}"
            )

        return matches[0]

    return find_smoke_row(
        rows,
        sample_key=sample_key,
        tree_name=tree_name,
        required_branches=required_branches,
    )


def count_row_values(
    rows: list[dict],
    field: str,
) -> dict[str, int]:
    """Count one exported field using JSON-safe string keys."""
    counts = Counter(
        str(row[field])
        for row in rows
    )

    return dict(
        sorted(counts.items())
    )


def main() -> None:
    args = parse_args()

    config_path = resolve_repo_path(
        args.config
    )
    cfg = load_yaml(
        config_path
    )

    manifest_path = resolve_repo_path(
        cfg["inputs"]["manifest"]
    )
    manifest_rows = load_manifest_rows(
        manifest_path,
        included_only=True,
    )

    sample_key = (
        args.sample_key
        if args.sample_key is not None
        else str(
            cfg["export_test"][
                "default_sample_key"
            ]
        )
    )

    maximum_events = (
        args.max_events
        if args.max_events is not None
        else int(
            cfg["export_test"][
                "default_max_events"
            ]
        )
    )

    if maximum_events < 0:
        raise ValueError(
            "--max-events must be non-negative"
        )

    tree_name = str(
        cfg["kinfit"]["tree_name"]
    )

    required_branches = (
        unique_preserving_order(
            list(
                cfg["kinfit"][
                    "required_branches"
                ]
            )
            + ROOT_EXPORT_BRANCHES
        )
    )

    manifest_row = select_manifest_row(
        manifest_rows,
        job_key=args.job_key,
        sample_key=sample_key,
        tree_name=tree_name,
        required_branches=required_branches,
    )

    print(
        f"[export] job:    "
        f"{manifest_row['job_key']}"
    )
    print(
        f"[export] input:  "
        f"{manifest_row['input_path']}"
    )
    print(
        f"[export] ROOT:   "
        f"{manifest_row['kinfit_root_path']}"
    )

    root_rows = read_selected_kinfit_rows(
        Path(
            manifest_row[
                "kinfit_root_path"
            ]
        ),
        tree_name=tree_name,
        required_branches=required_branches,
    )

    available_selected = len(
        root_rows["event_index"]
    )

    print(
        f"[export] selected ROOT rows: "
        f"{available_selected}"
    )

    feature_rows, pid_schema, skipped_events = (
        extract_mva_feature_rows(
            manifest_row,
            root_rows,
            cfg,
            max_events=maximum_events,
        )
    )
    skip_reason_counts = dict(sorted(Counter(
        record["reason"] for record in skipped_events
    ).items()))

    class_label_counts = count_row_values(
        feature_rows,
        "class_label",
    )
    analysis_category_counts = count_row_values(
        feature_rows,
        "analysis_category",
    )
    truth_higgs_decay_counts = count_row_values(
        feature_rows,
        "truth_higgs_decay",
    )
    truth_is_hbb_counts = count_row_values(
        feature_rows,
        "truth_is_hbb",
    )

    output_directory = resolve_repo_path(
        cfg["export_test"]["output_dir"]
    )

    output_path = (
        resolve_repo_path(args.output)
        if args.output is not None
        else (
            output_directory
            / (
                f"{manifest_row['job_key']}"
                f"__first{len(feature_rows)}.h5"
            )
        )
    )

    attributes = {
        "schema_version": 2,
        "feature_schema_version": cfg[
            "feature_schema"
        ]["version"],
        "created_utc": dt.datetime.now(
            dt.timezone.utc
        ).isoformat(),

        "config_path": str(
            config_path
        ),
        "manifest_path": str(
            manifest_path
        ),

        "job_key": manifest_row[
            "job_key"
        ],
        "sample_key": manifest_row[
            "sample_key"
        ],
        "manifest_class_label": manifest_row[
            "class_label"
        ],
        "event_category": int(
            manifest_row[
                "event_category"
            ]
        ),
        "polarization": manifest_row[
            "polarization"
        ],
        "helicity": manifest_row[
            "helicity"
        ],
        "logical_shard": manifest_row[
            "logical_shard"
        ],
        "physical_part": manifest_row[
            "physical_part"
        ],

        "input_path": manifest_row[
            "input_path"
        ],
        "kinfit_root_path": manifest_row[
            "kinfit_root_path"
        ],

        "selection": (
            "accepted == 1 && fit_success == 1"
        ),
        "truth_label_policy": (
            "For tth-sm and tth-cpv: truth H->bb is signal; "
            "truth H->non-bb is background. "
            "No ttH event is dropped by the truth classification."
        ),
        "n_selected_available": (
            available_selected
        ),
        "n_exported": len(
            feature_rows
        ),

        "class_label_counts":
            class_label_counts,
        "analysis_category_counts":
            analysis_category_counts,
        "truth_higgs_decay_counts":
            truth_higgs_decay_counts,
        "truth_is_hbb_counts":
            truth_is_hbb_counts,

        "pid_schema": pid_schema,
        "baseline_features": cfg[
            "feature_schema"
        ]["baseline_features"],
        "angle_features": cfg[
            "feature_schema"
        ]["angle_features"],
        "angle_definition": cfg[
            "feature_schema"
        ]["angle_definition"],

        "weights_status": "unresolved",
        "split_status": "unassigned",

        "n_selected_considered": len(feature_rows) + len(skipped_events),
        "n_skipped_events": len(skipped_events),
        "skip_reason_counts": skip_reason_counts,
    }

    write_hdf5_table(
        output_path,
        feature_rows,
        attributes=attributes,
    )

    validation = validate_hdf5_table(
        output_path,
        baseline_features=cfg[
            "feature_schema"
        ]["baseline_features"],
    )

    metadata_path = output_path.with_suffix(
        ".meta.json"
    )

    metadata = {
        "schema_version": 2,
        "created_utc": dt.datetime.now(
            dt.timezone.utc
        ).isoformat(),
        "output_hdf5": str(
            output_path
        ),
        "job_key": manifest_row[
            "job_key"
        ],
        "sample_key": manifest_row[
            "sample_key"
        ],
        "manifest_class_label": manifest_row[
            "class_label"
        ],
        "selected_available": (
            available_selected
        ),
        "exported_events": len(
            feature_rows
        ),
        "class_label_counts":
            class_label_counts,
        "analysis_category_counts":
            analysis_category_counts,
        "truth_higgs_decay_counts":
            truth_higgs_decay_counts,
        "truth_is_hbb_counts":
            truth_is_hbb_counts,
        "pid_schema": pid_schema,
        "validation": validation,
        "skipped_events": skipped_events,
        "skip_reason_counts": skip_reason_counts,
    }

    with metadata_path.open(
        "w"
    ) as stream:
        json.dump(
            metadata,
            stream,
            indent=2,
            sort_keys=True,
        )

    print(
        f"[export] class labels: "
        f"{json.dumps(class_label_counts, sort_keys=True)}"
    )
    print(
        f"[export] truth Higgs decays: "
        f"{json.dumps(truth_higgs_decay_counts, sort_keys=True)}"
    )
    print(
        f"[export] PID schema: "
        f"{json.dumps(pid_schema, sort_keys=True)}"
    )
    print(
        f"[export] HDF5:  {output_path}"
    )
    print(
        f"[export] meta:  {metadata_path}"
    )

    if skipped_events:
        print(
            f"[export] skipped events: {len(skipped_events)}, "
            f"reasons={json.dumps(skip_reason_counts, sort_keys=True)}"
        )

    print(
        f"[export] PASS: "
        f"events={validation['n_events']}, "
        f"skipped={len(skipped_events)}, "
        f"datasets={validation['n_datasets']}, "
        f"duplicate_event_ids=0, "
        f"non_finite_baseline_values=0"
    )


if __name__ == "__main__":
    main()
