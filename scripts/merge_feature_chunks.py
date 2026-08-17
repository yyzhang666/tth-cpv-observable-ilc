#!/usr/bin/env python3
"""Merge chunk-level feature CSV files into a single superdataset.

Validates that all specified chunks are present, schemas are identical across
chunks, and no duplicate events exist in the combined dataset. Preserves
lepton_flavor so channels can be filtered at training time.

Usage:
    python3 scripts/merge_feature_chunks.py \
        --input-pattern "outputs/angular_lr/features/chunk1-80/features_higgs_rest_chunk{chunk}.csv" \
        --chunks 1-80 \
        --out-dir outputs/ml_superdataset/features \
        --out-name features_superdataset.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List
import pandas as pd


def parse_chunk_spec(spec: str) -> List[int]:
    """Parse a chunk specification like '1-80' or '1,2,3-5' into a sorted list of ints."""
    chunks = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            low_s, high_s = part.split("-", 1)
            low, high = int(low_s), int(high_s)
            if low > high:
                raise SystemExit(f"Invalid chunk range '{part}': start > end")
            chunks.update(range(low, high + 1))
        else:
            chunks.add(int(part))
    if not chunks:
        raise SystemExit(f"No chunks parsed from --chunks '{spec}'")
    return sorted(chunks)


def validate_chunks_and_schema(input_pattern: str, chunk_ids: List[int]) -> List[pd.DataFrame]:
    """Check that all chunk CSV files exist and share an identical schema.
       Return with list of all data frames (combined all chunks)"""
    dfs = []
    missing_files = []
    reference_columns = None
    first_chunk_id = None

    print(f" Checking presence and schemas for {len(chunk_ids)} chunk files...")

    for chunk in chunk_ids:
        chunk_path = Path(input_pattern.format(chunk=chunk))
        if not chunk_path.exists():
            missing_files.append(str(chunk_path))
            continue

        df = pd.read_csv(chunk_path)
        cols = list(df.columns)

        if reference_columns is None:
            # setup the reference column
            reference_columns = cols
            first_chunk_id = chunk
        elif cols != reference_columns:
            # check if all chunks has matching schema
            raise SystemExit(
                f" Schema mismatch in Chunk {chunk} compared to Chunk {first_chunk_id}!\n"
                f"  Chunk {first_chunk_id} cols ({len(reference_columns)}): {reference_columns}\n"
                f"  Chunk {chunk} cols ({len(cols)}): {cols}"
            )

        dfs.append(df)

    if missing_files:
        raise SystemExit(
            f" Missing {len(missing_files)} chunk file(s):\n" + "\n".join(f"  - {f}" for f in missing_files)
        )

    print(f" All {len(chunk_ids)} chunk files present with identical schemas ({len(reference_columns)} columns).")
    return dfs


def check_duplicates(df: pd.DataFrame) -> None:
    """Check for duplicate events in the merged dataset."""

    print(" Checking for duplicate events across merged chunks...")
    
    # Priority check for explicit event identification columns
    id_cols = [col for col in ["event_id", "event", "evt", "event_number"] if col in df.columns]
    
    if id_cols:
        # Check if the same ID number appears more thanonce in the dataset. Return number of duplicated columns.
        num_dups = df.duplicated(subset=id_cols).sum()
        if num_dups > 0:
            raise SystemExit(f" Found {num_dups} duplicate events based on ID columns: {id_cols}")
    else:
        # If no ID columns exist in dataset, it will check if there exist any identical columns
        num_dups = df.duplicated().sum()
        if num_dups > 0:
            raise SystemExit(f" Found {num_dups} duplicate rows in the merged dataset!")

    print(" No duplicate events found.")


def print_and_summarize_dataset(df: pd.DataFrame) -> dict:
    """Compute and display event statistics broken down by lepton_flavor, split, and label."""
    total_events = len(df)
    
    # Ensure mandatory columns exist
    for col_name in ["lepton_flavor", "split", "label"]:
        if col_name not in df.columns:
            raise SystemExit(f" Missing required column '{col_name}' in feature dataset.")

    # Counts the total event count and the electron/muon, train/validation/test, and ± label 
    flavor_counts = df["lepton_flavor"].value_counts().to_dict()
    split_counts = df["split"].value_counts().to_dict()
    label_counts = df["label"].value_counts().to_dict()

    # Create a grid table counting events for every combination of flavor, split, and label
    grouped = df.groupby(["lepton_flavor", "split", "label"]).size().unstack(fill_value=0)

    print("\n" + "=" * 70)
    print("                SUPERDATASET EVENT SUMMARY REPORT                ")
    print("=" * 70)
    print(f" Total Events Merged : {total_events:,}")
    print("-" * 70)

    print("\n[Lepton Flavor Counts]")
    for flavor, count in flavor_counts.items():
        print(f"  - {flavor:<12}: {count:>8,} ({count / total_events * 100:.2f}%)")

    print("\n[Dataset Split Counts]")
    for split, count in split_counts.items():
        print(f"  - {split:<12}: {count:>8,} ({count / total_events * 100:.2f}%)")

    print("\n[Label Counts (+/-)]")
    for label, count in label_counts.items():
        print(f"  - Label {str(label):<6}: {count:>8,} ({count / total_events * 100:.2f}%)")

    print("\n[Detailed Breakdown: Lepton Flavor x Split x Label]")
    print(grouped.to_string())
    print("=" * 70 + "\n")

    return {
        "total_events": total_events,
        "lepton_flavor_counts": {str(k): int(v) for k, v in flavor_counts.items()},
        "split_counts": {str(k): int(v) for k, v in split_counts.items()},
        "label_counts": {str(k): int(v) for k, v in label_counts.items()},
        "detailed_breakdown": {
            f"{flavor}_{split}_label_{label}": int(cnt)
            for (flavor, split, label), cnt in df.groupby(["lepton_flavor", "split", "label"]).size().items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge chunk-level CSV feature files into a single superdataset."
    )

    parser.add_argument(
        "--chunks",
        default="1-79",
        help="Chunk specifier (e.g. '1-80' or '1,2,3-10')",
    )
    parser.add_argument(
        "--level",
        choices=["gen", "reco"],
        default="reco",
        help="Event level: 'gen' (generator-level) or 'reco' (reconstructed-level)",
    )
    parser.add_argument(
        "--model",
        choices=["sm", "cpv"],
        default="cpv",
        help="Physics model: 'sm' (Standard Model) or 'cpv' (CP violation)",
    )
    parser.add_argument(
        "--input-pattern",
        default=None,
        help="Pattern for chunk CSV files (containing {chunk})",
    )
    parser.add_argument(
        "--out-dir",
        default="../../outputs/ml_superdataset/features/{level}_{model}",
        help="Output directory for merged superdataset and metadata",
    )
    parser.add_argument(
        "--out-name",
        default=None,
        help="Output filename for merged CSV dataset",
    )

    args = parser.parse_args()

    # Model tag: '_sm' if sm is selected, empty string if cpv
    model_tag = "_sm" if args.model == "sm" else ""

    # Build input pattern
    if args.input_pattern is None:
        input_pattern = (
            f"../../outputs/ml_superdataset/features/{args.level}_{args.model}/"
            f"features{model_tag}_{args.level}_higgs_rest_chunk{{chunk}}.csv"
        )
    else:
        input_pattern = args.input_pattern

    # Build output filename
    if args.out_name is None:
        chunk_str = args.chunks.replace("-", "_").replace(",", "_")
        out_name = f"features{model_tag}_{args.level}_higgs_rest_chunk{chunk_str}.csv"
    else:
        out_name = args.out_name

    chunk_ids = parse_chunk_spec(args.chunks)

    # If output directory doesn't exist, create one
    resolved_out_dir = args.out_dir.format(level=args.level, model=args.model)
    out_dir = Path(resolved_out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Load and validate chunks/schema
    dfs = validate_chunks_and_schema(input_pattern, chunk_ids)

    # Merge into single superdataset dataframe
    merged_df = pd.concat(dfs, ignore_index=True)

    # Check for duplicates
    check_duplicates(merged_df)

    # Generate summary report & metadata stats
    stats_summary = print_and_summarize_dataset(merged_df)

    # Write merged dataset
    out_csv_path = out_dir / out_name
    print(f" Writing merged superdataset to {out_csv_path}...")
    merged_df.to_csv(out_csv_path, index=False)

    # Write metadata JSON
    out_meta_path = out_csv_path.with_suffix(".meta.json")
    metadata = {
        "merged_chunks": chunk_ids,
        "num_chunks": len(chunk_ids),
        "source_pattern": args.input_pattern,
        "num_columns": len(merged_df.columns),
        "columns": list(merged_df.columns),
        "summary": stats_summary,
    }

    with out_meta_path.open("w") as f:
        json.dump(metadata, f, indent=2)

    print(f" Metadata saved to {out_meta_path}")
    print(" Superdataset merge successfully completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())