#!/usr/bin/env python3
"""Export the standard event feature table (DATA_SCHEMA.md).

Feature policy: RAW variables only (E, theta, phi, mass per object) — no
log/sin/cos transformations (frozen supervisor decision, see
docs/DATA_SCHEMA.md).

Generator level runs per production chunk. Reconstruction level reads the
standard TTHSemiLepKinFit ROOT output first produced by
scripts/run_kinfit_assignment.sh, then joins the selected indices to the
matching complete_reco_kinfit_ready SLCIO chunk for jet four-vectors.

Usage:
    python3 scripts/export_features.py --config configs/analysis_ow_lr.yaml --level gen --chunk 0
    python3 scripts/export_features.py --config configs/analysis_ow_lr.yaml --level reco --chunk 0
    python3 scripts/export_features.py --config ... --level gen --chunk 0 --max-events 500
"""

from __future__ import annotations

import argparse
import datetime
import glob
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
from ilc_tth_cpv.slcio import (  # noqa: E402
    four_momentum,
    get_collection,
    get_pid_parameters,
    iter_slcio_events,
    open_stdhep,
    pdg,
)

NAN = float("nan")

OBJECTS = ("wjet_quark", "wjet_antiquark", "top_b", "antitop_bbar", "lepton",
           "neutrino", "top", "antitop", "higgs")

RECO_KINFIT_BRANCHES = (
    "run_number",
    "event_number",
    "event_index",
    "accepted",
    "fit_success",
    "fit_status",
    "best_combo_id",
    "idx_W1",
    "idx_W2",
    "idx_bhad",
    "idx_blep",
    "idx_H1",
    "idx_H2",
    "fitprob",
    "fitchi2",
    "chi2_over_ndof",
    "ndof",
    "final_selection_mode",
    "flavor_weight",
    "final_selection_score",
    "final_fit_score",
    "final_flavor_score",
)

RECO_KINFIT_OPTIONAL_BRANCHES = (
    "top_n",
    "best_preselect_score",
    "preselect_score_W",
    "preselect_score_top",
    "preselect_score_H",
    "n_constraints",
    "n_unmeasured",
    "constraint_mode",
    "mW_had_prefit",
    "mt_had_prefit",
    "mt_lep_prefit",
    "mH_prefit",
    "mW_had_postfit",
    "mt_had_postfit",
    "mt_lep_postfit",
    "mH_postfit",
    "lepton_charge",
    "lepton_flavor",
)

RECO_STRING_BRANCHES = {"constraint_mode", "final_selection_mode"}

RECO_SLOT_BRANCHES = {
    "wjet_quark": "idx_W1",
    "wjet_antiquark": "idx_W2",
    "top_b": "idx_bhad",
    "antitop_bbar": "idx_blep",
}

WEAVER_SUMMARY_KEYS = ("mc_b", "mc_bbar", "mc_c", "mc_cbar")


def add_p4s(*items):
    if any(item is None for item in items):
        return None
    return (
        sum(item[0] for item in items),
        sum(item[1] for item in items),
        sum(item[2] for item in items),
        sum(item[3] for item in items),
    )


def safe_theta(cos_theta: float) -> float:
    return math.acos(max(-1.0, min(1.0, float(cos_theta))))


def resolve_reco_chunk(cfg: dict, chunk_id: str) -> dict:
    manifest = load_yaml(repo_root() / cfg["samples"]["manifest"])
    sample_key = cfg["samples"]["reco_sample"]
    sample = manifest["signals"][sample_key]
    pattern = sample["file_pattern"].replace("*", str(chunk_id))
    matches = sorted(glob.glob(str(Path(sample["path"]) / pattern)))
    if not matches:
        raise FileNotFoundError(
            f"No reco SLCIO for chunk {chunk_id}: {sample['path']}/{pattern}"
        )
    return {
        "chunk": str(chunk_id),
        "sample_key": sample_key,
        "sample": sample,
        "slcio": Path(matches[0]),
    }


def kinfit_root_path(cfg: dict, sample_key: str, chunk_id: str) -> Path:
    return (
        repo_root()
        / cfg["outputs"]["base_dir"]
        / "kinfit"
        / f"kinfit_{sample_key}_chunk{chunk_id}.root"
    )


