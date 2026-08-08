import csv
import argparse

from ilc_tth_cpv.plotting import import_plotting
from ilc_tth_cpv.histograms import SignedHistogram


def load_signed_histogram(path) -> SignedHistogram:
    """Load a CSV file into a SignedHistogram object."""
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))

    edges = [float(r["bin_low"]) for r in rows] + [float(rows[-1]["bin_high"])]
    signed = [float(r["signed_weight_fb"]) for r in rows]

    return SignedHistogram(edges=edges, signed=signed)


def plot_four_curves(
    observable: str, 
    frame: str,
    lepton: str,
    base_dir: str = "outputs/angular_lr",):

    frame_suffix = "" if frame == "higgs_rest" else f"_{frame}"
    obs_dir = f"{base_dir}{frame_suffix}/angular/{observable}"
    curves = {
        "reco CPV": (f"{obs_dir}/{observable}_all_reco_{lepton}_bins.csv", "#2458a4", "-", 1.0),
        "reco SM / 10":  (f"{obs_dir}/{observable}_all_sm_reco_{lepton}_bins.csv", "#2458a4", "--", 0.1),
        "gen CPV":  (f"{obs_dir}/{observable}_all_gen_{lepton}_bins.csv", "#b34d2e", "-", 1.0),
        "gen SM / 10":   (f"{obs_dir}/{observable}_all_sm_gen_{lepton}_bins.csv", "#b34d2e", "--", 0.1),
    }

    plt = import_plotting()
    fig, ax = plt.subplots(figsize=(8.0, 5.0))

    for label, (path, color, linestyle, scale) in curves.items():
        # Load SignedHistogram object
        hist = load_signed_histogram(path)

        # Scale the signed weights by the scaling factor (SM*0.1, SPV*1)
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
    ax.set_xlabel(f"{observable} [rad]")
    ax.set_ylabel("signed weight [fb]")
    ax.set_title(f"{observable}, {lepton}: gen vs reco, CPV vs SM (scaled)")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()

    out_path=f"{obs_dir}/{observable}_all_sm_vs_cpv_gen_vs_reco_{lepton}_bins.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved plot: {out_path}")

def main():
    parser = argparse.ArgumentParser(description="Plot 4 curves for a given observable and lepton type.")
    parser.add_argument("--observable", choices=("O_W", "O_lD"), default="O_W")
    parser.add_argument("--frame", choices=("higgs_rest", "lab", "ttbar_rest"), default="higgs_rest")

    args = parser.parse_args()

    for lepton in ("electron", "muon"):
        plot_four_curves(
            observable=args.observable,
            frame=args.frame,
            lepton=lepton,
        )

if __name__ == "__main__":
    main()