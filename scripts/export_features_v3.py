#!/usr/bin/env python3
"""Export the reco-only reusable raw ML baseline schema v3."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.io import load_analysis_config  # noqa: E402
from ilc_tth_cpv.feature_table import (  # noqa: E402
    COMPAT_POLICIES,
    augment_feature_table,
    parse_chunk_spec,
)
from ilc_tth_cpv.reco_baseline import export_reco_baseline  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    baseline = subparsers.add_parser("baseline", help="export reco lab-raw baseline")
    baseline.add_argument("--config", required=True)
    baseline.add_argument("--component", choices=("interference", "sm"), default="interference")
    baseline.add_argument("--chunk", required=True)
    baseline.add_argument("--out-dir", default="outputs/ml_superdataset/features_v3_baseline")
    baseline.add_argument("--max-events", type=int, default=0)
    baseline.add_argument("--overwrite", action="store_true")
    augment = subparsers.add_parser("augment", help="derive a compact feature table from v3 baselines")
    augment.add_argument("--config", required=True)
    augment.add_argument("--feature-set", required=True)
    augment.add_argument("--input-pattern", required=True)
    augment.add_argument("--chunks", required=True)
    augment.add_argument("--output", required=True)
    augment.add_argument("--compat-policy", choices=COMPAT_POLICIES, default="canonical")
    args = parser.parse_args(argv)
    if args.command == "baseline" and args.max_events < 0:
        parser.error("--max-events must be non-negative")
    if args.command == "augment":
        if args.input_pattern.count("{chunk}") != 1:
            parser.error("--input-pattern must contain literal {chunk} exactly once")
        if Path(args.output).suffix != ".csv":
            parser.error("--output must have suffix .csv")
        try:
            args.chunk_ids = parse_chunk_spec(args.chunks)
        except ValueError as exc:
            parser.error(str(exc))
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = Path(args.config).resolve()
    cfg = load_analysis_config(config_path)
    cfg["_source_path"] = str(config_path)
    if args.command == "baseline":
        output = export_reco_baseline(
            cfg,
            component=args.component,
            chunk_id=str(args.chunk),
            out_dir=Path(args.out_dir),
            max_events=args.max_events,
            overwrite=args.overwrite,
        )
    else:
        output = augment_feature_table(
            cfg,
            config_path=config_path,
            feature_set=args.feature_set,
            input_pattern=args.input_pattern,
            chunks=args.chunk_ids,
            output=Path(args.output),
            compat_policy=args.compat_policy,
        )
    metadata = json.loads(output.with_suffix(".meta.json").read_text())
    n_rows = metadata.get("n_exported", metadata.get("n_output_rows"))
    print(f"wrote {n_rows} rows -> {output}")
    print(f"schema={metadata['schema_version']} columns={metadata['n_columns']} status={metadata['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