def first_isolated_lepton(evt):
    # Same collection order as TTHSemiLepKinFit::collectLeptons.
    for name in ("ISOElectrons", "ISOMuons"):
        col = get_collection(evt, name)
        if col is None:
            continue
        if col.getNumberOfElements() > 0:
            return col.getElementAt(0)
    return None


def read_reco_snapshots(slcio_path: Path, needed_indices: set[int]) -> dict:
    snapshots = {}
    if not needed_indices:
        return snapshots
    highest = max(needed_indices)
    for idx, evt in enumerate(iter_slcio_events([slcio_path])):
        if idx > highest and len(snapshots) == len(needed_indices):
            break
        if idx not in needed_indices:
            continue
        jets = get_collection(evt, "OutputErrorFlowJets6")
        if jets is None:
            raise RuntimeError(f"Missing OutputErrorFlowJets6 in event index {idx}")
        jet_p4s = [
            four_momentum(jets.getElementAt(k))
            for k in range(jets.getNumberOfElements())
        ]
        lepton = first_isolated_lepton(evt)
        yth = get_pid_parameters(evt, "RefinedJets6", "yth")
        weaver = get_pid_parameters(evt, "RefinedJets6", "weaver")
        snapshots[idx] = {
            "run_number": int(evt.getRunNumber()),
            "event_number": int(evt.getEventNumber()),
            "jets": jet_p4s,
            "lepton": four_momentum(lepton),
            "yth": next((row for row in yth if row), {}),
            "weaver": weaver,
        }
        if len(snapshots) == len(needed_indices):
            break
    missing = sorted(needed_indices - set(snapshots))
    if missing:
        raise RuntimeError(
            f"SLCIO ended before selected event indices could be read: {missing[:5]}"
        )
    return snapshots


def branch_names(tree) -> set[str]:
    return {str(branch.GetName()) for branch in tree.GetListOfBranches()}


def tree_value(tree, name: str, default=NAN):
    try:
        value = getattr(tree, name)
    except Exception:
        return default
    if name in RECO_STRING_BRANCHES:
        try:
            return value.c_str()
        except Exception:
            return str(value)
    if isinstance(value, str):
        return value
    if hasattr(value, "c_str"):
        try:
            return value.c_str()
        except Exception:
            pass
    try:
        return int(value) if isinstance(value, int) else float(value)
    except Exception:
        return value


def read_selected_kinfit_rows(root_path: Path, max_events: int) -> tuple[list[dict], dict]:
    if not root_path.exists():
        raise SystemExit(
            f"Missing kinfit ROOT: {root_path}\n"
            "Run first: bash scripts/run_kinfit_assignment.sh "
            "--config <same config> --chunk <same chunk>"
        )
    if root_path.stat().st_size <= 0:
        raise SystemExit(f"Empty kinfit ROOT: {root_path}")
    try:
        import ROOT  # type: ignore
    except Exception as exc:
        raise SystemExit(f"Cannot import ROOT; run: source env/setup.sh first ({exc})")

    handle = ROOT.TFile.Open(str(root_path))
    if not handle or handle.IsZombie():
        raise SystemExit(f"Cannot open kinfit ROOT: {root_path}")
    tree = handle.Get("TTHSemiLepKinFit")
    if tree is None:
        handle.Close()
        raise SystemExit(f"Missing TTHSemiLepKinFit tree in {root_path}")

    branches = branch_names(tree)
    missing = [name for name in RECO_KINFIT_BRANCHES if name not in branches]
    if missing:
        handle.Close()
        raise SystemExit(
            "Kinfit ROOT is missing required branches: " + ", ".join(missing)
        )

    rows = []
    total_entries = int(tree.GetEntries())
    n_status_skipped = 0
    for entry in range(total_entries):
        tree.GetEntry(entry)
        if int(tree_value(tree, "accepted", 0)) != 1 or int(tree_value(tree, "fit_success", 0)) != 1:
            n_status_skipped += 1
            continue
        row = {name: tree_value(tree, name) for name in RECO_KINFIT_BRANCHES}
        for name in RECO_KINFIT_OPTIONAL_BRANCHES:
            if name in branches:
                row[name] = tree_value(tree, name)
        rows.append(row)
        if max_events and len(rows) >= max_events:
            break
    handle.Close()

    return rows, {
        "root_entries": total_entries,
        "n_selected_rows": len(rows),
        "n_status_skipped": n_status_skipped,
        "branches_checked": list(RECO_KINFIT_BRANCHES),
    }


