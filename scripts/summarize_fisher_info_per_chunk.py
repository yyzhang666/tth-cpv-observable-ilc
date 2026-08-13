#!/usr/bin/env python3
"""
scripts/summarize_fisher_info_per_chunk.py

Aggregate Fisher information and event counts across all chunks for specified observables.
Reads:
  - N (event count) from *.meta.json
  - I (Fisher info) from *.fisher.json
Outputs:
  - fisher_summary.csv inside each observable's output directory (containing all chunks)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import pandas as pd


def extract_value_from_json(filepath: Path, target_keys: list[str]) -> float:
    """Extract a numeric value from a JSON file handling dicts and scalar numbers."""
    if not filepath.exists():
        return 0.0

    try:
        with open(filepath, "r") as f:
            data = json.load(f)

        if isinstance(data, (int, float)):
            return float(data)

        if isinstance(data, dict):
            for k in target_keys:
                if k in data and data[k] is not None:
                    return float(data[k])

            if len(data) == 1:
                val = list(data.values())[0]
                if isinstance(val, (int, float)):
                    return float(val)

            print(f"  [Debug] File {filepath.name} keys: {list(data.keys())} - could not match {target_keys}")
    except Exception as e:
        print(f"  [Warning] Failed reading {filepath.name}: {e}")

    return 0.0


def read_metric_pair(file_prefix: Path) -> tuple[float, float]:
    """Reads N from meta.json and I from fisher.json."""
    meta_path = Path(f"{file_prefix}.meta.json")
    fisher_path = Path(f"{file_prefix}.fisher.json")

    n_keys = [
        "n_events_filled",
        "N",
        "n_events",
        "num_events",
        "entries",
        "count",
        "total_events",
        "sum_weights",
    ]
    n_val = extract_value_from_json(meta_path, n_keys)

    i_keys = [
        "fisher_absolute",
        "I",
        "fisher_info",
        "fisher_information",
        "integral",
        "total_fisher_info",
        "val",
        "value",
    ]
    i_val = extract_value_from_json(fisher_path, i_keys)

    return n_val, i_val


def process_observable_directory(
    obs_dir: Path, obs_name: str, frame: str = "higgs_rest", max_chunks: int = 10
) -> None:
    """Process all chunks for an observable and aggregate into a single CSV file."""
    if not obs_dir.exists():
        print(f"Error: Directory {obs_dir} does not exist.")
        return

    print(f"\nProcessing directory: {obs_dir}")
    all_rows = []

    possible_chunks = list(range(0, max_chunks + 1))

    for chunk_id in possible_chunks:
        e_gen_prefix = obs_dir / f"{obs_name}_all_gen_electron_chunk{chunk_id}_bins"
        e_reco_prefix = obs_dir / f"{obs_name}_all_reco_electron_chunk{chunk_id}_bins"
        mu_gen_prefix = obs_dir / f"{obs_name}_all_gen_muon_chunk{chunk_id}_bins"
        mu_reco_prefix = obs_dir / f"{obs_name}_all_reco_muon_chunk{chunk_id}_bins"

        files_exist = any(
            Path(f"{p}.fisher.json").exists() or Path(f"{p}.meta.json").exists()
            for p in [e_gen_prefix, e_reco_prefix, mu_gen_prefix, mu_reco_prefix]
        )

        if not files_exist:
            continue

        n_gen_e, i_gen_e = read_metric_pair(e_gen_prefix)
        n_reco_e, i_reco_e = read_metric_pair(e_reco_prefix)
        n_gen_mu, i_gen_mu = read_metric_pair(mu_gen_prefix)
        n_reco_mu, i_reco_mu = read_metric_pair(mu_reco_prefix)

        ratio_e = (i_reco_e / i_gen_e) if i_gen_e > 0 else 0.0
        ratio_mu = (i_reco_mu / i_gen_mu) if i_gen_mu > 0 else 0.0

        n_gen_comb = n_gen_e + n_gen_mu
        n_reco_comb = n_reco_e + n_reco_mu
        i_gen_comb = i_gen_e + i_gen_mu
        i_reco_comb = i_reco_e + i_reco_mu
        ratio_comb = (i_reco_comb / i_gen_comb) if i_gen_comb > 0 else 0.0

        all_rows.extend([
            {
                "Chunk": chunk_id,
                "Observable": obs_name,
                "Lepton category": "electron",
                "Frame": frame,
                "N_gen": n_gen_e,
                "N_reco": n_reco_e,
                "I_gen": i_gen_e,
                "I_reco": i_reco_e,
                "I_reco / I_gen": ratio_e,
            },
            {
                "Chunk": chunk_id,
                "Observable": obs_name,
                "Lepton category": "muon",
                "Frame": frame,
                "N_gen": n_gen_mu,
                "N_reco": n_reco_mu,
                "I_gen": i_gen_mu,
                "I_reco": i_reco_mu,
                "I_reco / I_gen": ratio_mu,
            },
            {
                "Chunk": chunk_id,
                "Observable": obs_name,
                "Lepton category": "combined likelihood (e+mu)",
                "Frame": frame,
                "N_gen": n_gen_comb,
                "N_reco": n_reco_comb,
                "I_gen": i_gen_comb,
                "I_reco": i_reco_comb,
                "I_reco / I_gen": ratio_comb,
            },
        ])

    if all_rows:
        df = pd.DataFrame(all_rows)
        out_csv = obs_dir / "fisher_summary.csv"
        df.to_csv(out_csv, index=False)
        print(f"  --> Successfully created single combined file: {out_csv}")
    else:
        print(f"  [Warning] No matching chunk files found in {obs_dir}")


def main():
    parser = argparse.ArgumentParser(description="Summarize Fisher Info & Meta files into a single CSV per observable.")
    parser.add_argument(
        "--base-dir",
        type=str,
        default="outputs/angular_lr/angular",
        help="Base directory containing observable subdirectories",
    )
    parser.add_argument(
        "--observables",
        nargs="+",
        default=["O_lD", "O_W"],
        help="Observables to process (e.g. O_lD O_W)",
    )
    parser.add_argument("--frame", type=str, default="higgs_rest", help="Reference frame name")
    parser.add_argument("--chunks", type=int, default=10, help="Maximum number of chunks to check")
    args = parser.parse_args()

    base_dir = Path(args.base_dir)

    for obs in args.observables:
        obs_dir = base_dir / obs
        process_observable_directory(obs_dir, obs_name=obs, frame=args.frame, max_chunks=args.chunks)


if __name__ == "__main__":
    main()