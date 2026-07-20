#!/usr/bin/env python3
"""Inspect the first generator events of the sample defined in a config.

Prints identified truth objects, frame angles, and sidecar weights, so the
student can verify the sample before running anything heavy.

Usage:
    python3 scripts/inspect_generator_event.py --config configs/analysis_ow_lr.yaml --max-events 3
    python3 scripts/inspect_generator_event.py --config ... --chunk 5 --max-events 3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv import angles, frames, weights  # noqa: E402
from ilc_tth_cpv.io import load_analysis_config, load_yaml, repo_root, resolve_gen_chunk  # noqa: E402
from ilc_tth_cpv.objects import identify_semileptonic_truth  # noqa: E402
from ilc_tth_cpv.slcio import four_momentum, open_stdhep, pdg  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--chunk", default="0", help="production chunk id (default 0)")
    parser.add_argument("--max-events", type=int, default=3)
    args = parser.parse_args()

    cfg = load_analysis_config(Path(args.config))
    manifest = load_yaml(repo_root() / cfg["samples"]["manifest"])
    sample = manifest["signals"][cfg["samples"]["gen_sample"]]
    chunk = resolve_gen_chunk(sample, args.chunk)

    print(f"sample     : {cfg['samples']['gen_sample']} (chunk {chunk['chunk']})")
    print(f"stdhep     : {chunk['stdhep']}")
    print(f"sidecar    : {chunk['sidecar']}")

    sidecar = weights.read_sidecar(chunk["sidecar"])
    skipped = weights.parse_skipped_events_from_log(chunk.get("physsim_log"))
    aligned = weights.align_sidecar_to_stdhep(sidecar, skipped)
    report = weights.validate_signed_weights(aligned)
    print(f"sidecar rows={len(sidecar)} skipped={len(skipped)} aligned={len(aligned)}")
    print(f"weight check: ok={report['ok']} n_pos={report['n_pos']} "
          f"n_neg={report['n_neg']} signed_sum={report['signed_sum_fb']:.6g} fb")
    for problem in report["problems"]:
        print(f"  PROBLEM: {problem}")

    reader = open_stdhep(chunk["stdhep"])
    for i in range(args.max_events):
        col = reader.readEvent()
        if col is None:
            break
        mc_list = [col.getElementAt(k) for k in range(col.getNumberOfElements())]
        truth = identify_semileptonic_truth(mc_list)
        row = aligned[i]
        print(f"\n=== event {row['event']} (stdhep #{i}) "
              f"w_signed={row['event_weight_signed']:+.6g} fb")
        for name in ("higgs", "top", "antitop", "top_b", "antitop_bbar",
                     "wjet_quark", "wjet_antiquark", "lepton", "neutrino"):
            obj = getattr(truth, name)
            p4 = four_momentum(obj)
            if p4 is None:
                print(f"  {name:14s}: MISSING")
                continue
            print(f"  {name:14s}: pdg={pdg(obj):+4d} E={p4[0]:8.2f} GeV")

        top_p4, antitop_p4 = four_momentum(truth.top), four_momentum(truth.antitop)
        higgs_p4 = four_momentum(truth.higgs)
        for frame_name in cfg["observable"]["frames"]:
            rest_p4 = frames.rest_p4_for_frame(frame_name, top_p4, antitop_p4, higgs_p4)
            if rest_p4 is None:
                print(f"  frame {frame_name:11s}: cannot build")
                continue
            q_p4 = four_momentum(truth.wjet_quark)
            qbar_p4 = four_momentum(truth.wjet_antiquark)
            if q_p4 is None or qbar_p4 is None:
                print(f"  frame {frame_name:11s}: hadronic W daughters missing")
                continue
            q = frames.boost_only_angles(q_p4, rest_p4)
            qbar = frames.boost_only_angles(qbar_p4, rest_p4)
            if q is None or qbar is None:
                continue
            o_w = angles.delta_phi(q[2], qbar[2])
            print(f"  frame {frame_name:11s}: O_W = {o_w:+.4f} rad")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
