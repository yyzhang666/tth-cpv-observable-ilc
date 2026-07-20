#!/usr/bin/env python3
"""Inspect the first reconstructed events: collections, jets, weaver scores.

Input is the kinfit-ready complete reco production (configs/samples.yaml).
Collection contract: docs/KINFIT_JET_ASSIGNMENT.md.

Usage:
    python3 scripts/inspect_reco_event.py --config configs/analysis_ow_lr.yaml --max-events 1
    python3 scripts/inspect_reco_event.py --slcio /path/to/file.slcio --max-events 1
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.io import load_analysis_config, load_yaml, repo_root  # noqa: E402
from ilc_tth_cpv.slcio import (  # noqa: E402
    four_momentum,
    get_collection,
    get_pid_parameters,
    iter_slcio_events,
    list_collections,
)

JET_COLLECTIONS = ["OutputErrorFlowJets6", "RefinedJets6"]
LEPTON_COLLECTIONS = ["ISOMuons", "ISOElectrons"]


def resolve_input(args) -> Path:
    if args.slcio:
        return Path(args.slcio)
    cfg = load_analysis_config(Path(args.config))
    manifest = load_yaml(repo_root() / cfg["samples"]["manifest"])
    sample = manifest["signals"][cfg["samples"]["reco_sample"]]
    pattern = str(Path(sample["path"]) / sample["file_pattern"])
    matches = sorted(glob.glob(pattern))
    if not matches:
        raise SystemExit(f"No reco files match {pattern}")
    return Path(matches[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config")
    parser.add_argument("--slcio")
    parser.add_argument("--max-events", type=int, default=1)
    args = parser.parse_args()
    if not args.config and not args.slcio:
        parser.error("provide --config or --slcio")

    path = resolve_input(args)
    print(f"input: {path}")

    for i, evt in enumerate(iter_slcio_events([path], max_events=args.max_events)):
        print(f"\n=== event #{i} run={evt.getRunNumber()} event={evt.getEventNumber()}")
        names = list_collections(evt)
        print(f"collections ({len(names)}):")
        for name in names:
            col = get_collection(evt, name)
            n = col.getNumberOfElements() if col is not None else "?"
            print(f"  {name:40s} n={n}")

        for jet_name in JET_COLLECTIONS:
            col = get_collection(evt, jet_name)
            if col is None:
                continue
            pid_params = get_pid_parameters(evt, jet_name, "weaver")
            print(f"\n{jet_name}:")
            for j in range(col.getNumberOfElements()):
                jet = col.getElementAt(j)
                p4 = four_momentum(jet)
                scores = pid_params[j] if j < len(pid_params) else {}
                top = sorted(scores.items(), key=lambda kv: -kv[1])[:4]
                summary = ", ".join(f"{k}={v:.3f}" for k, v in top)
                print(f"  jet {j}: E={p4[0]:7.2f} GeV  weaver[{summary}]")

        for lep_name in LEPTON_COLLECTIONS:
            col = get_collection(evt, lep_name)
            if col is None:
                continue
            print(f"\n{lep_name}: n={col.getNumberOfElements()}")
            for j in range(col.getNumberOfElements()):
                p4 = four_momentum(col.getElementAt(j))
                print(f"  lepton {j}: E={p4[0]:7.2f} GeV")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
