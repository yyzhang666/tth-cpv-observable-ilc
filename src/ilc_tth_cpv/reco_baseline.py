"""Reco-only raw baseline export for reusable ML input-feature derivation."""

from __future__ import annotations

import csv
import datetime
import glob
import json
import math
import os
import tempfile
import time
from collections import Counter
from pathlib import Path

from ilc_tth_cpv import normalization, weights
from ilc_tth_cpv.features import deterministic_split
from ilc_tth_cpv.io import load_yaml, repo_root, resolve_gen_chunk
from ilc_tth_cpv.objects import classify_higgs_decay, classify_ttbar_decay
from ilc_tth_cpv.slcio import (
    four_momentum,
    get_collection,
    get_pid_parameters,
    iter_slcio_events,
)

SCHEMA_VERSION = "reco_baseline_v3"
NAN = float("nan")

WEAVER_SCORE_KEYS = (
    "mc_u", "mc_d", "mc_s", "mc_c", "mc_b",
    "mc_ubar", "mc_dbar", "mc_sbar", "mc_cbar", "mc_bbar",
)

IDENTITY_COLUMNS = (
    "event_id", "sample_name", "chunk", "process", "level", "helicity", "split",
)
WEIGHT_COLUMNS = (
    "weight_sm", "weight_sm_shape", "weight_interference_signed",
    "weight_interference_abs", "weight_quadratic", "weight_training",
    "weight_polarization", "weight_luminosity", "weight_template", "label",
)
PRIMITIVE_COLUMNS = (
    "run_number", "event_number", "event_index", "accepted", "fit_success",
    "fit_status", "best_combo_id", "idx_W1", "idx_W2", "idx_bhad", "idx_blep",
    "idx_H1", "idx_H2", "fitprob", "fitchi2", "ndof", "final_selection_mode",
    "flavor_weight", "final_selection_score", "final_fit_score",
    "final_flavor_score", "lepton_charge", "lepton_flavor",
    "best_preselect_score", "preselect_score_W", "preselect_score_top",
    "preselect_score_H", "constraint_mode", "mW_had_prefit", "mt_had_prefit",
    "mt_lep_prefit", "mH_prefit", "mW_had_postfit", "mt_had_postfit",
    "mt_lep_postfit", "mH_postfit",
)
JET_P4_COLUMNS = tuple(
    f"jet{slot}_{component}"
    for slot in range(6)
    for component in ("E", "px", "py", "pz")
)
LEPTON_NEUTRINO_COLUMNS = (
    "lepton_lab_E", "lepton_lab_px", "lepton_lab_py", "lepton_lab_pz",
    "nu_fit_E", "nu_fit_px", "nu_fit_py", "nu_fit_pz",
)
WEAVER_COLUMNS = tuple(
    f"jet{slot}_weaver_{key}"
    for slot in range(6)
    for key in WEAVER_SCORE_KEYS
)
TRUTH_COLUMNS = ("truth_higgs_decay", "truth_ttbar_decay", "pass_truth_hbb")

RECO_BASELINE_COLUMNS = (
    IDENTITY_COLUMNS
    + WEIGHT_COLUMNS
    + PRIMITIVE_COLUMNS
    + JET_P4_COLUMNS
    + LEPTON_NEUTRINO_COLUMNS
    + WEAVER_COLUMNS
    + TRUTH_COLUMNS
)

if len(RECO_BASELINE_COLUMNS) != 148:  # pragma: no cover - import-time contract
    raise RuntimeError(f"reco baseline schema has {len(RECO_BASELINE_COLUMNS)} columns, expected 148")

ROOT_REQUIRED_BRANCHES = (
    "run_number", "event_number", "event_index", "accepted", "fit_success",
    "fit_status", "best_combo_id", "idx_W1", "idx_W2", "idx_bhad", "idx_blep",
    "idx_H1", "idx_H2", "fitprob", "fitchi2", "ndof",
    "final_selection_mode", "flavor_weight", "final_selection_score",
    "final_fit_score", "final_flavor_score", "lepton_charge",
    "nu_fit_E", "nu_fit_px", "nu_fit_py", "nu_fit_pz",
)
ROOT_OPTIONAL_NUMERIC = (
    "best_preselect_score", "preselect_score_W", "preselect_score_top",
    "preselect_score_H", "mW_had_prefit", "mt_had_prefit", "mt_lep_prefit",
    "mH_prefit", "mW_had_postfit", "mt_had_postfit", "mt_lep_postfit",
    "mH_postfit",
)
ROOT_OPTIONAL_STRING = ("constraint_mode",)
ROOT_STRING_BRANCHES = {"final_selection_mode", "constraint_mode"}


