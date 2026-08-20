#!/usr/bin/env python3
"""Export all included manifest rows into per-job MVA HDF5 files."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


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
from mva_common import load_manifest_rows  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export every included physical manifest row "
            "into a full MVA HDF5 file."
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
        action="append",
        default=None,
        help=(
            "Restrict production to one or more sample keys. "
            "May be supplied multiple times."
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing HDF5 and metadata files.",
    )

    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue after a failed physical job.",
    )

    parser.add_argument(
        "--max-jobs",
        type=int,
        default=0,
        help=(
            "Maximum number of jobs to process. "
            "Use 0 for all matching jobs."
        ),
    )

    return parser.parse_args()


def resolve_repo_path(
    value: str | Path,
) -> Path:
    """Resolve a repository-relative path."""
    path = Path(value)

    return (
        path
        if path.is_absolute()
        else REPO_ROOT / path
    )


def merge_counts(
    destination: Counter,
    source: dict[str, Any],
) -> None:
    """Accumulate JSON count dictionaries."""
    for key, value in source.items():
        destination[str(key)] += int(value)


def read_metadata(
    metadata_path: Path,
) -> dict[str, Any]:
    """Read and minimally validate exporter metadata."""
    with metadata_path.open() as stream:
        metadata = json.load(stream)

    validation = metadata.get(
        "validation",
        {}
    )

    if not validation.get("ok", False):
        raise RuntimeError(
            f"Export metadata does not report success: "
            f"{metadata_path}"
        )

    return metadata


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

    if args.sample_key:
        requested_samples = set(
            args.sample_key
        )

        manifest_rows = [
            row
            for row in manifest_rows
            if row["sample_key"]
            in requested_samples
        ]

    if not manifest_rows:
        raise RuntimeError(
            "No matching included manifest rows"
        )

    if args.max_jobs < 0:
        raise ValueError(
            "--max-jobs must be non-negative"
        )

    if args.max_jobs > 0:
        manifest_rows = manifest_rows[
            :args.max_jobs
        ]

    job_keys = [
        row["job_key"]
        for row in manifest_rows
    ]

    if len(job_keys) != len(set(job_keys)):
        raise RuntimeError(
            "Duplicated job_key values in selected manifest rows"
        )

    output_directory = resolve_repo_path(
        cfg["export_test"]["output_dir"]
    )
    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    log_directory = (
        output_directory
        / "logs"
    )
    log_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    exporter_path = (
        REPO_ROOT
        / "scripts"
        / "mva"
        / "export_mva_dataset.py"
    )

    summary_path = (
        output_directory
        / "production_summary.json"
    )

    statuses: list[dict[str, Any]] = []

    total_class_counts = Counter()
    total_decay_counts = Counter()
    total_category_counts = Counter()
    sample_counts: dict[
        str,
        dict[str, Any],
    ] = {}

    failures = 0

    for job_number, manifest_row in enumerate(
        manifest_rows,
        start=1,
    ):
        job_key = manifest_row["job_key"]
        sample_key = manifest_row["sample_key"]

        output_path = (
            output_directory
            / f"{job_key}.h5"
        )
        metadata_path = output_path.with_suffix(
            ".meta.json"
        )
        log_path = (
            log_directory
            / f"{job_key}.log"
        )

        print(
            f"[batch] {job_number}/{len(manifest_rows)} "
            f"{job_key}"
        )

        should_run = (
            args.overwrite
            or not output_path.exists()
            or not metadata_path.exists()
        )

        if should_run:
            command = [
                sys.executable,
                str(exporter_path),
                "--config",
                str(config_path),
                "--job-key",
                job_key,
                "--max-events",
                "0",
                "--output",
                str(output_path),
            ]

            process = subprocess.run(
                command,
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            log_path.write_text(
                process.stdout,
                encoding="utf-8",
            )

            if process.returncode != 0:
                failures += 1

                status = {
                    "job_key": job_key,
                    "sample_key": sample_key,
                    "status": "failed",
                    "return_code":
                        process.returncode,
                    "log_path": str(log_path),
                }
                statuses.append(status)

                print(
                    f"[batch] FAIL: {job_key}; "
                    f"log={log_path}"
                )

                if not args.keep_going:
                    break

                continue

            run_status = "exported"

        else:
            run_status = "existing"

        try:
            metadata = read_metadata(
                metadata_path
            )
        except Exception as exc:
            failures += 1

            status = {
                "job_key": job_key,
                "sample_key": sample_key,
                "status": "invalid-metadata",
                "error": str(exc),
                "metadata_path":
                    str(metadata_path),
            }
            statuses.append(status)

            print(
                f"[batch] FAIL metadata: "
                f"{job_key}: {exc}"
            )

            if not args.keep_going:
                break

            continue

        exported_events = int(
            metadata["exported_events"]
        )

        class_counts = metadata.get(
            "class_label_counts",
            {}
        )
        decay_counts = metadata.get(
            "truth_higgs_decay_counts",
            {}
        )
        category_counts = metadata.get(
            "analysis_category_counts",
            {}
        )

        merge_counts(
            total_class_counts,
            class_counts,
        )
        merge_counts(
            total_decay_counts,
            decay_counts,
        )
        merge_counts(
            total_category_counts,
            category_counts,
        )

        sample_summary = sample_counts.setdefault(
            sample_key,
            {
                "jobs": 0,
                "events": 0,
                "class_label_counts":
                    Counter(),
                "truth_higgs_decay_counts":
                    Counter(),
                "analysis_category_counts":
                    Counter(),
            },
        )

        sample_summary["jobs"] += 1
        sample_summary["events"] += (
            exported_events
        )

        merge_counts(
            sample_summary[
                "class_label_counts"
            ],
            class_counts,
        )
        merge_counts(
            sample_summary[
                "truth_higgs_decay_counts"
            ],
            decay_counts,
        )
        merge_counts(
            sample_summary[
                "analysis_category_counts"
            ],
            category_counts,
        )

        statuses.append(
            {
                "job_key": job_key,
                "sample_key": sample_key,
                "status": run_status,
                "exported_events":
                    exported_events,
                "output_hdf5":
                    str(output_path),
                "metadata_path":
                    str(metadata_path),
                "log_path":
                    str(log_path),
            }
        )

        print(
            f"[batch] PASS: {job_key}, "
            f"events={exported_events}"
        )

    serializable_sample_counts = {}

    for sample_key, values in sorted(
        sample_counts.items()
    ):
        serializable_sample_counts[
            sample_key
        ] = {
            "jobs": int(
                values["jobs"]
            ),
            "events": int(
                values["events"]
            ),
            "class_label_counts": dict(
                sorted(
                    values[
                        "class_label_counts"
                    ].items()
                )
            ),
            "truth_higgs_decay_counts": dict(
                sorted(
                    values[
                        "truth_higgs_decay_counts"
                    ].items()
                )
            ),
            "analysis_category_counts": dict(
                sorted(
                    values[
                        "analysis_category_counts"
                    ].items()
                )
            ),
        }

    summary = {
        "config_path": str(
            config_path
        ),
        "manifest_path": str(
            manifest_path
        ),
        "requested_jobs": len(
            manifest_rows
        ),
        "completed_jobs": sum(
            status["status"]
            in {"exported", "existing"}
            for status in statuses
        ),
        "failed_jobs": failures,
        "total_exported_events": int(
            sum(
                values["events"]
                for values
                in sample_counts.values()
            )
        ),
        "class_label_counts": dict(
            sorted(
                total_class_counts.items()
            )
        ),
        "truth_higgs_decay_counts": dict(
            sorted(
                total_decay_counts.items()
            )
        ),
        "analysis_category_counts": dict(
            sorted(
                total_category_counts.items()
            )
        ),
        "samples":
            serializable_sample_counts,
        "jobs": statuses,
    }

    with summary_path.open(
        "w"
    ) as stream:
        json.dump(
            summary,
            stream,
            indent=2,
            sort_keys=True,
        )

    print(
        f"[batch] summary: "
        f"{summary_path}"
    )
    print(
        f"[batch] completed="
        f"{summary['completed_jobs']}, "
        f"failed={failures}, "
        f"events="
        f"{summary['total_exported_events']}"
    )

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()