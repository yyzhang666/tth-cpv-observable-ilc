#!/usr/bin/env python3
"""Build the angular observable template (signed histogram + plots + CSV).

Usage:
    python3 scripts/build_angular_observable.py \
        --config configs/analysis_ow_lr.yaml \
        --features outputs/ow_lr/features/features_gen_higgs_rest.csv \
        --observable O_W --split test
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.histograms import SignedHistogram  # noqa: E402
from ilc_tth_cpv.io import load_analysis_config, read_table, repo_root, write_table  # noqa: E402
from ilc_tth_cpv.validation import check_phi_wrapping, check_signed_weight_sums  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--features", required=True)
    parser.add_argument("--observable", default=None, help="default: config observable_family")
    parser.add_argument("--split", default="all", choices=("all", "train", "validation", "test"))
    parser.add_argument("--weight-column", default="weight_template")
    args = parser.parse_args()

    cfg = load_analysis_config(Path(args.config))
    observable = args.observable or cfg["analysis"]["observable_family"]
    n_bins = int(cfg["observable"]["n_bins"])
    frame = cfg["observable"]["default_frame"]

    rows = read_table(Path(args.features))
    if args.split != "all":
        rows = [row for row in rows if row["split"] == args.split]

    values, weights_used, n_invalid = [], [], 0
    for row in rows:
        try:
            value = float(row[observable])
            weight = float(row[args.weight_column])
        except (KeyError, TypeError, ValueError):
            n_invalid += 1
            continue
        if value != value or weight != weight:
            n_invalid += 1
            continue
        values.append(value)
        weights_used.append(weight)

    wrap_report = check_phi_wrapping(values)
    if not wrap_report["ok"]:
        raise SystemExit(f"phi wrapping check failed: {wrap_report['problems']}")

    hist = SignedHistogram.phi_binning(n_bins)
    for value, weight in zip(values, weights_used):
        hist.fill(value, weight)

    weight_report = check_signed_weight_sums(rows, args.weight_column)

    out_dir = repo_root() / cfg["outputs"]["base_dir"] / "angular" / observable
    out_dir.mkdir(parents=True, exist_ok=True)
    bin_rows = hist.as_rows(frame=frame, observable=observable)
    write_table(out_dir / f"{observable}_{args.split}_bins.csv", bin_rows, metadata={
        "config": cfg["analysis"]["name"],
        "observable": observable,
        "frame": frame,
        "split": args.split,
        "weight_column": args.weight_column,
        "n_events_filled": len(values),
        "n_invalid": n_invalid,
        "n_out_of_range": hist.n_out_of_range,
        "integral_signed_fb": hist.integral_signed(),
        "integral_abs_fb": hist.integral_abs(),
        "weight_report": {k: v for k, v in weight_report.items() if k != "problems"},
        "created": datetime.datetime.now().isoformat(),
    })
    print(f"bins   -> {out_dir / f'{observable}_{args.split}_bins.csv'}")
    print(f"filled={len(values)} invalid={n_invalid} "
          f"signed_integral={hist.integral_signed():+.6g} fb "
          f"z_signed={weight_report['z_signed']:+.2f}")

    try:
        from ilc_tth_cpv.plotting import plot_signed_histogram

        png = plot_signed_histogram(
            hist,
            out_dir / f"{observable}_{args.split}.png",
            title=f"{observable} [{frame}] split={args.split}",
            xlabel=f"{observable} [rad]",
        )
        print(f"plot   -> {png}")
    except Exception as exc:  # matplotlib may be absent in minimal envs
        print(f"plot skipped ({exc})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