def baseline_output_path(
    out_dir: Path, component: str, chunk_id: str, max_events: int
) -> Path:
    """Return the contracted full/debug filename for one baseline table."""
    suffix = f"_max{max_events}" if max_events > 0 else ""
    return Path(out_dir) / f"features_reco_baseline_v3_{component}_chunk{chunk_id}{suffix}.csv"


def _metadata_path(table_path: Path) -> Path:
    return table_path.with_suffix(".meta.json")


def _project_row(row: dict) -> dict:
    """Project a row to the exact stable schema, rejecting accidental extras."""
    return {column: row.get(column, "" if column in {"final_selection_mode", "lepton_flavor", "constraint_mode"} else NAN) for column in RECO_BASELINE_COLUMNS}


def _sample_key(cfg: dict, component: str, level: str) -> str:
    prefix = "sm_" if component == "sm" else ""
    key = f"{prefix}{level}_sample"
    if key not in cfg["samples"]:
        raise KeyError(f"Analysis config has no samples.{key}")
    return cfg["samples"][key]


def _resolve_reco_input(cfg: dict, component: str, chunk_id: str) -> tuple[str, dict, Path]:
    manifest = load_yaml(repo_root() / cfg["samples"]["manifest"])
    key = _sample_key(cfg, component, "reco")
    sample = manifest["signals"][key]
    pattern = sample["file_pattern"].replace("*", str(chunk_id))
    matches = sorted(glob.glob(str(Path(sample["path"]) / pattern)))
    if not matches:
        raise FileNotFoundError(f"No reco SLCIO for chunk {chunk_id}: {sample['path']}/{pattern}")
    return key, sample, Path(matches[0])


def _resolve_kinfit(cfg: dict, sample_key: str, chunk_id: str) -> Path:
    filename = f"kinfit_{sample_key.replace('tth_sm', 'tthsm')}_chunk{chunk_id}.root"
    family = cfg.get("kinfit", {}).get("input_family", "physsim")
    shared = repo_root() / "data" / "kinfit" / family / filename
    legacy = repo_root() / cfg["outputs"]["base_dir"] / "kinfit" / filename
    if shared.exists():
        return shared
    if legacy.exists():
        return legacy
    return shared


def _tree_value(tree, name: str, default=NAN):
    try:
        value = getattr(tree, name)
    except Exception:
        return default
    if name in ROOT_STRING_BRANCHES:
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


def _read_selected_rows(root_path: Path, max_events: int) -> tuple[list[dict], dict]:
    if not root_path.exists() or root_path.stat().st_size <= 0:
        raise FileNotFoundError(f"Missing or empty kinfit ROOT: {root_path}")
    try:
        import ROOT  # type: ignore
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(f"Cannot import ROOT; source the ZHH environment ({exc})") from exc

    handle = ROOT.TFile.Open(str(root_path))
    if not handle or handle.IsZombie():
        raise RuntimeError(f"Cannot open kinfit ROOT: {root_path}")
    try:
        tree = handle.Get("TTHSemiLepKinFit")
        if tree is None:
            raise RuntimeError(f"Missing TTHSemiLepKinFit tree in {root_path}")
        branches = {str(branch.GetName()) for branch in tree.GetListOfBranches()}
        missing = [name for name in ROOT_REQUIRED_BRANCHES if name not in branches]
        if missing:
            raise RuntimeError("Kinfit ROOT missing required branches: " + ", ".join(missing))
        rows: list[dict] = []
        status_skipped = 0
        total = int(tree.GetEntries())
        for entry in range(total):
            tree.GetEntry(entry)
            if int(_tree_value(tree, "accepted", 0)) != 1 or int(_tree_value(tree, "fit_success", 0)) != 1:
                status_skipped += 1
                continue
            row = {name: _tree_value(tree, name) for name in ROOT_REQUIRED_BRANCHES}
            for name in ROOT_OPTIONAL_NUMERIC:
                row[name] = _tree_value(tree, name) if name in branches else NAN
            for name in ROOT_OPTIONAL_STRING:
                row[name] = _tree_value(tree, name, "") if name in branches else ""
            rows.append(row)
            if max_events and len(rows) >= max_events:
                break
        return rows, {
            "root_entries": total,
            "n_selected_rows": len(rows),
            "n_status_skipped": status_skipped,
        }
    finally:
        handle.Close()


