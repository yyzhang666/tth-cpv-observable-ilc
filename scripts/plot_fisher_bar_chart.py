import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np


angular_observable = "O_lD"

OBSERVABLE_LATEX = {
    "O_W": r"O_W",
    "O_lD": r"O_{\ell D}",
}

latex_obs = OBSERVABLE_LATEX.get(angular_observable, angular_observable)

# ============================================================
# Frame-specific directories
# ============================================================
FRAME_DIRECTORIES = {
    "Lab Frame": Path(
        f"outputs/angular_lr_lab/angular/{angular_observable}/chunk_1-10"
    ),
    "ttbar Rest Frame": Path(
        f"outputs/angular_lr_ttbar_rest/angular/{angular_observable}/chunk_1-10"
    ),
    "Higgs Rest Frame": Path(
        f"outputs/angular_lr/angular/{angular_observable}/chunk1-10"
    ),
}

channels = ["electron", "muon"]


def load_fisher_value(json_path):
    """Safely extract fisher_absolute from a JSON file."""
    path = Path(json_path)

    if not path.exists():
        print(f"Warning: File not found -> {path}")
        return 0.0

    try:
        with open(path, "r") as f:
            data = json.load(f)

        return float(data.get("fisher_absolute", 0.0))

    except (json.JSONDecodeError, ValueError, TypeError) as e:
        print(f"Warning: Could not read {path}: {e}")
        return 0.0


def build_file_path(frame_key, channel, level):
    """
    Build the Fisher JSON path for a given frame, channel and level.

    level = 'gen' or 'reco'
    """
    directory = FRAME_DIRECTORIES[frame_key]

    filename = (
        f"{angular_observable}_{channel}_chunk1-10_{level}.fisher.json"
    )

    return directory / filename


# ============================================================
# Check all paths before plotting
# ============================================================
print("\nChecking Fisher information files:\n")

for frame_name in FRAME_DIRECTORIES:
    for channel in channels:
        for level in ["gen", "reco"]:
            path = build_file_path(frame_name, channel, level)
            print(f"{frame_name:20s} | "
                  f"{channel:8s} | "
                  f"{level:4s} -> {path}")


# ============================================================
# Create figure
# ============================================================
fig, axes = plt.subplots(
    1,
    2,
    figsize=(14, 6),
    sharey=True,
    dpi=300
)

frames = list(FRAME_DIRECTORIES.keys())

x = np.arange(len(frames))
width = 0.35


# ============================================================
# Plot electron and muon separately
# ============================================================
for idx, ch in enumerate(channels):

    ax = axes[idx]

    # --------------------------------------------------------
    # Load Fisher information
    # --------------------------------------------------------
    gen_vals = [
        load_fisher_value(
            build_file_path(frame_name, ch, "gen")
        )
        for frame_name in frames
    ]

    reco_vals = [
        load_fisher_value(
            build_file_path(frame_name, ch, "reco")
        )
        for frame_name in frames
    ]

    # --------------------------------------------------------
    # Plot bars
    # --------------------------------------------------------
    rects1 = ax.bar(
        x - width / 2,
        gen_vals,
        width,
        label="Parton Level (Gen)",
        color="#2458a4",
        #edgecolor="black",
        alpha=0.9,
    )

    rects2 = ax.bar(
        x + width / 2,
        reco_vals,
        width,
        label="Detector Level (Reco)",
        color="#b34d2e",
        #edgecolor="black",
        alpha=0.9,
    )

    # --------------------------------------------------------
    # Styling
    # --------------------------------------------------------
    ax.set_title(
        f"Channel: {ch.capitalize()}",
        fontsize=14,
        pad=12,
        fontweight="bold",
    )

    ax.set_xticks(x)

    ax.tick_params(
        axis="both",
        which="both",
        direction="in",
        top=True,
        right=True,
        labelsize=10,
    )

    ax.set_xticklabels(
        frames,
        fontsize=11,
        fontweight="bold"
    )

    #ax.grid(axis="y", linestyle="--", alpha=0.5)

    if idx == 0:
        ax.set_ylabel(
            fr"Fisher Information $\mathcal{{I}}({latex_obs})$",
            fontsize=13,
            fontweight="bold",
        )

        ax.legend(
            frameon=False,
            fontsize=11,
            loc="upper left"
        )

    # --------------------------------------------------------
    # Annotate values and retention
    # --------------------------------------------------------
    for i in range(len(frames)):

        g_val = gen_vals[i]
        r_val = reco_vals[i]

        # Gen
        if g_val > 0:
            ax.annotate(
                f"{g_val:.2f}",
                xy=(x[i] - width / 2, g_val),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
            )

        # Reco + retention
        if r_val > 0:

            retention = (
                r_val / g_val * 100
                if g_val > 0
                else 0
            )

            ax.annotate(
                f"{r_val:.2f}\n({retention:.1f}%)",
                xy=(x[i] + width / 2, r_val),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8.5,
                color="#a13d00",
                fontweight="bold",
            )


# ============================================================
# Dynamic Y-axis limit
# ============================================================
all_vals = []

for ch in channels:

    for frame_name in frames:

        all_vals.append(
            load_fisher_value(
                build_file_path(frame_name, ch, "gen")
            )
        )

        all_vals.append(
            load_fisher_value(
                build_file_path(frame_name, ch, "reco")
            )
        )


max_y = max(all_vals, default=1.0)

axes[0].set_ylim(
    0,
    max_y * 1.25
)


# ============================================================
# Figure title
# ============================================================
plt.suptitle(
    fr"Fisher Information Sensitivity & Frame Reconstruction Loss (${latex_obs}$)",
    fontsize=16,
    fontweight="bold",
    y=1.02,
)

plt.tight_layout()


# ============================================================
# Save plot
# ============================================================
out_dir = Path(f"outputs/angular_lr_plots/{angular_observable}")
out_dir.mkdir(
    parents=True,
    exist_ok=True
)

output_path = (
    out_dir /
    "fisher_info_frames_electron_vs_muon.png"
)

plt.savefig(
    output_path,
    bbox_inches="tight"
)

print(
    f"\nPlot successfully saved to:\n{output_path}"
)

plt.show()