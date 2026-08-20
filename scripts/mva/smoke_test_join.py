#!/usr/bin/env python3
"""Run one ROOT–SLCIO join smoke test for each formal sample group."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "mva"))

from ilc_tth_cpv.io import load_yaml  # noqa: E402
from mva_common import (  # noqa: E402
    find_smoke_row,
    load_manifest_rows,
    validate_root_slcio_join,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate ROOT event_index joins to the original "
            "manifest SLCIO input."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/mva_semilep.yaml"),
    )
    parser.add_argument(
        "--sample-key",
        action="append",
        default=None,
        help=(
            "Restrict to one sample_key. "
            "May be supplied more than once."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Override smoke_test.output_json.",
    )
    return parser.parse_args()


def resolve_repo_path(value: str | Path) -> Path:
    """Resolve repository-relative paths."""
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def main() -> None:
    args = parse_args()

    config_path = resolve_repo_path(
        args.config
    )
    cfg = load_yaml(config_path)

    manifest_path = resolve_repo_path(
        cfg["inputs"]["manifest"]
    )
    manifest_rows = load_manifest_rows(
        manifest_path,
        included_only=True,
    )

    tree_name = str(
        cfg["kinfit"]["tree_name"]
    )
    required_branches = list(
        cfg["kinfit"]["required_branches"]
    )

    sample_keys = (
        args.sample_key
        if args.sample_key
        else list(
            cfg["smoke_test"]["sample_keys"]
        )
    )

    collections = cfg["collections"]
    collection_names = {
        "iso_electrons": str(
            collections["iso_electrons"]
        ),
        "iso_muons": str(
            collections["iso_muons"]
        ),
        "fit_jets": str(
            collections["fit_jets"]
        ),
        "flavor_jets": str(
            collections["flavor_jets"]
        ),
    }

    selection = cfg["selection"]

    reports = []

    for sample_key in sample_keys:
        print(
            f"[smoke] selecting row for {sample_key}"
        )

        manifest_row = find_smoke_row(
            manifest_rows,
            sample_key=sample_key,
            tree_name=tree_name,
            required_branches=required_branches,
        )

        print(
            f"[smoke] joining {sample_key}: "
            f"{manifest_row['job_key']}"
        )

        report = validate_root_slcio_join(
            manifest_row,
            tree_name=tree_name,
            required_branches=required_branches,
            collection_names=collection_names,
            expected_iso_multiplicity=int(
                selection[
                    "isolated_lepton_multiplicity"
                ]
            ),
            expected_fit_jets=int(
                selection[
                    "fit_jet_multiplicity"
                ]
            ),
            expected_flavor_jets=int(
                selection[
                    "flavor_jet_multiplicity"
                ]
            ),
        )

        reports.append(report)

        print(
            f"[smoke] PASS {sample_key}: "
            f"job={report['job_key']}, "
            f"selected={report['selected_entries']}, "
            f"event_index="
            f"{report['first_event_index']}.."
            f"{report['last_event_index']}, "
            f"leptons={report['lepton_flavors']}"
        )

    output_path = (
        resolve_repo_path(args.output)
        if args.output is not None
        else resolve_repo_path(
            cfg["smoke_test"]["output_json"]
        )
    )
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "schema_version": 1,
        "created_utc": dt.datetime.now(
            dt.timezone.utc
        ).isoformat(),
        "config": str(config_path),
        "manifest": str(manifest_path),
        "tree_name": tree_name,
        "sample_keys": sample_keys,
        "all_passed": True,
        "reports": reports,
    }

    temporary_path = output_path.with_suffix(
        output_path.suffix + ".tmp"
    )

    with temporary_path.open("w") as stream:
        json.dump(
            payload,
            stream,
            indent=2,
            sort_keys=True,
        )

    temporary_path.replace(output_path)

    total_selected = sum(
        report["selected_entries"]
        for report in reports
    )

    print(
        f"[smoke] all six groups passed; "
        f"selected_events={total_selected}"
    )
    print(f"[smoke] report: {output_path}")


if __name__ == "__main__":
    main()