def _first_isolated_lepton(event):
    for collection_name, flavor_name in (("ISOElectrons", "electron"), ("ISOMuons", "muon")):
        collection = get_collection(event, collection_name)
        if collection is not None and collection.getNumberOfElements() > 0:
            return collection.getElementAt(0), flavor_name
    return None, ""


def _read_snapshots(slcio_path: Path, needed_indices: set[int]) -> dict[int, dict]:
    snapshots: dict[int, dict] = {}
    if not needed_indices:
        return snapshots
    highest = max(needed_indices)
    for index, event in enumerate(iter_slcio_events([slcio_path])):
        if index > highest and len(snapshots) == len(needed_indices):
            break
        if index not in needed_indices:
            continue
        p4_collection = get_collection(event, "OutputErrorFlowJets6")
        pid_collection = get_collection(event, "RefinedJets6")
        truth_collection = get_collection(event, "MCParticlesSkimmed")
        if p4_collection is None or pid_collection is None or truth_collection is None:
            raise RuntimeError(f"Missing required collection in event_index={index}")
        if p4_collection.getNumberOfElements() != 6 or pid_collection.getNumberOfElements() != 6:
            raise RuntimeError(f"Expected six p4/PID jet slots in event_index={index}")
        p4s = [four_momentum(p4_collection.getElementAt(slot)) for slot in range(6)]
        if any(p4 is None for p4 in p4s):
            raise RuntimeError(f"Invalid OutputErrorFlowJets6 p4 in event_index={index}")
        weaver = get_pid_parameters(event, "RefinedJets6", "weaver")
        if len(weaver) != 6:
            raise RuntimeError(f"Expected six Weaver PID slots in event_index={index}")
        truth = [truth_collection.getElementAt(slot) for slot in range(truth_collection.getNumberOfElements())]
        lepton, lepton_flavor = _first_isolated_lepton(event)
        snapshots[index] = {
            "run_number": int(event.getRunNumber()),
            "event_number": int(event.getEventNumber()),
            "jets": p4s,
            "weaver": weaver,
            "lepton": four_momentum(lepton),
            "lepton_flavor": lepton_flavor,
            "truth_higgs_decay": classify_higgs_decay(truth),
            "truth_ttbar_decay": classify_ttbar_decay(truth),
        }
        if len(snapshots) == len(needed_indices):
            break
    missing = sorted(needed_indices - set(snapshots))
    if missing:
        raise RuntimeError(f"SLCIO ended before selected event indices: {missing[:5]}")
    return snapshots


def _weight_fields(component: str, signed_weight: float = NAN, sm_weights: dict | None = None) -> dict:
    if component == "interference":
        signed = float(signed_weight)
        return {
            "weight_sm": NAN, "weight_sm_shape": NAN,
            "weight_interference_signed": signed,
            "weight_interference_abs": abs(signed), "weight_quadratic": NAN,
            "weight_training": weights.training_weight(signed),
            "weight_polarization": NAN, "weight_luminosity": NAN,
            "weight_template": signed, "label": 1 if signed > 0.0 else -1,
        }
    if sm_weights is None:
        raise ValueError("SM component requires normalization")
    physical = float(sm_weights["physical_weight_fb"])
    return {
        "weight_sm": physical, "weight_sm_shape": float(sm_weights["shape_weight"]),
        "weight_interference_signed": NAN, "weight_interference_abs": NAN,
        "weight_quadratic": NAN, "weight_training": NAN,
        "weight_polarization": NAN, "weight_luminosity": NAN,
        "weight_template": physical, "label": 0,
    }


