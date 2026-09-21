#!/usr/bin/env python3
"""Apply the frozen PHYSSIM jet-truth helper to Whizard common4730 q_reco rows.

This is a conditional cross-generator diagnostic.  It does not rerank
candidates and it does not alter the external PHYSSIM truth implementation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_SELECTED_SHA256 = "885a86c45f0ce64255af5edb60c9148ffc0bcfdd2813234b6c13d7bde7dbc540"
DEFAULT_SOURCES_SHA256 = "22ac26aa42257e08c92afe04ef38fd0321b547fd2b7eb9138816ec429fe74522"
DEFAULT_FILTERED_MANIFEST_SHA256 = "e5966d8e68029713e2ba089936f15a0d90df9eb8f6462d5294b60ce1169b7adf"
DEFAULT_TRUTH_HELPER_SHA256 = "0d058caa16ab8e1f560c8cc75d817c5b4ec29a67cb5edd720d0472fb54d9fd33"
EXPECTED_PER_SOURCE = {
    "whizard_I410213_0": 1168,
    "whizard_I410213_1": 1168,
    "whizard_I410213_2": 1168,
    "whizard_I410213_3": 1226,
}
BASE_DENOMINATOR = 4730
METHOD = "q_reco minimize [signed-flavor-preselected Top10]"
INTERNAL_MODE = "authoritative_best_tree"
SELECTED_STAGE = "authoritative postfit candidate choice; pair indices on raw/prefit OutputErrorFlowJets6"
TRUTH_DEFINITION = "unchanged PHYSSIM truth on RefinedJets6 via >=0.95 collection bridge"
COLLECTIONS = {
    "fit": "OutputErrorFlowJets6",
    "refined": "RefinedJets6",
    "truejets": "TrueJets",
    "truejet_link": "TrueJetPFOLink",
    "recomc_link": "RecoMCTruthLink",
    "mc": "MCParticlesSkimmed",
}
BRIDGE_MINIMUM_DICE = 0.95
TOP_MINIMUM_DICE = 0.2
REQUIRED_ROOT_BRANCHES = {
    "event_index", "run_number", "event_number", "accepted", "fit_success",
    "best_combo_id", "idx_W1", "idx_W2", "idx_bhad", "idx_blep", "idx_H1",
    "idx_H2", "jet_collection_name", "flavor_jet_collection_name",
}


class IntegrityError(RuntimeError):
    pass


def hard(code: str, detail: str = "") -> IntegrityError:
    return IntegrityError(code + (f": {detail}" if detail else ""))


def diagnostic_status(evaluable: int, coverage: float) -> str:
    if evaluable == 0:
        return "no_evaluable_events"
    return "cross_generator_diagnostic" if coverage >= 0.95 else "conditional_cross_generator_diagnostic"


def should_plot(evaluable: int) -> bool:
    return evaluable > 0


def validate_flags(flags: Mapping[str, Any]) -> dict[str, bool]:
    normalized = {name: bool(flags[name]) for name in ("W", "top", "H", "all")}
    if normalized["all"] != (normalized["W"] and normalized["top"] and normalized["H"]):
        raise hard("unexpected_exception", "all flag is not W-and-top-and-H")
    return normalized


def sha256(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen_json(path: Path, expected_hash: str) -> dict[str, Any]:
    observed = sha256(path)
    if observed != expected_hash:
        raise hard("source_file_hash_mismatch", f"{path}: {observed} != {expected_hash}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_selected(path: Path, expected_hash: str) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    if sha256(path) != expected_hash:
        raise hard("selected_csv_hash_mismatch")
    required = {
        "source_file_id", "local_index", "run_number", "event_number",
        "kinfit_signed_combo_id",
    }
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(required - set(reader.fieldnames or ()))
        if missing:
            raise hard("missing_selected_key", f"selected-common fields {missing}")
        rows = [
            {
                "source_file_id": row["source_file_id"],
                "local_index": int(row["local_index"]),
                "run_number": int(row["run_number"]),
                "event_number": int(row["event_number"]),
                "kinfit_signed_combo_id": int(row["kinfit_signed_combo_id"]),
            }
            for row in reader
        ]
    keys = [
        (row["source_file_id"], row["local_index"], row["run_number"], row["event_number"])
        for row in rows
    ]
    if len(rows) != BASE_DENOMINATOR or len(set(keys)) != BASE_DENOMINATOR:
        if len(set(keys)) != len(keys):
            raise hard("duplicate_selected_key")
        raise hard("selected_count_mismatch", f"{len(rows)} != {BASE_DENOMINATOR}")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["source_file_id"]].append(row)
    counts = {source: len(grouped[source]) for source in sorted(grouped)}
    if counts != EXPECTED_PER_SOURCE:
        raise hard("selected_per_source_mismatch", str(counts))
    for source_rows in grouped.values():
        source_rows.sort(key=lambda row: row["local_index"])
    return rows, grouped


def read_mapping(path: Path, expected_hash: str, source_rows: list[dict[str, Any]]) -> list[dict[str, int | str]]:
    if sha256(path) != expected_hash:
        raise hard("mapping_hash_mismatch", str(path))
    required = {
        "source_file_id", "filtered_local_index", "original_local_index",
        "run_number", "event_number",
    }
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(required - set(reader.fieldnames or ()))
        if missing:
            raise hard("mapping_key_mismatch", f"missing fields {missing}")
        rows = [
            {
                "source_file_id": row["source_file_id"],
                "filtered_local_index": int(row["filtered_local_index"]),
                "original_local_index": int(row["original_local_index"]),
                "run_number": int(row["run_number"]),
                "event_number": int(row["event_number"]),
            }
            for row in reader
        ]
    expected = [
        (row["source_file_id"], index, row["local_index"], row["run_number"], row["event_number"])
        for index, row in enumerate(source_rows)
    ]
    observed = [
        (row["source_file_id"], row["filtered_local_index"], row["original_local_index"], row["run_number"], row["event_number"])
        for row in rows
    ]
    if observed != expected:
        raise hard("mapping_key_mismatch", str(path))
    return rows


def expected_indices(assignment: Mapping[str, Any]) -> dict[str, list[int]]:
    return {
        "W": [int(value) for value in assignment["W"]],
        "top": [int(assignment["top_b"]), int(assignment["lep_b"])],
        "H": [int(value) for value in assignment["H"]],
    }


def validate_candidate_row(
    root_row: Mapping[str, Any], selected_row: Mapping[str, Any], assignment: Mapping[str, Any]
) -> dict[str, Any]:
    if int(root_row["accepted"]) != 1 or int(root_row["fit_success"]) != 1:
        if int(root_row["accepted"]) != 1:
            raise hard("root_not_accepted")
        raise hard("root_fit_unsuccessful")
    combo = int(selected_row["kinfit_signed_combo_id"])
    if int(root_row["best_combo_id"]) != combo or int(assignment["combo_id"]) != combo:
        raise hard("best_combo_mismatch")
    if (int(root_row["run_number"]), int(root_row["event_number"])) != (
        int(selected_row["run_number"]), int(selected_row["event_number"])
    ):
        raise hard("root_run_event_mismatch")
    if str(root_row["jet_collection_name"]) != COLLECTIONS["fit"]:
        raise hard("explicit_indices_combo_mismatch", "fit jet collection changed")
    if str(root_row["flavor_jet_collection_name"]) != COLLECTIONS["refined"]:
        raise hard("explicit_indices_combo_mismatch", "flavor jet collection changed")
    indices = expected_indices(assignment)
    explicit = {
        "W": [int(root_row["idx_W1"]), int(root_row["idx_W2"])],
        "top": [int(root_row["idx_bhad"]), int(root_row["idx_blep"])],
        "H": [int(root_row["idx_H1"]), int(root_row["idx_H2"])],
    }
    if explicit != indices:
        raise hard("explicit_indices_combo_mismatch", f"{explicit} != {indices}")
    flattened = indices["W"] + indices["top"] + indices["H"]
    if sorted(flattened) != list(range(6)):
        raise hard("selected_indices_invalid")
    return {
        **dict(selected_row),
        "selected": indices,
        "best_combo_id": combo,
    }


def load_candidates(root_path: Path, expected_hash: str, source_rows: list[dict[str, Any]], rerank: Any) -> dict[int, dict[str, Any]]:
    if sha256(root_path) != expected_hash:
        raise hard("source_file_hash_mismatch", str(root_path))
    handle = rerank.ROOT.TFile.Open(str(root_path))
    if not handle or handle.IsZombie():
        raise hard("root_open_or_tree_failure", str(root_path))
    try:
        tree = handle.Get("TTHSemiLepKinFit")
        if tree is None:
            raise hard("root_open_or_tree_failure", "missing TTHSemiLepKinFit")
        branches = rerank.branch_names(tree)
        missing = sorted(REQUIRED_ROOT_BRANCHES - branches)
        if missing:
            raise hard("root_required_branch_missing", str(missing))
        wanted = {row["local_index"]: row for row in source_rows}
        found: dict[int, dict[str, Any]] = {}
        for entry in tree:
            event_index = int(entry.event_index)
            if event_index not in wanted:
                continue
            if event_index in found:
                raise hard("root_best_row_duplicate", str(event_index))
            root_row = {
                name: getattr(entry, name)
                for name in REQUIRED_ROOT_BRANCHES
            }
            combo = int(wanted[event_index]["kinfit_signed_combo_id"])
            assignment = rerank.ASSIGNMENT_BY_ID.get(combo)
            if assignment is None:
                raise hard("best_combo_mismatch", f"unknown combo {combo}")
            found[event_index] = validate_candidate_row(root_row, wanted[event_index], assignment)
        if set(found) != set(wanted):
            missing_indices = sorted(set(wanted) - set(found))
            raise hard("root_best_row_missing", str(missing_indices[:10]))
        return found
    finally:
        handle.Close()


def event_identity(event: Any) -> tuple[int, int]:
    return int(event.getRunNumber()), int(event.getEventNumber())


def evaluate_event(event: Any, candidate: Mapping[str, Any], helper: Any, UTIL: Any) -> dict[str, Any]:
    required = {name: helper.get_collection(event, collection) for name, collection in COLLECTIONS.items()}
    missing = sorted(COLLECTIONS[name] for name, collection in required.items() if collection is None)
    if missing:
        return {"status": "unresolved", "reason": "missing_collections:" + ",".join(missing)}

    fit_infos = helper.build_jet_pfo_infos(required["fit"])
    refined_infos = helper.build_jet_pfo_infos(required["refined"])
    bridge = helper.build_collection_bridge(fit_infos, refined_infos, BRIDGE_MINIMUM_DICE)
    diagnostic: dict[str, Any] = {
        "bridge": {
            "status": bridge["status"],
            "reason": bridge["reason"],
            "mapping": {str(key): int(value) for key, value in bridge.get("mapping", {}).items()},
            "dice": {str(key): float(value) for key, value in bridge.get("dice", {}).items()},
            "minimum_dice": float(bridge.get("minimum_dice", 0.0)),
        }
    }
    if bridge["status"] != "evaluable":
        return {"status": "unresolved", "reason": "collection_bridge:" + bridge["reason"], **diagnostic}

    selected = {
        name: [int(bridge["mapping"][index]) for index in candidate["selected"][name]]
        for name in ("W", "top", "H")
    }
    diagnostic["selected_refined"] = selected
    truejet_navigator = UTIL.LCRelationNavigator(required["truejet_link"])
    direct_b = helper.build_direct_b_truejet_infos(required["truejets"], truejet_navigator)
    diagnostic["direct_b_truejet_multiplicity"] = len(direct_b)
    top_match = helper.match_reco_to_top_truejets(refined_infos, direct_b, TOP_MINIMUM_DICE)
    diagnostic["top_match"] = {
        "status": top_match["status"],
        "reason": top_match["reason"],
        "indices": sorted(int(index) for index in top_match.get("matches", {})),
    }
    if top_match["status"] != "evaluable":
        return {"status": "unresolved", "reason": top_match["reason"], **diagnostic}

    top_indices = sorted(int(index) for index in top_match["matches"])
    seed_map, seed_counts = helper.build_seed_groups(event, COLLECTIONS["mc"])
    diagnostic["seed_counts"] = {str(key): int(value) for key, value in seed_counts.items()}
    valid_seeds, seed_reason = helper.validate_seed_counts(seed_counts)
    if not valid_seeds:
        return {"status": "unresolved", "reason": seed_reason, **diagnostic}
    if len(top_indices) != 2:
        return {"status": "unresolved", "reason": f"top_pair_multiplicity_{len(top_indices)}", **diagnostic}

    recomc_navigator = UTIL.LCRelationNavigator(required["recomc_link"])
    relation_counters: Counter = Counter()
    ancestry_cache: dict[int, tuple[set[str], bool]] = {}
    origins = [
        helper.analyze_jet_origin(info["object"], recomc_navigator, seed_map, relation_counters, ancestry_cache)["truth_origin_local"]
        for info in refined_infos
    ]
    higgs_indices = [index for index, origin in enumerate(origins) if origin == "Hbb"]
    diagnostic["origins"] = origins
    diagnostic["higgs_indices"] = higgs_indices
    diagnostic["relation_counters"] = {str(key): int(value) for key, value in relation_counters.items()}
    if len(higgs_indices) != 2:
        return {"status": "unresolved", "reason": f"higgs_pair_multiplicity_{len(higgs_indices)}", **diagnostic}
    partition = helper.build_three_pair_truth_partition(top_indices, higgs_indices, range(6))
    diagnostic["truth_partition"] = {
        "status": partition["status"],
        "reason": partition["reason"],
        "pairs": {
            name: sorted(int(value) for value in pair)
            for name, pair in partition.get("pairs", {}).items()
        },
    }
    if partition["status"] != "evaluable":
        return {"status": "unresolved", "reason": partition["reason"], **diagnostic}
    comparison = helper.three_pair_assignment_flags(
        selected["W"], selected["top"], selected["H"], partition["pairs"]
    )
    if comparison["status"] != "evaluable":
        return {"status": "unresolved", "reason": "assignment_flags:" + comparison["reason"], **diagnostic}
    flags = validate_flags(comparison["flags"])
    return {"status": "evaluable", "reason": "", "flags": flags, **diagnostic}


def open_lcio(path: Path, IOIMPL: Any):
    reader = IOIMPL.LCFactory.getInstance().createLCReader()
    reader.open(str(path))
    return reader


def compare_smoke_source(
    source_id: str,
    original_lcio: Path,
    filtered_lcio: Path,
    mapping: list[dict[str, Any]],
    candidates: Mapping[int, Mapping[str, Any]],
    helper: Any,
    IOIMPL: Any,
    UTIL: Any,
    count: int,
) -> list[dict[str, Any]]:
    chosen = mapping[:count]
    original_results: dict[int, dict[str, Any]] = {}
    original = open_lcio(original_lcio, IOIMPL)
    wanted = {int(row["original_local_index"]): row for row in chosen}
    try:
        local_index = 0
        while local_index <= max(wanted):
            event = original.readNextEvent()
            if not bool(event):
                raise hard("filtered_count_or_order_mismatch", f"{source_id}: original LCIO ended during smoke")
            if local_index in wanted:
                row = wanted[local_index]
                if event_identity(event) != (row["run_number"], row["event_number"]):
                    raise hard("lcio_key_mismatch", f"{source_id}: original smoke")
                original_results[local_index] = evaluate_event(
                    event, candidates[local_index], helper, UTIL
                )
            local_index += 1
    finally:
        original.close()

    filtered = open_lcio(filtered_lcio, IOIMPL)
    rows = []
    try:
        for filtered_index, row in enumerate(chosen):
            event = filtered.readNextEvent()
            if not bool(event):
                raise hard("filtered_count_or_order_mismatch", f"{source_id}: filtered smoke ended")
            if filtered_index != row["filtered_local_index"]:
                raise hard("filtered_count_or_order_mismatch", f"{source_id}: smoke index")
            if event_identity(event) != (row["run_number"], row["event_number"]):
                raise hard("lcio_key_mismatch", f"{source_id}: filtered smoke")
            original_index = int(row["original_local_index"])
            filtered_result = evaluate_event(event, candidates[original_index], helper, UTIL)
            if filtered_result != original_results[original_index]:
                raise hard(
                    "smoke_original_filtered_mismatch",
                    f"{source_id}:{original_index}",
                )
            rows.append(
                {
                    "source_file_id": source_id,
                    "original_local_index": original_index,
                    "filtered_local_index": filtered_index,
                    "run_number": row["run_number"],
                    "event_number": row["event_number"],
                    "result": filtered_result,
                }
            )
    finally:
        filtered.close()
    return rows


def update_diagnostics(diagnostics: Counter, result: Mapping[str, Any]) -> None:
    if "direct_b_truejet_multiplicity" in result:
        diagnostics[f"direct_b_truejet_multiplicity:{int(result['direct_b_truejet_multiplicity'])}"] += 1
    bridge = result.get("bridge", {})
    if bridge:
        diagnostics[f"bridge_status:{bridge.get('status', '')}:{bridge.get('reason', '')}"] += 1
        diagnostics[f"bridge_minimum_dice_bin:{float(bridge.get('minimum_dice', 0.0)):.3f}"] += 1
    seed_counts = result.get("seed_counts", {})
    for name in ("Hbb_seed_partons", "topbb_seed_partons", "Whad_seed_partons"):
        diagnostics[f"seed_count:{name}:{int(seed_counts.get(name, -1))}"] += 1
    top_match = result.get("top_match", {})
    if top_match:
        diagnostics[f"top_pair_multiplicity:{len(top_match.get('indices', []))}"] += 1
    if "higgs_indices" in result:
        diagnostics[f"higgs_pair_multiplicity:{len(result['higgs_indices'])}"] += 1
    for name, value in result.get("relation_counters", {}).items():
        diagnostics[f"relation_counter:{name}"] += int(value)


def analyze_filtered_source(
    source_id: str,
    filtered_lcio: Path,
    mapping: list[dict[str, Any]],
    candidates: Mapping[int, Mapping[str, Any]],
    helper: Any,
    IOIMPL: Any,
    UTIL: Any,
) -> tuple[Counter, Counter, Counter]:
    counts: Counter = Counter(base=len(mapping))
    reasons: Counter = Counter()
    diagnostics: Counter = Counter()
    reader = open_lcio(filtered_lcio, IOIMPL)
    try:
        for filtered_index, row in enumerate(mapping):
            event = reader.readNextEvent()
            if not bool(event):
                raise hard("filtered_count_or_order_mismatch", f"{source_id}: ended at {filtered_index}")
            if filtered_index != row["filtered_local_index"]:
                raise hard("filtered_count_or_order_mismatch", f"{source_id}: index drift")
            if event_identity(event) != (row["run_number"], row["event_number"]):
                raise hard("lcio_key_mismatch", f"{source_id}:{filtered_index}")
            original_index = int(row["original_local_index"])
            result = evaluate_event(event, candidates[original_index], helper, UTIL)
            update_diagnostics(diagnostics, result)
            if result["status"] == "evaluable":
                counts["evaluable"] += 1
                for name, value in result["flags"].items():
                    counts[f"{name}_correct"] += int(value)
            else:
                reasons[result["reason"]] += 1
        extra = reader.readNextEvent()
        if bool(extra):
                raise hard("filtered_count_or_order_mismatch", f"{source_id}: extra events")
    finally:
        reader.close()
    if counts["base"] != counts["evaluable"] + sum(reasons.values()):
        raise hard("filtered_count_or_order_mismatch", f"{source_id}: exclusive closure")
    return counts, reasons, diagnostics


def aggregate(per_source: Mapping[str, tuple[Counter, Counter, Counter]]) -> tuple[Counter, Counter, Counter]:
    counts: Counter = Counter()
    reasons: Counter = Counter()
    diagnostics: Counter = Counter()
    for source_counts, source_reasons, source_diagnostics in per_source.values():
        counts.update(source_counts)
        reasons.update(source_reasons)
        diagnostics.update(source_diagnostics)
    if counts["base"] != BASE_DENOMINATOR:
        raise hard("selected_count_mismatch", "formal base denominator drift")
    if counts["base"] != counts["evaluable"] + sum(reasons.values()):
        raise hard("filtered_count_or_order_mismatch", "formal exclusive truth-result closure")
    if counts["all_correct"] > min(
        counts["W_correct"], counts["top_correct"], counts["H_correct"]
    ):
        raise hard("unexpected_exception", "all-correct numerator is not W-and-top-and-H")
    if any(counts[f"{name}_correct"] > counts["evaluable"] for name in ("W", "top", "H", "all")):
        raise hard("unexpected_exception", "accuracy numerator exceeds denominator")
    return counts, reasons, diagnostics


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else ["name", "count"]
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def render_plot(metrics: dict[str, Any], output_png: Path, output_pdf: Path) -> None:
    import matplotlib.pyplot as plt

    labels = ["W", "top", "H", "all"]
    values = [metrics[f"A_{name}"] for name in labels]
    fig, ax = plt.subplots(figsize=(9.2, 6.2), dpi=180)
    bars = ax.bar(labels, values, color=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"])
    ax.bar_label(bars, fmt="%.3f", fontsize=12, padding=4)
    ax.set_ylim(0.0, max(0.9, max(values) + 0.08))
    ax.set_ylabel("assignment accuracy")
    if metrics["coverage"] < 0.95:
        ax.set_title(
            f"CONDITIONAL CROSS-GENERATOR DIAGNOSTIC — coverage {metrics['coverage']:.2%} (<95%)",
            fontsize=14,
            weight="bold",
        )
    else:
        ax.set_title("Cross-generator truth diagnostic", fontsize=15, weight="bold")
    ax.text(
        0.5,
        1.01,
        (
            "Whizard eL.pR frozen common4730; q_reco minimize; PHYSSIM truth on "
            f"RefinedJets6 via Dice >= 0.95 bridge\nbase={metrics['selection_base_denominator']}, "
            f"evaluable={metrics['evaluable_denominator']}, coverage={metrics['coverage']:.2%}; "
            "base historically conditioned by Whizard six-positive-Dice selection"
        ),
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=9,
    )
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_png, bbox_inches="tight")
    fig.savefig(output_pdf, bbox_inches="tight")
    plt.close(fig)


def build_inputs(args: argparse.Namespace, rerank: Any):
    selected_path = args.selected_common_csv.resolve(strict=True)
    _rows, grouped = read_selected(selected_path, args.expected_selected_common_sha256)
    source_path = args.sources_json.resolve(strict=True)
    if sha256(source_path) != args.expected_sources_json_sha256:
        raise hard("sources_json_hash_mismatch")
    source_payload = json.loads(source_path.read_text(encoding="utf-8"))
    filtered_path = args.filtered_manifest.resolve(strict=True)
    if sha256(filtered_path) != args.expected_filtered_manifest_sha256:
        raise hard("filtered_manifest_hash_mismatch")
    filtered_payload = json.loads(filtered_path.read_text(encoding="utf-8"))
    sources = {row["source_file_id"]: row for row in source_payload["sources"]}
    filtered = {row["source_file_id"]: row for row in filtered_payload["sources"]}
    if set(sources) != set(EXPECTED_PER_SOURCE) or set(filtered) != set(EXPECTED_PER_SOURCE):
        raise hard("selected_per_source_mismatch", "source identities")
    built = {}
    for source_id in EXPECTED_PER_SOURCE:
        source = sources[source_id]
        replay = filtered[source_id]
        original_lcio = Path(source["lcio"]).resolve(strict=True)
        filtered_lcio = Path(replay["filtered_lcio"]).resolve(strict=True)
        if str(original_lcio) != str(Path(replay["input_lcio"]).resolve(strict=True)):
            raise hard("mapping_key_mismatch", f"{source_id}: original LCIO differs")
        if sha256(original_lcio) != replay["input_sha256"]:
            raise hard("source_file_hash_mismatch", f"{source_id}: original LCIO")
        expected_filtered_hash = replay.get("filtered_lcio_sha256", replay.get("filtered_sha256"))
        expected_mapping_hash = replay.get("mapping_csv_sha256", replay.get("mapping_sha256"))
        if sha256(filtered_lcio) != expected_filtered_hash:
            raise hard("source_file_hash_mismatch", f"{source_id}: filtered LCIO")
        mapping = read_mapping(
            Path(replay["mapping_csv"]).resolve(strict=True),
            expected_mapping_hash,
            grouped[source_id],
        )
        candidates = load_candidates(
            Path(source["root"]).resolve(strict=True),
            source["root_sha256"],
            grouped[source_id],
            rerank,
        )
        built[source_id] = {
            "original_lcio": original_lcio,
            "filtered_lcio": filtered_lcio,
            "mapping": mapping,
            "candidates": candidates,
            "source": source,
            "filtered": replay,
        }
    return selected_path, built


def create_provenance(output_dir: Path, test_path: Path | None) -> list[Path]:
    provenance = output_dir / "provenance"
    provenance.mkdir()
    copied = []
    for source in (Path(__file__).resolve(), test_path.resolve(strict=True) if test_path else None):
        if source is None:
            continue
        target = provenance / source.name
        shutil.copy2(source, target)
        copied.append(target)
    return copied


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2], text=True
        ).strip()
    except Exception:
        return "unavailable"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("smoke", "formal"), required=True)
    parser.add_argument("--selected-common-csv", type=Path, required=True)
    parser.add_argument("--expected-selected-common-sha256", required=True)
    parser.add_argument("--sources-json", type=Path, required=True)
    parser.add_argument("--expected-sources-json-sha256", required=True)
    parser.add_argument("--filtered-manifest", type=Path, required=True)
    parser.add_argument("--expected-filtered-manifest-sha256", required=True)
    parser.add_argument("--truth-helper", type=Path, required=True)
    parser.add_argument("--expected-truth-helper-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--test-file", type=Path)
    parser.add_argument("--smoke-per-source", type=int, default=5)
    parser.add_argument("--compare-original-filtered", action="store_true")
    args = parser.parse_args()
    if args.output_dir.exists() or args.output_dir.is_symlink():
        raise RuntimeError(f"refusing to reuse output directory: {args.output_dir}")
    frozen_expectations = (
        (args.expected_selected_common_sha256, DEFAULT_SELECTED_SHA256, "selected_csv_hash_mismatch"),
        (args.expected_sources_json_sha256, DEFAULT_SOURCES_SHA256, "sources_json_hash_mismatch"),
        (args.expected_filtered_manifest_sha256, DEFAULT_FILTERED_MANIFEST_SHA256, "filtered_manifest_hash_mismatch"),
        (args.expected_truth_helper_sha256, DEFAULT_TRUTH_HELPER_SHA256, "helper_hash_mismatch"),
    )
    for supplied, frozen, code in frozen_expectations:
        if supplied != frozen:
            raise hard(code, "expected hash argument differs from frozen contract")
    if args.mode == "smoke" and not args.compare_original_filtered:
        raise hard("smoke_original_filtered_mismatch", "--compare-original-filtered required")
    if args.mode == "formal" and args.compare_original_filtered:
        raise hard("unexpected_exception", "formal mode rejects smoke-only comparison option")
    helper_path = args.truth_helper.resolve(strict=True)
    if sha256(helper_path) != args.expected_truth_helper_sha256:
        raise hard("helper_hash_mismatch")
    legacy_rerank = Path(__file__).resolve().parents[2] / "reco_performance_study/legacy/rerank_tth_semilep_kinfit_with_flavor.py"
    rerank = load_module("frozen_whizard_rerank", legacy_rerank.resolve(strict=True))
    helper = load_module("frozen_physsim_bjet_truth", helper_path)
    try:
        import pyLCIO
        from pyLCIO import IOIMPL, UTIL
        lcio_module_path = str(Path(pyLCIO.__file__).resolve())
    except Exception:
        import lcio  # noqa: F401
        from lcio import IOIMPL, UTIL
        lcio_module_path = str(Path(lcio.__file__).resolve())

    started = time.monotonic()
    selected_path, inputs = build_inputs(args, rerank)
    if args.mode == "smoke":
        if args.smoke_per_source < 1 or args.smoke_per_source > 5:
            raise hard("unexpected_exception", "smoke-per-source must be in [1,5]")
        rows = []
        for source_id, data in inputs.items():
            rows.extend(
                compare_smoke_source(
                    source_id,
                    data["original_lcio"],
                    data["filtered_lcio"],
                    data["mapping"],
                    data["candidates"],
                    helper,
                    IOIMPL,
                    UTIL,
                    args.smoke_per_source,
                )
            )
        if len(rows) != args.smoke_per_source * 4:
            raise hard("filtered_count_or_order_mismatch", "smoke count")
        args.output_dir.mkdir(parents=True)
        smoke_csv = args.output_dir / "smoke_events.csv"
        smoke_rows = []
        for row in rows:
            original = row["result"]
            filtered = row["result"]
            smoke_rows.append(
                {
                    "source_file_id": row["source_file_id"],
                    "original_local_index": row["original_local_index"],
                    "filtered_local_index": row["filtered_local_index"],
                    "run_number": row["run_number"],
                    "event_number": row["event_number"],
                    "best_combo_id": inputs[row["source_file_id"]]["candidates"][row["original_local_index"]]["best_combo_id"],
                    "selected_W": json.dumps(inputs[row["source_file_id"]]["candidates"][row["original_local_index"]]["selected"]["W"]),
                    "selected_top": json.dumps(inputs[row["source_file_id"]]["candidates"][row["original_local_index"]]["selected"]["top"]),
                    "selected_H": json.dumps(inputs[row["source_file_id"]]["candidates"][row["original_local_index"]]["selected"]["H"]),
                    "original_status": original["status"],
                    "original_reason": original["reason"],
                    "filtered_status": filtered["status"],
                    "filtered_reason": filtered["reason"],
                    "original_bridge_mapping": json.dumps(original.get("bridge", {}).get("mapping", {}), sort_keys=True),
                    "filtered_bridge_mapping": json.dumps(filtered.get("bridge", {}).get("mapping", {}), sort_keys=True),
                    "original_truth_pairs": json.dumps(original.get("truth_partition", {}).get("pairs", {}), sort_keys=True),
                    "filtered_truth_pairs": json.dumps(filtered.get("truth_partition", {}).get("pairs", {}), sort_keys=True),
                    "original_flags": json.dumps(original.get("flags", {}), sort_keys=True),
                    "filtered_flags": json.dumps(filtered.get("flags", {}), sort_keys=True),
                    "identical": 1,
                }
            )
        write_csv(smoke_csv, smoke_rows)
        output = args.output_dir / "smoke_summary.json"
        output.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "passed",
                    "events": len(rows),
                    "per_source": args.smoke_per_source,
                    "comparison": "identical status/reason/bridge/truth partition/flags",
                    "integrity_failures": [],
                    "smoke_events_csv": {"path": str(smoke_csv.resolve()), "sha256": sha256(smoke_csv)},
                    "elapsed_seconds": time.monotonic() - started,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"status": "passed", "events": len(rows), "output": str(output)}))
        return 0

    per_source: dict[str, tuple[Counter, Counter, Counter]] = {}
    for source_id, data in inputs.items():
        per_source[source_id] = analyze_filtered_source(
            source_id,
            data["filtered_lcio"],
            data["mapping"],
            data["candidates"],
            helper,
            IOIMPL,
            UTIL,
        )
    totals, reasons, diagnostics = aggregate(per_source)
    evaluable = int(totals["evaluable"])
    coverage = evaluable / BASE_DENOMINATOR
    metrics = {
        "method": METHOD,
        "internal_mode": INTERNAL_MODE,
        "candidate_pool": "signed-flavor-preselected Top10",
        "selected_stage": SELECTED_STAGE,
        "truth_definition": TRUTH_DEFINITION,
        "status": diagnostic_status(evaluable, coverage),
        "selection_base_denominator": BASE_DENOMINATOR,
        "evaluable_denominator": evaluable,
        "coverage": coverage,
        **{
            f"{name}_correct": int(totals[f"{name}_correct"])
            for name in ("W", "top", "H", "all")
        },
        **{
            f"A_{name}": (int(totals[f"{name}_correct"]) / evaluable if evaluable else None)
            for name in ("W", "top", "H", "all")
        },
    }
    args.output_dir.mkdir(parents=True)
    provenance_paths = create_provenance(args.output_dir, args.test_file)
    accuracy_csv = args.output_dir / "assignment_accuracy.csv"
    rejection_csv = args.output_dir / "rejection_summary.csv"
    summary_json = args.output_dir / "summary.json"
    manifest_json = args.output_dir / "manifest.json"
    write_csv(accuracy_csv, [metrics])
    rejection_rows = []
    for source_id, (_counts, source_reasons, source_diagnostics) in per_source.items():
        rejection_rows.extend(
            {
                "source_file_id": source_id,
                "category": "truth_unresolved_exclusive",
                "reason": reason,
                "count": int(count),
            }
            for reason, count in sorted(source_reasons.items())
        )
        rejection_rows.extend(
            {
                "source_file_id": source_id,
                "category": "diagnostic_nonexclusive",
                "reason": reason,
                "count": int(count),
            }
            for reason, count in sorted(source_diagnostics.items())
        )
    rejection_rows.extend(
        {
            "source_file_id": "total",
            "category": "truth_unresolved_exclusive",
            "reason": reason,
            "count": int(count),
        }
        for reason, count in sorted(reasons.items())
    )
    rejection_rows.extend(
        {
            "source_file_id": "total",
            "category": "diagnostic_nonexclusive",
            "reason": reason,
            "count": int(count),
        }
        for reason, count in sorted(diagnostics.items())
    )
    write_csv(rejection_csv, rejection_rows)
    output_paths = [accuracy_csv, rejection_csv]
    if should_plot(evaluable):
        png = args.output_dir / "assignment_accuracy_physsim_truth_qreco.png"
        pdf = args.output_dir / "assignment_accuracy_physsim_truth_qreco.pdf"
        render_plot(metrics, png, pdf)
        output_paths.extend((png, pdf))
    elapsed = time.monotonic() - started
    summary = {
        "schema_version": 1,
        "status": metrics["status"],
        "method": {
            "display": METHOD,
            "internal_mode": INTERNAL_MODE,
            "candidate_pool": metrics["candidate_pool"],
            "selected_stage": SELECTED_STAGE,
        },
        "inputs": {
            "selected_common_csv": {"path": str(selected_path), "sha256": sha256(selected_path)},
            "sources_json": {"path": str(args.sources_json.resolve()), "sha256": sha256(args.sources_json)},
            "filtered_manifest": {"path": str(args.filtered_manifest.resolve()), "sha256": sha256(args.filtered_manifest)},
            "truth_helper": {"path": str(helper_path), "sha256": sha256(helper_path)},
        },
        "selection_base_denominator": BASE_DENOMINATOR,
        "evaluable_denominator": evaluable,
        "coverage": coverage,
        "numerators": {name: int(totals[f"{name}_correct"]) for name in ("W", "top", "H", "all")},
        "accuracies": {name: metrics[f"A_{name}"] for name in ("W", "top", "H", "all")},
        "truth_unresolved_exclusive": dict(sorted(reasons.items())),
        "diagnostic_nonexclusive": dict(sorted(diagnostics.items())),
        "integrity_failures": [],
        "per_source": {
            source_id: {
                "counts": dict(counts),
                "exclusive_rejections": dict(sorted(source_reasons.items())),
                "diagnostic_nonexclusive": dict(sorted(source_diagnostics.items())),
            }
            for source_id, (counts, source_reasons, source_diagnostics) in per_source.items()
        },
        "closure": f"{BASE_DENOMINATOR} = {evaluable} evaluable + {sum(reasons.values())} truth-unresolved",
        "physics_contract": {
            "interpretation": "CONDITIONAL CROSS-GENERATOR DIAGNOSTIC; no assignment-performance claim" if coverage < 0.95 else "Cross-generator truth diagnostic on the historically conditioned base",
            "truth_definition": TRUTH_DEFINITION,
            "historical_conditioning": "common4730 was preconditioned on the old Whizard all-six-positive-Dice gate; that gate is not reapplied",
        },
        "elapsed_seconds": elapsed,
    }
    summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_paths.append(summary_json)
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": summary["status"],
        "contract": {
            "sample": "Whizard eL.pR frozen common4730",
            "event_key": ["source_file_id", "local_index", "run_number", "event_number"],
            "candidate": METHOD,
            "candidate_selection": "accepted=1 && fit_success=1 && best_combo_id==kinfit_signed_combo_id",
            "fit_collection": COLLECTIONS["fit"],
            "truth_collection": COLLECTIONS["refined"],
            "bridge_minimum_dice": BRIDGE_MINIMUM_DICE,
            "top_minimum_dice": TOP_MINIMUM_DICE,
            "base_conditioning": "historical Whizard all-six-positive-Dice common-event selection only; not reapplied in PHYSSIM truth",
        },
        "inputs": {
            "selected_common_csv": {"path": str(selected_path), "sha256": sha256(selected_path)},
            "sources_json": {"path": str(args.sources_json.resolve()), "sha256": sha256(args.sources_json)},
            "filtered_manifest": {"path": str(args.filtered_manifest.resolve()), "sha256": sha256(args.filtered_manifest)},
            "physsim_truth_module": {"path": str(helper_path), "sha256": sha256(helper_path)},
            "legacy_rerank": {"path": str(legacy_rerank.resolve()), "sha256": sha256(legacy_rerank)},
            "sources": [
                {
                    "source_file_id": source_id,
                    "authoritative_root": str(data["source"]["root"]),
                    "authoritative_root_sha256": data["source"]["root_sha256"],
                    "original_lcio": str(data["original_lcio"]),
                    "filtered_lcio": str(data["filtered_lcio"]),
                    "filtered_lcio_sha256": data["filtered"].get("filtered_lcio_sha256", data["filtered"].get("filtered_sha256")),
                    "mapping_csv": data["filtered"]["mapping_csv"],
                    "mapping_csv_sha256": data["filtered"].get("mapping_csv_sha256", data["filtered"].get("mapping_sha256")),
                }
                for source_id, data in inputs.items()
            ],
        },
        "command": [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
        "cwd": str(Path.cwd()),
        "git_commit": git_commit(),
        "runtime": {
            "python_executable": sys.executable,
            "python_version": sys.version,
            "root_version": str(rerank.ROOT.gROOT.GetVersion()),
            "root_module": str(getattr(rerank.ROOT, "__file__", "")),
            "lcio_module": lcio_module_path,
        },
        "elapsed_seconds": elapsed,
        "outputs": {},
    }
    for path in output_paths + provenance_paths:
        manifest["outputs"][path.relative_to(args.output_dir).as_posix()] = {
            "path": str(path.resolve()),
            "sha256": sha256(path),
        }
    manifest_json.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": summary["status"], "metrics": metrics, "output_dir": str(args.output_dir)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except IntegrityError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
    except Exception as error:
        print(f"unexpected_exception: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(3)
