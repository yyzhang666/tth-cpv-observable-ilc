#!/usr/bin/env python3
"""Plot observable curves (gen vs reco, CPV vs SM) for both Angular and ML observables."""

import csv
import argparse
from pathlib import Path

from ilc_tth_cpv.plotting import import_plotting
from ilc_tth_cpv.histograms import SignedHistogram


def load_signed_histogram(path: Path) -> SignedHistogram:
    """Load a CSV file into a SignedHistogram object."""
    if not path.exists():
        raise FileNotFoundError(f"Missing required template file: {path}")

    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))

    edges = [float(r["bin_low"]) for r in rows] + [float(rows[-1]["bin_high"])]
    signed = [float(r["signed_weight_fb"]) for r in rows]

    return SignedHistogram(edges=edges, signed=signed)


def find_existing_file(candidates: list[Path]) -> Path:
    """Return the first candidate path that exists, or the primary path if none exist."""
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def build_angular_config(args, lepton: str) -> tuple[dict[str, tuple[Path, str, str, float]], str, str, Path]:
    frame_suffix = "" if args.frame == "higgs_rest" else f"_{args.frame}"
    obs = args.observable
    chunks = args.chunks

    # Base folder path including chunk directory
    obs_dir_chunk = Path(f"{args.base_dir}{frame_suffix}/angular/{obs}/{chunks}")
    obs_dir_flat = Path(f"{args.base_dir}{frame_suffix}/angular/{obs}")

    # Build candidate paths for each curve
    reco_cpv_path = find_existing_file([
        obs_dir_chunk / f"{obs}_{lepton}_{chunks}_reco_combined_bins.csv",
        obs_dir_flat / f"{obs}_all_reco_{lepton}_bins.csv",
    ])
    reco_sm_path = find_existing_file([
        obs_dir_chunk / f"{obs}_{lepton}_{chunks}_sm_reco_combined_bins.csv",
        obs_dir_chunk / f"{obs}_{lepton}_{chunks}_reco_sm_combined_bins.csv",
        obs_dir_flat / f"{obs}_all_sm_reco_{lepton}_bins.csv",
    ])
    gen_cpv_path = find_existing_file([
        obs_dir_chunk / f"{obs}_{lepton}_{chunks}_gen_combined_bins.csv",
        obs_dir_flat / f"{obs}_all_gen_{lepton}_bins.csv",
    ])
    gen_sm_path = find_existing_file([
        obs_dir_chunk / f"{obs}_{lepton}_{chunks}_sm_gen_combined_bins.csv",
        obs_dir_chunk / f"{obs}_{lepton}_{chunks}_gen_sm_combined_bins.csv",
        obs_dir_flat / f"{obs}_all_sm_gen_{lepton}_bins.csv",
    ])

    curves = {
        "reco CPV":     (reco_cpv_path, "#2458a4", "-",  1.0),
        "reco SM / 20": (reco_sm_path,  "#2458a4", "--", 1 / 20),
        "gen CPV":      (gen_cpv_path,  "#b34d2e", "-",  1.0),
        "gen SM / 20":  (gen_sm_path,   "#b34d2e", "--", 1 / 20),
    }

    xlabel = f"{obs} [rad]"
    title = f"{obs} ({args.frame}), {lepton}: gen vs reco, CPV vs SM (scaled)"
    out_dir = obs_dir_chunk if obs_dir_chunk.exists() else obs_dir_flat
    out_path = out_dir / f"{obs}_{chunks}_sm_vs_cpv_gen_vs_reco_{lepton}_bins.png"
    return curves, xlabel, title, out_path


def build_ml_config(args, lepton: str) -> tuple[dict[str, tuple[Path, str, str, float]], str, str, Path]:
    if args.version == "v2":
        obs_folder = "ml_observable_v2"
    elif args.version == "v0":
        obs_folder = "ml_observable_v0"
    else:
        obs_folder = "ml_observable"

    obs_dir = Path("outputs/ml_superdataset") / obs_folder / args.feature_set / args.model_type

    curves = {
        "reco CPV":     (obs_dir / f"template_{args.split}_{lepton}_reco_cpv_bins.csv", "#2458a4", "-",  1.0),
        "reco SM / 100": (obs_dir / f"template_{args.split}_{lepton}_reco_sm_bins.csv",  "#2458a4", "--", 1 / 100),
    }
    xlabel = r"ML Score $O_{\text{ML}} = P(+) - P(-)$"
    title = f"ML Observable ({args.model_type.upper()} {args.version}), {lepton}: reco CPV vs SM (scaled)"
    out_path = obs_dir / f"ml_observable_reco_sm_vs_cpv_{lepton}_bins.png"
    return curves, xlabel, title, out_path


def plot_observable_curves(args, lepton: str):

    if args.mode == "angular":
        curves, xlabel, title, out_path = build_angular_config(args, lepton)
    else:
        curves, xlabel, title, out_path = build_ml_config(args, lepton)

    plt = import_plotting()
    fig, ax = plt.subplots(figsize=(8.0, 5.0))

    ax.tick_params(direction="in", top=True, right=True, which="both")

    for label, (path, color, linestyle, scale) in curves.items():

        try:
            hist = load_signed_histogram(path)
        except FileNotFoundError as err:
            print(f"Skipping '{label}' curve: {err}")
            continue

        scaled_signed = [s * scale for s in hist.signed]

        ax.step(
            hist.edges, 
            scaled_signed + [scaled_signed[-1]], 
            where="post",
            color=color, 
            linewidth=1.4, 
            linestyle=linestyle, 
            label=label,
        )

    ax.axhline(0.0, color="#222222", linewidth=0.8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("signed weight [fb]")
    ax.set_title(title)
    ax.legend(frameon=False)
    fig.tight_layout()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved plot: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Plot 4 curves for a given observable and lepton type.")
    parser.add_argument("--mode", choices=("angular", "ml"), default="angular", help="Select mode")

    # Angular parameters
    parser.add_argument("--observable", choices=("O_W", "O_lD"), default="O_W")
    parser.add_argument("--frame", choices=("higgs_rest", "lab", "ttbar_rest"), default="higgs_rest")
    parser.add_argument("--base-dir", default="outputs/angular_lr")
    parser.add_argument("--chunks", default="chunk1-10", help="Chunk folder tag, e.g. chunk1-10 or chunk1-79")

    # ML parameters
    parser.add_argument("--model-type", choices=("xgboost", "catboost"), default="xgboost")
    parser.add_argument("--version", choices=("v0", "v1", "v2"), default="v2")
    parser.add_argument("--feature-set", choices=("lD", "lD_auxiliary", "lD_auxiliary_wbjets"), default="lD", help="Feature set directory (e.g., lD)")
    parser.add_argument("--split", choices=("validation", "test"), default="test")
    

    args = parser.parse_args()

    for lepton in ("electron", "muon"):
        plot_observable_curves(args, lepton)


if __name__ == "__main__":
    main()