def jet_by_index(jets: list, index_value) -> tuple | None:
    try:
        idx = int(index_value)
    except Exception:
        return None
    if idx < 0 or idx >= len(jets):
        return None
    return jets[idx]


def fill_object_features(record: dict, object_p4: dict, rest_p4) -> dict:
    phi_by_object = {}
    for name in OBJECTS:
        p4 = object_p4.get(name)
        triple = (
            frames.boost_only_angles(p4, rest_p4)
            if (p4 is not None and rest_p4 is not None)
            else None
        )
        if triple is None:
            record.update({f"{name}_E": NAN, f"{name}_theta": NAN,
                           f"{name}_phi": NAN, f"{name}_mass": NAN,
                           f"{name}_valid": 0})
        else:
            energy, cos_theta, phi = triple
            record.update({
                f"{name}_E": energy,
                f"{name}_theta": safe_theta(cos_theta),
                f"{name}_phi": phi,
                f"{name}_mass": frames.invariant_mass(p4),
                f"{name}_valid": 1,
            })
            phi_by_object[name] = phi
    return phi_by_object


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


def export_reco(cfg: dict, chunk_id: str, max_events: int) -> Path:
    manifest = load_yaml(repo_root() / cfg["samples"]["manifest"])
    reco = resolve_reco_chunk(cfg, chunk_id)
    sample_key = reco["sample_key"]
    root_path = kinfit_root_path(cfg, sample_key, reco["chunk"])

    kinfit_rows, kinfit_report = read_selected_kinfit_rows(root_path, max_events)
    if not kinfit_rows:
        raise SystemExit(
            f"No accepted && fit_success rows in {root_path}"
            + (f" within max_events={max_events}" if max_events else "")
        )

    gen_sample = manifest["signals"][cfg["samples"]["gen_sample"]]
    gen_chunk = resolve_gen_chunk(gen_sample, reco["chunk"])
    sidecar = weights.read_sidecar(gen_chunk["sidecar"])
    skipped = weights.parse_skipped_events_from_log(gen_chunk.get("physsim_log"))
    aligned = weights.align_sidecar_to_stdhep(sidecar, skipped)
    weight_report = weights.validate_signed_weights(aligned)
    if not weight_report["ok"]:
        raise SystemExit(f"Sidecar validation failed: {weight_report['problems']}")

    frame_name = cfg["observable"]["default_frame"]
    split_cfg = cfg["split"]
    fractions = {k: split_cfg[k] for k in ("train", "validation", "test")}
    id_offset = int(reco["chunk"]) * 1_000_000

    needed_indices = {int(row["event_index"]) for row in kinfit_rows}
    snapshots = read_reco_snapshots(reco["slcio"], needed_indices)
    rows = []
    n_event_number_mismatch = 0
    for fit_row in kinfit_rows:
        event_index = int(fit_row["event_index"])
        if event_index < 0 or event_index >= len(aligned):
            raise SystemExit(
                f"Kinfit event_index {event_index} is outside aligned sidecar "
                f"length {len(aligned)}"
            )
        snapshot = snapshots[event_index]
        if int(fit_row["event_number"]) != int(snapshot["event_number"]):
            n_event_number_mismatch += 1
        row_meta = aligned[event_index]
        w_signed = float(row_meta["event_weight_signed"])
        event_id = id_offset + int(row_meta["event"])

        record = {
            "event_id": event_id,
            "sample_name": sample_key,
            "chunk": reco["chunk"],
            "process": "ttH_CPVint",
            "level": "reco",
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

        for key, value in fit_row.items():
            record[key] = value

        jets = snapshot["jets"]
        w1 = jet_by_index(jets, fit_row["idx_W1"])
        w2 = jet_by_index(jets, fit_row["idx_W2"])
        bhad = jet_by_index(jets, fit_row["idx_bhad"])
        blep = jet_by_index(jets, fit_row["idx_blep"])
        h1 = jet_by_index(jets, fit_row["idx_H1"])
        h2 = jet_by_index(jets, fit_row["idx_H2"])
        lepton = snapshot["lepton"]

        # Reco names follow the frozen selected-pair contract:
        # W1-W2 for O_W and b_had-b_lep for O_b. The neutrino fit p4 is not
        # stored in the best tree, so the leptonic top composite is visible-only.
        object_p4 = {
            "wjet_quark": w1,
            "wjet_antiquark": w2,
            "top_b": bhad,
            "antitop_bbar": blep,
            "lepton": lepton,
            "neutrino": None,
            "top": add_p4s(w1, w2, bhad),
            "antitop": add_p4s(lepton, blep),
            "higgs": add_p4s(h1, h2),
        }
        rest_p4 = frames.rest_p4_for_frame(
            frame_name,
            object_p4["top"],
            object_p4["antitop"],
            object_p4["higgs"],
        )
        phi_by_object = fill_object_features(record, object_p4, rest_p4)

        def dphi(a: str, b: str) -> float:
            if a in phi_by_object and b in phi_by_object:
                return angles.delta_phi(phi_by_object[a], phi_by_object[b])
            return NAN

        record["O_W"] = dphi("wjet_quark", "wjet_antiquark")
        record["O_b"] = dphi("top_b", "antitop_bbar")
        record["O_top"] = dphi("top", "antitop")
        record["O_lnu"] = dphi("lepton", "neutrino")

        yth = snapshot["yth"]
        for key in ("y45", "y56", "y67"):
            record[key] = float(yth.get(key, NAN))

        weaver = snapshot["weaver"]
        for key in WEAVER_SUMMARY_KEYS:
            values = [float(row[key]) for row in weaver if key in row]
            record[f"max_weaver_{key}"] = max(values) if values else NAN
        for slot_name, branch in RECO_SLOT_BRANCHES.items():
            idx = int(fit_row[branch])
            scores = weaver[idx] if 0 <= idx < len(weaver) else {}
            for key in WEAVER_SUMMARY_KEYS:
                record[f"{slot_name}_weaver_{key}"] = float(scores.get(key, NAN))

        rows.append(record)

    report = validate_table(rows, required_objects=list(OBJECTS))
    out_dir = repo_root() / cfg["outputs"]["base_dir"] / "features"
    out_path = out_dir / f"features_reco_{frame_name}_chunk{reco['chunk']}.csv"
    write_table(out_path, rows, metadata={
        "config": cfg["analysis"]["name"],
        "sample": sample_key,
        "chunk": reco["chunk"],
        "level": "reco",
        "frame": frame_name,
        "basis": "lab_axes (boost only, phi vs fixed lab axes)",
        "pair_ordering": "selected W1-W2 for O_W; selected b_had-b_lep for O_b",
        "feature_policy": "raw variables only (E, theta, phi, mass)",
        "kinfit_root": root_path,
        "reco_slcio": reco["slcio"],
        "gen_sidecar": gen_chunk["sidecar"],
        "n_sidecar": len(sidecar),
        "n_skipped": len(skipped),
        "n_exported": len(rows),
        "max_events": max_events,
        "event_index_alignment": "TTHSemiLepKinFit event_index is the input SLCIO record index; sidecar uses accepted-event-order matching",
        "n_event_number_mismatch": n_event_number_mismatch,
        "neutrino_note": "best-tree fitted neutrino p4 is not stored; neutrino columns are NaN and leptonic-top composite is visible-only",
        "kinfit_report": kinfit_report,
        "weight_report": {k: v for k, v in weight_report.items() if k != "problems"},
        "schema_report": report,
        "created": datetime.datetime.now().isoformat(),
    })
    print(f"wrote {len(rows)} rows -> {out_path}")
    print(f"schema check: ok={report['ok']}")
    for problem in report["problems"]:
        print(f"  NOTE: {problem}")
    if n_event_number_mismatch:
        print(f"  NOTE: event_number mismatches vs SLCIO: {n_event_number_mismatch}")
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
    export_reco(cfg, args.chunk, args.max_events)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
