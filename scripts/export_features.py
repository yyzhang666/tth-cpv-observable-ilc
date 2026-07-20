#!/usr/bin/env python3
"""Export the standard event feature table (DATA_SCHEMA.md).

Feature policy: RAW variables only (E, theta, phi, mass per object) — no
log/sin/cos transformations (frozen supervisor decision, see
docs/DATA_SCHEMA.md).

Generator level runs per production chunk. Reconstruction level requires the
kinfit stage output first (docs/KINFIT_JET_ASSIGNMENT.md) and fails loudly
until that reader is implemented against the fit tree.

Usage:
    python3 scripts/export_features.py --config configs/analysis_ow_lr.yaml --level gen --chunk 0
    python3 scripts/export_features.py --config ... --level gen --chunk 0 --max-events 500
"""

from __future__ import annotations

import argparse
import datetime
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv import angles, frames, weights  # noqa: E402
from ilc_tth_cpv.features import deterministic_split  # noqa: E402
from ilc_tth_cpv.io import (  # noqa: E402
    load_analysis_config,
    load_yaml,
    repo_root,
    resolve_gen_chunk,
    validate_table,
    write_table,
)
from ilc_tth_cpv.objects import identify_semileptonic_truth  # noqa: E402
from ilc_tth_cpv.slcio import four_momentum, open_stdhep, pdg  # noqa: E402

NAN = float("nan")

OBJECTS = ("wjet_quark", "wjet_antiquark", "top_b", "antitop_bbar", "lepton",
           "neutrino", "top", "antitop", "higgs")


