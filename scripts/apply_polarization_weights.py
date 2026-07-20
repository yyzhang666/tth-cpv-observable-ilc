#!/usr/bin/env python3
"""Apply LCF polarisation weights to an event table.

Adds weight_polarization (a_r or b_r by helicity) and weight_luminosity
(fraction * total lumi) for one running configuration, and refreshes
weight_template = base physics weight * a/b * luminosity.
Runs the closure check first and refuses to continue on failure.

Usage:
    python3 scripts/apply_polarization_weights.py \
        --features outputs/ow_lr/features/features_gen_higgs_rest.csv \
        --scenario configs/lcf_polarization.yaml \
        --running mp
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.io import load_yaml, read_table, write_table  # noqa: E402
from ilc_tth_cpv.polarization import closure_check, physical_event_weight, running_weights  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", required=True)
    parser.add_argument("--scenario", default="configs/lcf_polarization.yaml")
    parser.add_argument("--running", required=True, help="mm / mp / pm / pp")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    scenario = load_yaml(Path(args.scenario))
    closure = closure_check(scenario["running"])
    if not closure["ok"]:
        raise SystemExit(f"Polarisation closure failed: {closure['problems']}")
    factors = running_weights(scenario["running"], scenario["total_luminosity_ab"])
    if args.running not in factors:
        raise SystemExit(f"Unknown running config {args.running}; have {sorted(factors)}")
    cfg = factors[args.running]
    print(f"running={args.running} a={cfg['a']:.4f} b={cfg['b']:.4f} "
          f"lumi={cfg['luminosity_ab']:.3f} ab^-1")

    rows = read_table(Path(args.features))
    lumi_fb = cfg["luminosity_ab"] * 1000.0
    for row in rows:
        base = float(row["weight_interference_signed"])
        pol = physical_event_weight(row["helicity"], 1.0, cfg["a"], cfg["b"])
        row["weight_polarization"] = pol
        row["weight_luminosity"] = lumi_fb
        # base weight is in fb -> yield = w[fb] * pol * L[fb^-1]
        row["weight_template"] = base * pol * lumi_fb

    out_path = Path(args.out) if args.out else Path(
        str(args.features).replace(".csv", f".pol_{args.running}.csv")
    )
    write_table(out_path, rows, metadata={
        "scenario": str(args.scenario),
        "running": args.running,
        "factors": cfg,
        "closure": closure,
        "source": str(args.features),
        "created": datetime.datetime.now().isoformat(),
    })
    print(f"wrote -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