def _atomic_write(table_path: Path, rows: list[dict], metadata: dict) -> None:
    if not rows:
        raise ValueError("Refusing to publish an empty baseline table")
    table_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path = _metadata_path(table_path)
    csv_tmp = meta_tmp = None
    backups: dict[Path, Path] = {}
    published: list[Path] = []
    try:
        with tempfile.NamedTemporaryFile("w", newline="", dir=table_path.parent, prefix=f".{table_path.name}.", suffix=".tmp", delete=False) as stream:
            csv_tmp = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=RECO_BASELINE_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        payload = dict(metadata)
        payload["table"] = table_path.name
        with tempfile.NamedTemporaryFile("w", dir=table_path.parent, prefix=f".{meta_path.name}.", suffix=".tmp", delete=False) as stream:
            meta_tmp = Path(stream.name)
            json.dump(payload, stream, indent=2, sort_keys=True, default=str)
        for target in (table_path, meta_path):
            if target.exists():
                handle, backup_name = tempfile.mkstemp(
                    dir=target.parent, prefix=f".{target.name}.", suffix=".bak"
                )
                os.close(handle)
                backup = Path(backup_name)
                backup.unlink()
                os.replace(target, backup)
                backups[target] = backup
        os.replace(csv_tmp, table_path)
        csv_tmp = None
        published.append(table_path)
        os.replace(meta_tmp, meta_path)
        meta_tmp = None
        published.append(meta_path)
        for backup in backups.values():
            backup.unlink(missing_ok=True)
        backups.clear()
    except Exception:
        for target in published:
            target.unlink(missing_ok=True)
        for target, backup in backups.items():
            if backup.exists():
                os.replace(backup, target)
        backups.clear()
        raise
    finally:
        for temporary in (csv_tmp, meta_tmp):
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def export_reco_baseline(
    cfg: dict,
    *,
    component: str,
    chunk_id: str,
    out_dir: Path,
    max_events: int = 0,
    overwrite: bool = False,
) -> Path:
    """Export one selected-kinfit, truth-Hbb raw reco baseline chunk."""
    if component not in {"interference", "sm"}:
        raise ValueError(f"unsupported component: {component}")
    if max_events < 0:
        raise ValueError("max_events must be non-negative")
    start = time.monotonic()
    resolved_out_dir = Path(out_dir)
    if not resolved_out_dir.is_absolute():
        resolved_out_dir = repo_root() / resolved_out_dir
    target = baseline_output_path(resolved_out_dir, component, str(chunk_id), max_events)
    meta_target = _metadata_path(target)
    if not overwrite and (target.exists() or meta_target.exists()):
        raise FileExistsError(f"Refusing to overwrite existing baseline pair: {target}, {meta_target}")

    manifest = load_yaml(repo_root() / cfg["samples"]["manifest"])
    sample_key, reco_sample, slcio_path = _resolve_reco_input(cfg, component, str(chunk_id))
    root_path = _resolve_kinfit(cfg, sample_key, str(chunk_id))
    selected_rows, root_report = _read_selected_rows(root_path, max_events)
    if not selected_rows:
        raise RuntimeError(f"No accepted && fit_success rows in {root_path}")

    sidecar: list[dict] = []
    skipped: set[int] = set()
    aligned = None
    weight_report = None
    sm_weight_report = None
    gen_sidecar = None
    if component == "interference":
        gen_sample = manifest["signals"][_sample_key(cfg, component, "gen")]
        gen_chunk = resolve_gen_chunk(gen_sample, str(chunk_id))
        gen_sidecar = gen_chunk["sidecar"]
        sidecar = weights.read_sidecar(gen_sidecar)
        skipped = weights.parse_skipped_events_from_log(gen_chunk.get("physsim_log"))
        aligned = weights.align_sidecar_to_stdhep(sidecar, skipped)
        weight_report = weights.validate_signed_weights(aligned)
        if not weight_report["ok"]:
            raise RuntimeError(f"Sidecar validation failed: {weight_report['problems']}")
    else:
        sm_weight_report = normalization.sm_chunk_weights(reco_sample)

    needed = {int(row["event_index"]) for row in selected_rows}
    snapshots = _read_snapshots(slcio_path, needed)
    split_cfg = cfg["split"]
    fractions = {name: split_cfg[name] for name in ("train", "validation", "test")}
    id_offset = int(chunk_id) * 1_000_000
    truth_counts: Counter[str] = Counter()
    missing_score_counts: Counter[str] = Counter({key: 0 for key in WEAVER_SCORE_KEYS})
    event_mismatch = 0
    rows: list[dict] = []

    for fit_row in selected_rows:
        event_index = int(fit_row["event_index"])
        if aligned is not None and not 0 <= event_index < len(aligned):
            raise RuntimeError(f"event_index {event_index} outside aligned sidecar length {len(aligned)}")
        snapshot = snapshots[event_index]
        if int(fit_row["event_number"]) != int(snapshot["event_number"]):
            event_mismatch += 1
        truth_higgs = snapshot["truth_higgs_decay"]
        truth_ttbar = snapshot["truth_ttbar_decay"]
        truth_counts[f"higgs_mode::{truth_higgs}"] += 1
        truth_counts[f"ttbar_mode::{truth_ttbar}"] += 1
        if truth_higgs != "H->bb":
            truth_counts["rejected_non_hbb"] += 1
            continue
        truth_counts["selected_hbb"] += 1

        row_meta = aligned[event_index] if aligned is not None else None
        event_id = id_offset + (int(row_meta["event"]) if row_meta else event_index + 1)
        record = {
            "event_id": event_id,
            "sample_name": sample_key,
            "chunk": str(chunk_id),
            "process": "ttH_CPVint" if component == "interference" else "ttH_SM",
            "level": "reco",
            "helicity": cfg["analysis"]["helicity"],
            "split": deterministic_split(event_id, int(split_cfg["seed"]), fractions),
        }
        record.update(_weight_fields(component, float(row_meta["event_weight_signed"]) if row_meta else NAN, sm_weight_report))
        record.update(fit_row)
        record["lepton_flavor"] = snapshot["lepton_flavor"]

        for slot, p4 in enumerate(snapshot["jets"]):
            for suffix, value in zip(("E", "px", "py", "pz"), p4):
                record[f"jet{slot}_{suffix}"] = value
        lepton = snapshot["lepton"]
        for suffix, value in zip(("E", "px", "py", "pz"), lepton if lepton is not None else (NAN,) * 4):
            record[f"lepton_lab_{suffix}"] = value
        for slot, scores in enumerate(snapshot["weaver"]):
            for key in WEAVER_SCORE_KEYS:
                value = scores.get(key, NAN)
                if key not in scores or not math.isfinite(float(value)):
                    missing_score_counts[key] += 1
                    value = NAN
                record[f"jet{slot}_weaver_{key}"] = value
        record.update({
            "truth_higgs_decay": truth_higgs,
            "truth_ttbar_decay": truth_ttbar,
            "pass_truth_hbb": 1,
        })
        rows.append(_project_row(record))

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "frame": "lab_raw",
        "level": "reco",
        "status": "diagnostic_smoke" if max_events > 0 else "baseline_export",
        "config": cfg.get("_source_path", cfg["analysis"].get("name")),
        "component": component,
        "sample": sample_key,
        "chunk": str(chunk_id),
        "helicity": cfg["analysis"]["helicity"],
        "kinfit_root": root_path,
        "reco_slcio": slcio_path,
        "gen_sidecar": gen_sidecar,
        "collections": {
            "jet_p4": "OutputErrorFlowJets6",
            "jet_pid": "RefinedJets6",
            "pid_algorithm": "weaver",
            "truth": "MCParticlesSkimmed",
            "isolated_lepton_priority": ["ISOElectrons", "ISOMuons"],
            "slot_alignment": "OutputErrorFlowJets6 p4 slot i is paired with RefinedJets6/weaver PID slot i",
        },
        "columns": list(RECO_BASELINE_COLUMNS),
        "n_columns": len(RECO_BASELINE_COLUMNS),
        "weaver_score_keys": list(WEAVER_SCORE_KEYS),
        "split": {"seed": split_cfg["seed"], "fractions": fractions},
        "truth_selection": {
            "higgs": "classify_higgs_decay(MCParticlesSkimmed) == 'H->bb'",
            "ttbar": "recorded but not filtered",
            "denominator": "accepted==1 && fit_success==1 kinfit rows intersect truth H->bb",
        },
        "root_entries": root_report["root_entries"],
        "n_kinfit_selected_before_truth_hbb": len(selected_rows),
        "n_status_skipped": root_report["n_status_skipped"],
        "truth_selection_counts": dict(sorted(truth_counts.items())),
        "n_event_number_mismatch": event_mismatch,
        "missing_weaver_score_counts": dict(sorted(missing_score_counts.items())),
        "n_exported": len(rows),
        "max_events": max_events,
        "weight_report": {key: value for key, value in weight_report.items() if key != "problems"} if weight_report else None,
        "sm_normalization": sm_weight_report,
        "event_alignment": (
            "kinfit event_index is the input SLCIO record index; interference sidecar is accepted-event-order aligned"
            if component == "interference"
            else "kinfit event_index is the SM input SLCIO record index"
        ),
        "n_sidecar": len(sidecar),
        "n_skipped_sidecar_events": len(skipped),
        "elapsed_seconds": time.monotonic() - start,
        "created": datetime.datetime.now().isoformat(),
    }
    _atomic_write(target, rows, metadata)
    return target