def export_gen(cfg: dict, chunk_id: str, max_events: int) -> Path:
    manifest = load_yaml(repo_root() / cfg["samples"]["manifest"])
    sample_key = cfg["samples"]["gen_sample"]
    sample = manifest["signals"][sample_key]
    chunk = resolve_gen_chunk(sample, chunk_id)

    sidecar = weights.read_sidecar(chunk["sidecar"])
    skipped = weights.parse_skipped_events_from_log(chunk.get("physsim_log"))
    aligned = weights.align_sidecar_to_stdhep(sidecar, skipped)
    weight_report = weights.validate_signed_weights(aligned)
    if not weight_report["ok"]:
        raise SystemExit(f"Sidecar validation failed: {weight_report['problems']}")

    frame_name = cfg["observable"]["default_frame"]
    split_cfg = cfg["split"]
    fractions = {k: split_cfg[k] for k in ("train", "validation", "test")}
    # event ids unique across chunks: chunk * 1e6 + sidecar row event number
    id_offset = int(chunk["chunk"]) * 1_000_000

    reader = open_stdhep(chunk["stdhep"])
    rows = []
    n_read = 0
    for row_meta in aligned:
        if max_events and n_read >= max_events:
            break
        col = reader.readEvent()
        if col is None:
            break
        n_read += 1
        mc_list = [col.getElementAt(k) for k in range(col.getNumberOfElements())]
        truth = identify_semileptonic_truth(mc_list)

        # Convention A (theory-study primary): boost into the frame, then
        # measure angles against the fixed lab axes — no rotation after boost.
        rest_p4 = frames.rest_p4_for_frame(
            frame_name,
            four_momentum(truth.top),
            four_momentum(truth.antitop),
            four_momentum(truth.higgs),
        )

        event_id = id_offset + int(row_meta["event"])
        w_signed = float(row_meta["event_weight_signed"])
        record = {
            "event_id": event_id,
            "sample_name": sample_key,
            "chunk": chunk["chunk"],
            "process": "ttH_CPVint",
            "level": "gen",
            "helicity": cfg["analysis"]["helicity"],
            "split": deterministic_split(event_id, int(split_cfg["seed"]), fractions),
            "weight_sm": NAN,
            "weight_interference_signed": w_signed,
            "weight_interference_abs": abs(w_signed),
            "weight_quadratic": NAN,
            "weight_training": weights.training_weight(w_signed),
            "weight_polarization": NAN,
            "weight_luminosity": NAN,
            "weight_template": w_signed,
            "label": 1 if w_signed > 0 else -1,
        }

        phi_by_object = {}
        for name in OBJECTS:
            p4 = four_momentum(getattr(truth, name))
            triple = (frames.boost_only_angles(p4, rest_p4)
                      if (p4 and rest_p4) else None)
            if triple is None:
                record.update({f"{name}_E": NAN, f"{name}_theta": NAN,
                               f"{name}_phi": NAN, f"{name}_mass": NAN,
                               f"{name}_valid": 0})
            else:
                energy, cos_theta, phi = triple
                record.update({
                    f"{name}_E": energy,
                    f"{name}_theta": math.acos(cos_theta),
                    f"{name}_phi": phi,
                    f"{name}_mass": frames.invariant_mass(p4),
                    f"{name}_valid": 1,
                })
                phi_by_object[name] = phi

        def dphi(a: str, b: str) -> float:
            if a in phi_by_object and b in phi_by_object:
                return angles.delta_phi(phi_by_object[a], phi_by_object[b])
            return NAN

        # pair ordering: particle - antiparticle (PHYSICS_CONVENTIONS §4)
        record["O_W"] = dphi("wjet_quark", "wjet_antiquark")
        record["O_b"] = dphi("top_b", "antitop_bbar")
        record["O_top"] = dphi("top", "antitop")
        # O_lnu is CP-ordered: W-: phi(l-) - phi(anti-nu); W+: phi(nu) - phi(l+)
        lepton_pdg = pdg(truth.lepton)
        if lepton_pdg is not None and lepton_pdg > 0:      # l- from W-
            record["O_lnu"] = dphi("lepton", "neutrino")
        else:                                              # l+ from W+
            record["O_lnu"] = dphi("neutrino", "lepton")
        rows.append(record)

    report = validate_table(rows)
    out_dir = repo_root() / cfg["outputs"]["base_dir"] / "features"
    out_path = out_dir / f"features_gen_{frame_name}_chunk{chunk['chunk']}.csv"
    write_table(out_path, rows, metadata={
        "config": cfg["analysis"]["name"],
        "sample": sample_key,
        "chunk": chunk["chunk"],
        "level": "gen",
        "frame": frame_name,
        "basis": "lab_axes (boost only, phi vs fixed lab axes)",
        "pair_ordering": "particle - antiparticle; O_lnu CP-ordered",
        "feature_policy": "raw variables only (E, theta, phi, mass)",
        "n_sidecar": len(sidecar),
        "n_skipped": len(skipped),
        "n_exported": len(rows),
        "max_events": max_events,
        "weight_report": {k: v for k, v in weight_report.items() if k != "problems"},
        "schema_report": report,
        "created": datetime.datetime.now().isoformat(),
    })
    print(f"wrote {len(rows)} rows -> {out_path}")
    print(f"schema check: ok={report['ok']}")
    for problem in report["problems"]:
        print(f"  NOTE: {problem}")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--level", choices=("gen", "reco"), required=True)
    parser.add_argument("--chunk", default="0", help="production chunk id (default 0)")
    parser.add_argument("--max-events", type=int, default=0,
                        help="debug early stop; 0 = all (debug output is not a physics result)")
    args = parser.parse_args()

    cfg = load_analysis_config(Path(args.config))
    if args.level == "gen":
        export_gen(cfg, args.chunk, args.max_events)
        return 0
    raise SystemExit(
        "reco-level export must read the kinfit selected candidate "
        "(outputs/<analysis>/kinfit/*.root, docs/KINFIT_JET_ASSIGNMENT.md). "
        "Run scripts/run_kinfit_assignment.sh first; the tree reader is part "
        "of the student baseline work."
    )


if __name__ == "__main__":
    raise SystemExit(main())
