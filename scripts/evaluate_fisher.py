#!/usr/bin/env python3
"""Fisher information from binned templates.

I = sum_i nu1_i^2 / nu0_i  (absolute yield), optional shape-only variant,
optional parameter-independent background. Warns on invalid bins.

The SM production exists, and its written-event totals plus LR cross section
are audited, but SM feature export and the pure-RL cross section are not wired
into a normalised binned template yet (KNOWN_ISSUES: SM denominator template).
Until then use --nu0-from-abs only as a technical pipeline placeholder; it is
NOT a physics result.

Usage:
    python3 scripts/evaluate_fisher.py \
        --template outputs/ow_lr/angular/O_W/O_W_test_bins.csv \
        --nu0-from-abs --luminosity-scale 1.0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.fisher import fisher_information  # noqa: E402
from ilc_tth_cpv.io import read_table  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True,
                        help="bin CSV from build_angular_observable/build_ml_observable")
    parser.add_argument("--sm-template", default=None,
                        help="bin CSV providing nu0 (SM yields)")
    parser.add_argument("--background-template", default=None,
                        help="bin CSV providing background yields b_i")
    parser.add_argument("--nu0-from-abs", action="store_true",
                        help="TECHNICAL PLACEHOLDER: use abs_weight as nu0")
    parser.add_argument("--luminosity-scale", type=float, default=1.0,
                        help="scale factor applied to all yields (e.g. lumi * a_r)")
    parser.add_argument("--shape-only", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    rows = read_table(Path(args.template))
    nu1 = [float(row["signed_weight_fb"]) * args.luminosity_scale for row in rows]

    if args.sm_template:
        sm_rows = read_table(Path(args.sm_template))
        if len(sm_rows) != len(rows):
            raise SystemExit("SM template binning mismatch")
        nu0 = [float(row["signed_weight_fb"]) * args.luminosity_scale for row in sm_rows]
        nu0_source = args.sm_template
    elif args.nu0_from_abs:
        nu0 = [float(row["abs_weight_fb"]) * args.luminosity_scale for row in rows]
        nu0_source = "ABS-WEIGHT PLACEHOLDER (not a physics result)"
    else:
        raise SystemExit("Provide --sm-template or (technical only) --nu0-from-abs")

    background = None
    if args.background_template:
        bg_rows = read_table(Path(args.background_template))
        if len(bg_rows) != len(rows):
            raise SystemExit("Background template binning mismatch")
        background = [float(row["signed_weight_fb"]) * args.luminosity_scale
                      for row in bg_rows]

    result = fisher_information(nu0, nu1, background=background,
                                shape_only=args.shape_only)
    mode = "signal-plus-background" if background is not None else "signal-only"
    print(f"mode            : {mode}")
    print(f"nu0 source      : {nu0_source}")
    print(f"Fisher absolute : {result['fisher_absolute']:.6g}")
    if args.shape_only:
        print(f"Fisher shape    : {result['fisher_shape_only']:.6g}")
    print(f"sigma_c ~ 68%   : {result['c68']:.6g}")
    print(f"95% interval    : +/- {result['c95']:.6g}")
    if result["n_invalid_bins"]:
        print(f"WARNING: {result['n_invalid_bins']} invalid bins:")
        for row in result["per_bin"]:
            if row["invalid"]:
                print(f"  bin {row['bin_index']}: {row['invalid']} "
                      f"(nu0={row['nu0']:.4g}, nu1={row['nu1']:.4g})")

    out_path = Path(args.out) if args.out else Path(args.template).with_suffix(".fisher.json")
    payload = dict(result)
    payload.update({"mode": mode, "nu0_source": nu0_source,
                    "luminosity_scale": args.luminosity_scale,
                    "template": str(args.template)})
    with out_path.open("w") as stream:
        json.dump(payload, stream, indent=2)
    print(f"result -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
