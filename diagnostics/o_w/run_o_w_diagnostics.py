#!/usr/bin/env python3
"""Local-only O_W ordering diagnostics.

This script reads the existing exported feature CSVs. It does not rerun
kinfit, modify the production workflow, or replace the headline total-retention
definition.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


N_BINS = 36
LOW = -math.pi
HIGH = math.pi
DEFAULT_LUMINOSITY_FB = 8000.0
DEFAULT_SHUFFLES = 2000


@dataclass
class Sample:
    name: str
    rows: list[dict[str, str]]
    value: np.ndarray
    weight: np.ndarray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root containing outputs/ow_lr/features",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "results",
    )
    parser.add_argument(
        "--luminosity-scale",
        type=float,
        default=DEFAULT_LUMINOSITY_FB,
        help="Integrated luminosity in fb^-1 applied to both nu1 and nu0",
    )
    parser.add_argument("--bins", type=int, default=N_BINS)
    parser.add_argument("--n-shuffles", type=int, default=DEFAULT_SHUFFLES)
    parser.add_argument("--seed", type=int, default=20260723)
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def finite_float(row: dict[str, str], column: str) -> float | None:
    try:
        value = float(row[column])
    except (KeyError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def wrap_phi(value: float) -> float:
    """Wrap to the repository convention [-pi, pi)."""
    return (value + math.pi) % (2.0 * math.pi) - math.pi


def current_o_w(row: dict[str, str]) -> float | None:
    return finite_float(row, "O_W")


def eta_ordered_o_w(row: dict[str, str]) -> float | None:
    """Order the existing pair by larger pseudorapidity eta first.

    The theta and phi values are those already exported in the configured
    analysis frame. For the current files this is the Higgs-rest Ma basis.
    """
    theta_1 = finite_float(row, "wjet_quark_theta")
    theta_2 = finite_float(row, "wjet_antiquark_theta")
    phi_1 = finite_float(row, "wjet_quark_phi")
    phi_2 = finite_float(row, "wjet_antiquark_phi")
    if None in (theta_1, theta_2, phi_1, phi_2):
        return None
    assert theta_1 is not None and theta_2 is not None
    assert phi_1 is not None and phi_2 is not None
    if not (0.0 < theta_1 < math.pi and 0.0 < theta_2 < math.pi):
        return None
    eta_1 = -math.log(math.tan(0.5 * theta_1))
    eta_2 = -math.log(math.tan(0.5 * theta_2))
    if eta_1 >= eta_2:
        return wrap_phi(phi_1 - phi_2)
    return wrap_phi(phi_2 - phi_1)


def select_all(_: dict[str, str]) -> bool:
    return True


def select_opposite_preferences(row: dict[str, str]) -> bool:
    return row.get("w_orientation_status") == "opposite_preferences"


def make_sample(
    name: str,
    rows: Iterable[dict[str, str]],
    value_fn: Callable[[dict[str, str]], float | None],
    weight_column: str,
    selection: Callable[[dict[str, str]], bool] = select_all,
) -> Sample:
    used_rows: list[dict[str, str]] = []
    values: list[float] = []
    weights: list[float] = []
    for row in rows:
        if not selection(row):
            continue
        value = value_fn(row)
        weight = finite_float(row, weight_column)
        if value is None or weight is None:
            continue
        used_rows.append(row)
        values.append(value)
        weights.append(weight)
    return Sample(
        name=name,
        rows=used_rows,
        value=np.asarray(values, dtype=float),
        weight=np.asarray(weights, dtype=float),
    )


def histogram(sample: Sample, edges: np.ndarray) -> dict[str, np.ndarray]:
    signed, _ = np.histogram(sample.value, bins=edges, weights=sample.weight)
    absolute, _ = np.histogram(
        sample.value, bins=edges, weights=np.abs(sample.weight)
    )
    sumw2, _ = np.histogram(
        sample.value, bins=edges, weights=np.square(sample.weight)
    )
    entries, _ = np.histogram(sample.value, bins=edges)
    return {
        "signed": signed.astype(float),
        "absolute": absolute.astype(float),
        "sumw2": sumw2.astype(float),
        "entries": entries.astype(int),
    }


def fisher(nu1_fb: np.ndarray, nu0_fb: np.ndarray, luminosity: float) -> dict:
    nu1 = luminosity * np.asarray(nu1_fb, dtype=float)
    nu0 = luminosity * np.asarray(nu0_fb, dtype=float)
    valid = np.isfinite(nu0) & np.isfinite(nu1) & (nu0 > 0.0)
    invalid_signal = (~valid) & (np.abs(nu1) > 0.0)
    per_bin = np.zeros_like(nu1)
    per_bin[valid] = np.square(nu1[valid]) / nu0[valid]
    information = float(np.sum(per_bin[valid]))
    return {
        "fisher_absolute": information,
        "c68": float(1.0 / math.sqrt(information)) if information > 0.0 else math.inf,
        "c95": float(1.96 / math.sqrt(information)) if information > 0.0 else math.inf,
        "n_invalid_bins": int(np.count_nonzero(invalid_signal)),
        "per_bin": per_bin,
    }


def odd_power_fraction(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    total_power = float(np.dot(values, values))
    if total_power == 0.0:
        return math.nan
    odd = 0.5 * (values - values[::-1])
    return float(np.dot(odd, odd) / total_power)


def cosine_similarity(first: np.ndarray, second: np.ndarray) -> float:
    denominator = float(np.linalg.norm(first) * np.linalg.norm(second))
    if denominator == 0.0:
        return math.nan
    return float(np.dot(first, second) / denominator)


def read_signed_template(path: Path) -> np.ndarray:
    with path.open(newline="") as stream:
        return np.asarray(
            [float(row["signed_weight_fb"]) for row in csv.DictReader(stream)],
            dtype=float,
        )


def shuffled_fisher(
    cpv: Sample,
    sm_hist: dict[str, np.ndarray],
    edges: np.ndarray,
    luminosity: float,
    n_shuffles: int,
    rng: np.random.Generator,
    observed_fisher: float,
) -> dict[str, float]:
    if n_shuffles <= 0 or len(cpv.weight) == 0:
        return {}
    values = np.empty(n_shuffles, dtype=float)
    for index in range(n_shuffles):
        shuffled = rng.permutation(cpv.weight)
        signed, _ = np.histogram(cpv.value, bins=edges, weights=shuffled)
        values[index] = fisher(signed, sm_hist["signed"], luminosity)[
            "fisher_absolute"
        ]
    return {
        "shuffle_mean": float(np.mean(values)),
        "shuffle_median": float(np.median(values)),
        "shuffle_p95": float(np.quantile(values, 0.95)),
        "shuffle_p99": float(np.quantile(values, 0.99)),
        "shuffle_pvalue": float(
            (np.count_nonzero(values >= observed_fisher) + 1) / (n_shuffles + 1)
        ),
    }


def write_template(
    path: Path,
    frame: str,
    method: str,
    hist: dict[str, np.ndarray],
    edges: np.ndarray,
    weight_column: str,
    n_input: int,
    n_used: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    centers = 0.5 * (edges[:-1] + edges[1:])
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "frame",
                "observable",
                "bin_index",
                "bin_low",
                "bin_high",
                "bin_center",
                "signed_weight_fb",
                "abs_weight_fb",
                "local_signed_fraction",
                "entries",
                "sumw2_fb2",
            ]
        )
        for index, center in enumerate(centers):
            absolute = hist["absolute"][index]
            fraction = hist["signed"][index] / absolute if absolute > 0.0 else math.nan
            writer.writerow(
                [
                    frame,
                    "O_W",
                    index,
                    edges[index],
                    edges[index + 1],
                    center,
                    hist["signed"][index],
                    absolute,
                    fraction,
                    hist["entries"][index],
                    hist["sumw2"][index],
                ]
            )
    metadata = {
        "status": "local_NAF_diagnostic",
        "frame": frame,
        "observable": "O_W",
        "method": method,
        "weight_column": weight_column,
        "n_input_rows": n_input,
        "n_events_filled": n_used,
        "integral_signed_fb": float(np.sum(hist["signed"])),
        "integral_abs_fb": float(np.sum(hist["absolute"])),
        "table": path.name,
    }
    path.with_suffix(".meta.json").write_text(json.dumps(metadata, indent=2) + "\n")


def plot_templates(
    path: Path,
    title: str,
    test_statement: str,
    cpv_hist: dict[str, np.ndarray],
    sm_hist: dict[str, np.ndarray],
    edges: np.ndarray,
    cpv_n: int,
    sm_n: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    centers = 0.5 * (edges[:-1] + edges[1:])
    half_width = 0.5 * np.diff(edges)
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(9.2, 7.2),
        sharex=True,
        gridspec_kw={"height_ratios": [1.25, 1.0]},
        constrained_layout=True,
    )
    axes[0].errorbar(
        centers,
        cpv_hist["signed"],
        xerr=half_width,
        yerr=np.sqrt(cpv_hist["sumw2"]),
        fmt="o",
        markersize=3.2,
        linewidth=1.0,
        capsize=1.5,
        color="#b42318",
        label=f"signed CPV interference ({cpv_n} events)",
    )
    axes[0].axhline(0.0, color="#202124", linewidth=0.8)
    axes[0].set_ylabel("signed weight / bin [fb]")
    axes[0].legend(frameon=False, loc="best")
    axes[0].grid(alpha=0.2)

    axes[1].bar(
        centers,
        sm_hist["signed"],
        width=0.94 * np.diff(edges),
        color="#2878b5",
        alpha=0.82,
        label=f"SM denominator ({sm_n} events)",
    )
    axes[1].set_xlabel(r"$O_W$ [rad]")
    axes[1].set_ylabel("SM weight / bin [fb]")
    axes[1].set_xlim(LOW, HIGH)
    axes[1].legend(frameon=False, loc="best")
    axes[1].grid(axis="y", alpha=0.2)

    fig.suptitle(title, fontsize=14)
    axes[0].set_title(test_statement, fontsize=9, pad=6)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_case(
    *,
    key: str,
    method: str,
    level: str,
    cpv_rows: list[dict[str, str]],
    sm_rows: list[dict[str, str]],
    value_fn: Callable[[dict[str, str]], float | None],
    selection: Callable[[dict[str, str]], bool],
    output_dir: Path,
    edges: np.ndarray,
    luminosity: float,
    n_shuffles: int,
    rng: np.random.Generator,
    make_plot: bool,
    plot_title: str,
    test_statement: str,
) -> dict:
    cpv = make_sample(
        f"{key}_cpv", cpv_rows, value_fn, "weight_template", selection
    )
    sm = make_sample(f"{key}_sm", sm_rows, value_fn, "weight_sm", selection)
    cpv_hist = histogram(cpv, edges)
    sm_hist = histogram(sm, edges)
    result = fisher(cpv_hist["signed"], sm_hist["signed"], luminosity)
    shuffle = shuffled_fisher(
        cpv,
        sm_hist,
        edges,
        luminosity,
        n_shuffles,
        rng,
        result["fisher_absolute"],
    )

    case_dir = output_dir / key
    write_template(
        case_dir / "cpv_bins.csv",
        "higgs_rest",
        method,
        cpv_hist,
        edges,
        "weight_template",
        len(cpv_rows),
        len(cpv.rows),
    )
    write_template(
        case_dir / "sm_bins.csv",
        "higgs_rest",
        method,
        sm_hist,
        edges,
        "weight_sm",
        len(sm_rows),
        len(sm.rows),
    )
    if make_plot:
        plot_templates(
            case_dir / "distribution.png",
            plot_title,
            test_statement,
            cpv_hist,
            sm_hist,
            edges,
            len(cpv.rows),
            len(sm.rows),
        )

    payload = {
        "key": key,
        "status": "local_NAF_diagnostic",
        "method": method,
        "level": level,
        "frame": "higgs_rest",
        "luminosity_scale_fb_inverse": luminosity,
        "n_bins": len(edges) - 1,
        "cpv_input_rows": len(cpv_rows),
        "cpv_used_rows": len(cpv.rows),
        "sm_input_rows": len(sm_rows),
        "sm_used_rows": len(sm.rows),
        "cpv_integral_signed_fb": float(np.sum(cpv_hist["signed"])),
        "cpv_integral_abs_fb": float(np.sum(cpv_hist["absolute"])),
        "sm_integral_fb": float(np.sum(sm_hist["signed"])),
        "cpv_odd_power_fraction": odd_power_fraction(cpv_hist["signed"]),
        "fisher_absolute": result["fisher_absolute"],
        "sigma_c_68": result["c68"],
        "interval_c_95_half_width": result["c95"],
        "n_invalid_bins": result["n_invalid_bins"],
        **shuffle,
    }
    (case_dir / "result.json").write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def write_summary_plot(path: Path, results: list[dict]) -> None:
    labels = [
        "gen current",
        "gen eta-order",
        "reco current",
        "reco opposite-only",
        "reco eta-order",
    ]
    values = [row["fisher_absolute"] for row in results]
    null_p95 = [row.get("shuffle_p95", math.nan) for row in results]
    colors = ["#6c757d", "#2878b5", "#6c757d", "#d97706", "#b42318"]
    fig, ax = plt.subplots(figsize=(9.0, 5.0), constrained_layout=True)
    positions = np.arange(len(results))
    ax.bar(positions, values, color=colors, width=0.7, label="observed")
    ax.scatter(
        positions,
        null_p95,
        marker="_",
        s=500,
        linewidth=2.0,
        color="#111111",
        label="95% sign-shuffle level",
        zorder=3,
    )
    ax.set_yscale("log")
    ax.set_xticks(positions, labels, rotation=18, ha="right")
    ax.set_ylabel("binned Fisher information")
    fig.suptitle("O_W ordering diagnostics", fontsize=14)
    ax.set_title(
        "This compares ordering choices with fixed samples, frame, bins and luminosity.",
        fontsize=9,
        pad=6,
    )
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir.resolve()
    feature_dir = repo_root / "outputs" / "ow_lr" / "features"
    paths = {
        "cpv_gen": feature_dir / "features_gen_higgs_rest_chunk0.csv",
        "sm_gen": feature_dir / "features_sm_gen_higgs_rest_chunk0.csv",
        "cpv_reco": feature_dir / "features_reco_higgs_rest_chunk0.csv",
        "sm_reco": feature_dir / "features_sm_reco_higgs_rest_chunk0.csv",
    }
    rows = {key: read_rows(path) for key, path in paths.items()}
    edges = np.linspace(LOW, HIGH, args.bins + 1)
    rng = np.random.default_rng(args.seed)

    common = {
        "output_dir": output_dir,
        "edges": edges,
        "luminosity": args.luminosity_scale,
        "n_shuffles": args.n_shuffles,
        "rng": rng,
    }
    results = [
        run_case(
            key="baseline_gen",
            method="truth q/qbar ordering already present in exported gen features",
            level="gen",
            cpv_rows=rows["cpv_gen"],
            sm_rows=rows["sm_gen"],
            value_fn=current_o_w,
            selection=select_all,
            make_plot=False,
            plot_title="",
            test_statement="",
            **common,
        ),
        run_case(
            key="eta_ordered_gen",
            method="larger same-frame pseudorapidity eta first; exported gen pair",
            level="gen",
            cpv_rows=rows["cpv_gen"],
            sm_rows=rows["sm_gen"],
            value_fn=eta_ordered_o_w,
            selection=select_all,
            make_plot=True,
            plot_title=r"Generator pair: $\eta$-ordered $O_W$",
            test_statement=(
                "This tests whether identity-free eta ordering retains the "
                "generator-level signed interference."
            ),
            **common,
        ),
        run_case(
            key="baseline_reco",
            method="current conditional Weaver q/qbar ordering",
            level="reco",
            cpv_rows=rows["cpv_reco"],
            sm_rows=rows["sm_reco"],
            value_fn=current_o_w,
            selection=select_all,
            make_plot=False,
            plot_title="",
            test_statement="",
            **common,
        ),
        run_case(
            key="opposite_preferences_reco",
            method=(
                "current Weaver q/qbar ordering, restricted independently in "
                "CPV and SM to w_orientation_status=opposite_preferences"
            ),
            level="reco",
            cpv_rows=rows["cpv_reco"],
            sm_rows=rows["sm_reco"],
            value_fn=current_o_w,
            selection=select_opposite_preferences,
            make_plot=True,
            plot_title=r"Reco $O_W$: opposite Weaver preferences only",
            test_statement=(
                "This tests the current q/qbar ordering where the two selected "
                "jets prefer opposite signs."
            ),
            **common,
        ),
        run_case(
            key="eta_ordered_reco",
            method=(
                "larger same-frame pseudorapidity eta first; current selected "
                "kinfit pair; no offline pair reranking"
            ),
            level="reco",
            cpv_rows=rows["cpv_reco"],
            sm_rows=rows["sm_reco"],
            value_fn=eta_ordered_o_w,
            selection=select_all,
            make_plot=True,
            plot_title=r"Current reco kinfit pair: $\eta$-ordered $O_W$",
            test_statement=(
                "This tests eta ordering while preserving the production "
                "kinfit pair, frame, event population and weights."
            ),
            **common,
        ),
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    templates = {
        result["key"]: read_signed_template(
            output_dir / result["key"] / "cpv_bins.csv"
        )
        for result in results
    }
    matching_reference = {
        "baseline_gen": "baseline_gen",
        "eta_ordered_gen": "eta_ordered_gen",
        "baseline_reco": "baseline_gen",
        "opposite_preferences_reco": "baseline_gen",
        "eta_ordered_reco": "eta_ordered_gen",
    }
    for result in results:
        key = result["key"]
        result["cosine_to_current_gen"] = cosine_similarity(
            templates[key], templates["baseline_gen"]
        )
        reference_key = matching_reference[key]
        result["shape_reference"] = reference_key
        result["cosine_to_matching_gen"] = cosine_similarity(
            templates[key], templates[reference_key]
        )
        (output_dir / key / "result.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )

    summary_columns = [
        "key",
        "level",
        "cpv_input_rows",
        "cpv_used_rows",
        "sm_input_rows",
        "sm_used_rows",
        "cpv_integral_signed_fb",
        "cpv_integral_abs_fb",
        "sm_integral_fb",
        "cpv_odd_power_fraction",
        "cosine_to_current_gen",
        "shape_reference",
        "cosine_to_matching_gen",
        "fisher_absolute",
        "sigma_c_68",
        "interval_c_95_half_width",
        "shuffle_mean",
        "shuffle_median",
        "shuffle_p95",
        "shuffle_p99",
        "shuffle_pvalue",
        "n_invalid_bins",
    ]
    with (output_dir / "summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=summary_columns)
        writer.writeheader()
        for result in results:
            writer.writerow({key: result.get(key, "") for key in summary_columns})
    (output_dir / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
    write_summary_plot(output_dir / "fisher_summary.png", results)

    print(f"results -> {output_dir}")
    for result in results:
        print(
            f"{result['key']:27s} "
            f"N(CPV/SM)={result['cpv_used_rows']}/{result['sm_used_rows']} "
            f"I={result['fisher_absolute']:.6g} "
            f"shuffle95={result.get('shuffle_p95', math.nan):.6g} "
            f"p={result.get('shuffle_pvalue', math.nan):.4g}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
