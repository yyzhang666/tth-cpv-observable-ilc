#!/usr/bin/env python3
"""Evaluate frozen Whizard common4730 q_reco rows with a hybrid truth label.

Only the top-b TrueJet selection is supplied by the pinned Whizard ancestry
classifier.  The collection bridge, top matching, Hbb labels, W complement,
and assignment flags are supplied by the pinned PHYSSIM helper unchanged.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


BASE_REPORT = Path(__file__).with_name("report_whizard_physsim_truth_assignment.py")
PHYSSIM_SHA256 = "0d058caa16ab8e1f560c8cc75d817c5b4ec29a67cb5edd720d0472fb54d9fd33"
WHIZARD_TRUTH_SHA256 = "c117466ccd9cd8dca2ff90686f5c937ca32300367c75da32614eee7e04b128f0"
CHI2_RECO_SHA256 = "e7c9bbca72afef927ce99786855ec75b651a38c77805ebd9c5490130ecc7d174"
METHOD = "q_reco minimize [signed-flavor-preselected Top10]"
TRUTH_DEFINITION = (
    "Whizard origin-aware top-b selection + fixed PHYSSIM Hbb/W truth; "
    "not pure PHYSSIM truth and not canonical Whizard truth"
)
COLLECTIONS = {
    "fit": "OutputErrorFlowJets6",
    "refined": "RefinedJets6",
    "truejets": "TrueJets",
    "truejet_link": "TrueJetPFOLink",
    "truejet_mc_link": "TrueJetMCParticleLink",
    "recomc_link": "RecoMCTruthLink",
    "mc": "MCParticlesSkimmed",
}
BRIDGE_MINIMUM_DICE = 0.95
TOP_MINIMUM_DICE = 0.2


def load_local_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load_local_module("whizard_physsim_truth_frozen_harness", BASE_REPORT)
IntegrityError = BASE.IntegrityError
hard = BASE.hard
sha256 = BASE.sha256


def verify_module(module: Any, expected_path: Path, expected_hash: str, code: str) -> None:
    observed_path = Path(module.__file__).resolve()
    if observed_path != expected_path.resolve():
        raise hard("module_binding_mismatch", f"{observed_path} != {expected_path.resolve()}")
    observed_hash = sha256(observed_path)
    if observed_hash != expected_hash:
        raise hard(code, f"{observed_path}: {observed_hash} != {expected_hash}")


def load_truth_modules(
    physsim_path: Path,
    whizard_truth_path: Path,
    chi2_reco_path: Path,
) -> tuple[Any, Any, Any]:
    verify_path_hashes = (
        (physsim_path, PHYSSIM_SHA256, "helper_hash_mismatch"),
        (whizard_truth_path, WHIZARD_TRUTH_SHA256, "whizard_truth_hash_mismatch"),
        (chi2_reco_path, CHI2_RECO_SHA256, "chi2_reco_hash_mismatch"),
    )
    for path, expected, code in verify_path_hashes:
        if sha256(path.resolve(strict=True)) != expected:
            raise hard(code, str(path))

    previous = sys.modules.get("chi2_reco")
    chi2_reco = load_local_module("chi2_reco", chi2_reco_path.resolve(strict=True))
    sys.modules["chi2_reco"] = chi2_reco
    try:
        whizard_truth = load_local_module(
            "frozen_whizard_truth_matching", whizard_truth_path.resolve(strict=True)
        )
    except Exception:
        if previous is None:
            sys.modules.pop("chi2_reco", None)
        else:
            sys.modules["chi2_reco"] = previous
        raise
    physsim = load_local_module("frozen_physsim_bjet_truth_hybrid", physsim_path.resolve(strict=True))
    verify_module(chi2_reco, chi2_reco_path, CHI2_RECO_SHA256, "chi2_reco_hash_mismatch")
    verify_module(whizard_truth, whizard_truth_path, WHIZARD_TRUTH_SHA256, "whizard_truth_hash_mismatch")
    verify_module(physsim, physsim_path, PHYSSIM_SHA256, "helper_hash_mismatch")
    if whizard_truth.chi2_reco is not chi2_reco:
        raise hard("module_binding_mismatch", "truth_matching did not bind pinned chi2_reco")
    return physsim, whizard_truth, chi2_reco


def select_origin_aware_top_truejets(true_map: Mapping[int, Mapping[str, Any]]) -> dict[str, Any]:
    role_ids: dict[str, list[int]] = {}
    for truejet_id, info in true_map.items():
        role_ids.setdefault(str(info.get("role", "other")), []).append(int(truejet_id))
    for ids in role_ids.values():
        ids.sort()
    had = role_ids.get("top_had_b", [])
    lep = role_ids.get("top_lep_b", [])
    if len(had) != 1 or len(lep) != 1:
        return {
            "status": "unresolved",
            "reason": f"top_role_multiplicity_had_{len(had)}_lep_{len(lep)}",
            "role_ids": role_ids,
            "selected_ids": [],
            "selected_infos": [],
        }
    selected_ids = [had[0], lep[0]]
    selected_infos = [dict(true_map[truejet_id]) for truejet_id in selected_ids]
    if any(str(info.get("role")) not in ("top_had_b", "top_lep_b") for info in selected_infos):
        raise hard("unexpected_exception", "H/other TrueJet entered top selector")
    return {
        "status": "evaluable",
        "reason": "",
        "role_ids": role_ids,
        "selected_ids": selected_ids,
        "selected_infos": selected_infos,
    }


def combine_physsim_h_w_truth(
    helper: Any,
    top_indices: list[int],
    higgs_indices: list[int],
    selected: Mapping[str, list[int]],
) -> dict[str, Any]:
    partition = helper.build_three_pair_truth_partition(top_indices, higgs_indices, range(6))
    diagnostic = {
        "truth_partition": {
            "status": partition["status"],
            "reason": partition["reason"],
            "pairs": {
                name: sorted(int(value) for value in pair)
                for name, pair in partition.get("pairs", {}).items()
            },
        }
    }
    if partition["status"] != "evaluable":
        return {"status": "unresolved", "reason": partition["reason"], **diagnostic}
    comparison = helper.three_pair_assignment_flags(
        selected["W"], selected["top"], selected["H"], partition["pairs"]
    )
    if comparison["status"] != "evaluable":
        return {
            "status": "unresolved",
            "reason": "assignment_flags:" + comparison["reason"],
            **diagnostic,
        }
    return {
        "status": "evaluable",
        "reason": "",
        "flags": BASE.validate_flags(comparison["flags"]),
        **diagnostic,
    }


def evaluate_event(
    event: Any,
    candidate: Mapping[str, Any],
    helper: Any,
    whizard_truth: Any,
    chi2_reco: Any,
    UTIL: Any,
) -> dict[str, Any]:
    required = {name: helper.get_collection(event, collection) for name, collection in COLLECTIONS.items()}
    missing = sorted(COLLECTIONS[name] for name, collection in required.items() if collection is None)
    if missing:
        raise hard("missing_required_collection", ",".join(missing))

    truth_info = chi2_reco.truth_event_info(
        event,
        {"mc_collection": COLLECTIONS["mc"], "allowed_truth_leptons": ["e", "mu"]},
    )
    if truth_info is None:
        return {"status": "unresolved", "reason": "no_valid_whizard_emu_semileptonic_hbb_truth"}

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

    tj_pfo_nav = UTIL.LCRelationNavigator(required["truejet_link"])
    tj_mc_nav = UTIL.LCRelationNavigator(required["truejet_mc_link"])
    quark_truejets = chi2_reco.collect_truejet_quark_jets(required["truejets"])
    true_map = whizard_truth.build_truejet_pfo_map_direct(
        quark_truejets, tj_pfo_nav, tj_mc_nav, truth_info
    )
    direct_b_count = sum(abs(int(item.get("pdg", 0))) == 5 for item in true_map.values())
    top_selection = select_origin_aware_top_truejets(true_map)
    diagnostic.update(
        {
            "direct_b_truejet_multiplicity": direct_b_count,
            "truejet_role_ids": top_selection["role_ids"],
            "selected_top_truejet_object_ids_nonpersistent": top_selection["selected_ids"],
            "selected_top_truejet_stable": [
                {
                    "truejet_index": int(info["truejet_index"]),
                    "direct_pdg": int(info["pdg"]),
                    "role": str(info["role"]),
                }
                for info in top_selection["selected_infos"]
            ],
        }
    )
    if top_selection["status"] != "evaluable":
        return {"status": "unresolved", "reason": top_selection["reason"], **diagnostic}

    top_infos = [
        {
            "index": int(info["truejet_index"]),
            "object": info["truejet"],
            "pdg": int(info["pdg"]),
            "pfo_ids": set(info["pfo_ids"]),
            "energy": float(info["energy"]),
        }
        for info in top_selection["selected_infos"]
    ]
    top_match = helper.match_reco_to_top_truejets(refined_infos, top_infos, TOP_MINIMUM_DICE)
    diagnostic["top_match"] = {
        "status": top_match["status"],
        "reason": top_match["reason"],
        "indices": sorted(int(index) for index in top_match.get("matches", {})),
        "truejet_indices": sorted(
            int(value["truejet_index"]) for value in top_match.get("matches", {}).values()
        ),
        "dice": {
            str(index): float(value["dice"])
            for index, value in sorted(top_match.get("matches", {}).items())
        },
    }
    if top_match["status"] != "evaluable":
        return {"status": "unresolved", "reason": top_match["reason"], **diagnostic}
    top_indices = diagnostic["top_match"]["indices"]
    if len(top_indices) != 2:
        return {"status": "unresolved", "reason": f"top_pair_multiplicity_{len(top_indices)}", **diagnostic}

    seed_map, seed_counts = helper.build_seed_groups(event, COLLECTIONS["mc"])
    diagnostic["seed_counts"] = {str(key): int(value) for key, value in seed_counts.items()}
    valid_seeds, seed_reason = helper.validate_seed_counts(seed_counts)
    if not valid_seeds:
        return {"status": "unresolved", "reason": seed_reason, **diagnostic}
    recomc_nav = UTIL.LCRelationNavigator(required["recomc_link"])
    relation_counters: Counter = Counter()
    ancestry_cache: dict[int, tuple[set[str], bool]] = {}
    origins = [
        helper.analyze_jet_origin(
            info["object"], recomc_nav, seed_map, relation_counters, ancestry_cache
        )["truth_origin_local"]
        for info in refined_infos
    ]
    higgs_indices = [index for index, origin in enumerate(origins) if origin == "Hbb"]
    diagnostic.update(
        {
            "origins": origins,
            "higgs_indices": higgs_indices,
            "relation_counters": {str(key): int(value) for key, value in relation_counters.items()},
        }
    )
    if len(higgs_indices) != 2:
        return {"status": "unresolved", "reason": f"higgs_pair_multiplicity_{len(higgs_indices)}", **diagnostic}
    combined = combine_physsim_h_w_truth(helper, top_indices, higgs_indices, selected)
    return {**combined, **diagnostic, **{k: v for k, v in combined.items() if k != "truth_partition"}}


def smoke_signature(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": result.get("status"),
        "reason": result.get("reason"),
        "bridge": result.get("bridge", {}),
        "selected_top_truejet_stable": result.get("selected_top_truejet_stable", []),
        "top_match": result.get("top_match", {}),
        "higgs_indices": result.get("higgs_indices", []),
        "truth_partition": result.get("truth_partition", {}),
        "flags": result.get("flags", {}),
    }


def compare_smoke_source(
    source_id: str,
    data: Mapping[str, Any],
    helper: Any,
    whizard_truth: Any,
    chi2_reco: Any,
    IOIMPL: Any,
    UTIL: Any,
    count: int,
) -> list[dict[str, Any]]:
    chosen = data["mapping"][:count]
    original_results: dict[int, dict[str, Any]] = {}
    original = BASE.open_lcio(data["original_lcio"], IOIMPL)
    wanted = {int(row["original_local_index"]): row for row in chosen}
    try:
        for local_index in range(max(wanted) + 1):
            event = original.readNextEvent()
            if not bool(event):
                raise hard("filtered_count_or_order_mismatch", f"{source_id}: original smoke ended")
            if local_index not in wanted:
                continue
            row = wanted[local_index]
            if BASE.event_identity(event) != (row["run_number"], row["event_number"]):
                raise hard("lcio_key_mismatch", f"{source_id}: original smoke")
            original_results[local_index] = evaluate_event(
                event, data["candidates"][local_index], helper, whizard_truth, chi2_reco, UTIL
            )
    finally:
        original.close()

    rows = []
    filtered = BASE.open_lcio(data["filtered_lcio"], IOIMPL)
    try:
        for filtered_index, row in enumerate(chosen):
            event = filtered.readNextEvent()
            if not bool(event):
                raise hard("filtered_count_or_order_mismatch", f"{source_id}: filtered smoke ended")
            if filtered_index != int(row["filtered_local_index"]):
                raise hard("filtered_count_or_order_mismatch", f"{source_id}: filtered smoke index")
            if BASE.event_identity(event) != (row["run_number"], row["event_number"]):
                raise hard("lcio_key_mismatch", f"{source_id}: filtered smoke")
            original_index = int(row["original_local_index"])
            result = evaluate_event(
                event, data["candidates"][original_index], helper, whizard_truth, chi2_reco, UTIL
            )
            original_result = original_results[original_index]
            if smoke_signature(result) != smoke_signature(original_result):
                raise hard(
                    "smoke_original_filtered_mismatch",
                    f"{source_id}:{original_index}: original={json.dumps(smoke_signature(original_result), sort_keys=True)} "
                    f"filtered={json.dumps(smoke_signature(result), sort_keys=True)}",
                )
            expected_ids = sorted(
                ids[0]
                for role, ids in result.get("truejet_role_ids", {}).items()
                if role in ("top_had_b", "top_lep_b") and len(ids) == 1
            )
            if sorted(result.get("selected_top_truejet_object_ids_nonpersistent", [])) != expected_ids:
                raise hard("smoke_role_id_mismatch", f"{source_id}:{original_index}")
            rows.append(
                {
                    "source_file_id": source_id,
                    "original_local_index": original_index,
                    "filtered_local_index": filtered_index,
                    "run_number": row["run_number"],
                    "event_number": row["event_number"],
                    "result": result,
                }
            )
    finally:
        filtered.close()
    return rows


def update_diagnostics(diagnostics: Counter, roles: Counter, result: Mapping[str, Any]) -> None:
    if "direct_b_truejet_multiplicity" in result:
        diagnostics[f"direct_b_truejet_multiplicity:{int(result['direct_b_truejet_multiplicity'])}"] += 1
    for role, ids in result.get("truejet_role_ids", {}).items():
        roles[f"{role}:events"] += 1
        roles[f"{role}:truejets"] += len(ids)
        diagnostics[f"role_multiplicity:{role}:{len(ids)}"] += 1
    bridge = result.get("bridge", {})
    if bridge:
        diagnostics[f"bridge_status:{bridge.get('status', '')}:{bridge.get('reason', '')}"] += 1
    if "top_match" in result:
        diagnostics[f"top_pair_multiplicity:{len(result['top_match'].get('indices', []))}"] += 1
    if "higgs_indices" in result:
        diagnostics[f"higgs_pair_multiplicity:{len(result['higgs_indices'])}"] += 1
    for name, value in result.get("relation_counters", {}).items():
        diagnostics[f"relation_counter:{name}"] += int(value)


def analyze_filtered_source(
    source_id: str,
    data: Mapping[str, Any],
    helper: Any,
    whizard_truth: Any,
    chi2_reco: Any,
    IOIMPL: Any,
    UTIL: Any,
) -> tuple[Counter, Counter, Counter, Counter]:
    counts: Counter = Counter(base=len(data["mapping"]))
    reasons: Counter = Counter()
    diagnostics: Counter = Counter()
    roles: Counter = Counter()
    reader = BASE.open_lcio(data["filtered_lcio"], IOIMPL)
    try:
        for filtered_index, row in enumerate(data["mapping"]):
            event = reader.readNextEvent()
            if not bool(event):
                raise hard("filtered_count_or_order_mismatch", f"{source_id}: ended at {filtered_index}")
            if filtered_index != int(row["filtered_local_index"]):
                raise hard("filtered_count_or_order_mismatch", f"{source_id}: index drift")
            if BASE.event_identity(event) != (row["run_number"], row["event_number"]):
                raise hard("lcio_key_mismatch", f"{source_id}:{filtered_index}")
            original_index = int(row["original_local_index"])
            result = evaluate_event(
                event, data["candidates"][original_index], helper, whizard_truth, chi2_reco, UTIL
            )
            update_diagnostics(diagnostics, roles, result)
            if result["status"] == "evaluable":
                counts["evaluable"] += 1
                for name, value in result["flags"].items():
                    counts[f"{name}_correct"] += int(value)
            else:
                reasons[result["reason"]] += 1
        if bool(reader.readNextEvent()):
            raise hard("filtered_count_or_order_mismatch", f"{source_id}: extra events")
    finally:
        reader.close()
    if counts["base"] != counts["evaluable"] + sum(reasons.values()):
        raise hard("filtered_count_or_order_mismatch", f"{source_id}: exclusive closure")
    return counts, reasons, diagnostics, roles


def aggregate(per_source: Mapping[str, tuple[Counter, Counter, Counter, Counter]]):
    counts: Counter = Counter()
    reasons: Counter = Counter()
    diagnostics: Counter = Counter()
    roles: Counter = Counter()
    for source_counts, source_reasons, source_diagnostics, source_roles in per_source.values():
        counts.update(source_counts)
        reasons.update(source_reasons)
        diagnostics.update(source_diagnostics)
        roles.update(source_roles)
    if counts["base"] != BASE.BASE_DENOMINATOR:
        raise hard("selected_count_mismatch", "formal base denominator drift")
    if counts["base"] != counts["evaluable"] + sum(reasons.values()):
        raise hard("filtered_count_or_order_mismatch", "formal exclusive truth-result closure")
    if counts["all_correct"] > min(counts["W_correct"], counts["top_correct"], counts["H_correct"]):
        raise hard("unexpected_exception", "all-correct numerator is not intersection")
    if any(counts[f"{name}_correct"] > counts["evaluable"] for name in ("W", "top", "H", "all")):
        raise hard("unexpected_exception", "accuracy numerator exceeds denominator")
    return counts, reasons, diagnostics, roles


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    BASE.write_csv(path, rows)


def render_plot(metrics: Mapping[str, Any], png: Path, pdf: Path) -> None:
    import matplotlib.pyplot as plt

    labels = ["W", "top", "H", "all"]
    values = [float(metrics[f"A_{name}"]) for name in labels]
    fig, ax = plt.subplots(figsize=(10.0, 6.7), dpi=180)
    bars = ax.bar(labels, values, color=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"])
    ax.bar_label(bars, fmt="%.3f", fontsize=13, padding=4)
    ax.set_ylim(0.0, max(0.9, max(values) + 0.08))
    ax.set_ylabel("assignment accuracy on evaluable hybrid-truth subset")
    title = (
        "CONDITIONAL HYBRID-TRUTH DIAGNOSTIC"
        if metrics["coverage"] < 0.95
        else "HYBRID-TRUTH CROSS-GENERATOR DIAGNOSTIC"
    )
    ax.set_title(title, fontsize=15, weight="bold")
    ax.text(
        0.5,
        1.01,
        (
            "Whizard origin-aware top-b selection + fixed PHYSSIM Hbb/W truth; "
            "not pure PHYSSIM truth and not canonical Whizard truth\n"
            f"q_reco common4730: evaluable={metrics['evaluable_denominator']}/"
            f"{metrics['selection_base_denominator']} ({metrics['coverage']:.2%}); "
            "base historically conditioned by Whizard six-positive-Dice selection"
        ),
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=9,
    )
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(png, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)


def create_provenance(output_dir: Path, test_file: Path | None) -> list[Path]:
    provenance = output_dir / "provenance"
    provenance.mkdir()
    sources = [Path(__file__).resolve(), BASE_REPORT.resolve()]
    if test_file is not None:
        sources.append(test_file.resolve(strict=True))
    copied = []
    for source in sources:
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
    parser.add_argument("--physsim-truth-helper", type=Path, required=True)
    parser.add_argument("--expected-physsim-truth-sha256", required=True)
    parser.add_argument("--whizard-truth-helper", type=Path, required=True)
    parser.add_argument("--expected-whizard-truth-sha256", required=True)
    parser.add_argument("--chi2-reco", type=Path, required=True)
    parser.add_argument("--expected-chi2-reco-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--test-file", type=Path)
    parser.add_argument("--smoke-per-source", type=int, default=5)
    parser.add_argument("--compare-original-filtered", action="store_true")
    args = parser.parse_args()
    if args.output_dir.exists() or args.output_dir.is_symlink():
        raise RuntimeError(f"refusing to reuse output directory: {args.output_dir}")
    expected = (
        (args.expected_selected_common_sha256, BASE.DEFAULT_SELECTED_SHA256, "selected_csv_hash_mismatch"),
        (args.expected_sources_json_sha256, BASE.DEFAULT_SOURCES_SHA256, "sources_json_hash_mismatch"),
        (args.expected_filtered_manifest_sha256, BASE.DEFAULT_FILTERED_MANIFEST_SHA256, "filtered_manifest_hash_mismatch"),
        (args.expected_physsim_truth_sha256, PHYSSIM_SHA256, "helper_hash_mismatch"),
        (args.expected_whizard_truth_sha256, WHIZARD_TRUTH_SHA256, "whizard_truth_hash_mismatch"),
        (args.expected_chi2_reco_sha256, CHI2_RECO_SHA256, "chi2_reco_hash_mismatch"),
    )
    for supplied, frozen, code in expected:
        if supplied != frozen:
            raise hard(code, "expected hash argument differs from frozen contract")
    if args.mode == "smoke" and not args.compare_original_filtered:
        raise hard("smoke_original_filtered_mismatch", "--compare-original-filtered required")
    if args.mode == "formal" and args.compare_original_filtered:
        raise hard("unexpected_exception", "formal rejects smoke-only comparison")
    if args.mode == "smoke" and not (1 <= args.smoke_per_source <= 5):
        raise hard("unexpected_exception", "smoke-per-source must be in [1,5]")

    helper, whizard_truth, chi2_reco = load_truth_modules(
        args.physsim_truth_helper, args.whizard_truth_helper, args.chi2_reco
    )
    legacy_rerank = (
        Path(__file__).resolve().parents[2]
        / "reco_performance_study/legacy/rerank_tth_semilep_kinfit_with_flavor.py"
    )
    rerank = BASE.load_module("frozen_whizard_rerank_hybrid", legacy_rerank.resolve(strict=True))
    try:
        import pyLCIO
        from pyLCIO import IOIMPL, UTIL
        lcio_module_path = str(Path(pyLCIO.__file__).resolve())
    except Exception:
        import lcio
        from lcio import IOIMPL, UTIL
        lcio_module_path = str(Path(lcio.__file__).resolve())

    started = time.monotonic()
    selected_path, inputs = BASE.build_inputs(args, rerank)
    if args.mode == "smoke":
        rows = []
        for source_id, data in inputs.items():
            rows.extend(
                compare_smoke_source(
                    source_id,
                    data,
                    helper,
                    whizard_truth,
                    chi2_reco,
                    IOIMPL,
                    UTIL,
                    args.smoke_per_source,
                )
            )
        expected_events = args.smoke_per_source * len(BASE.EXPECTED_PER_SOURCE)
        if len(rows) != expected_events:
            raise hard("filtered_count_or_order_mismatch", "smoke count")
        if not any(int(row["result"].get("direct_b_truejet_multiplicity", 0)) > 2 for row in rows):
            raise hard("smoke_falsification_failed", "did not reproduce >2 direct-b TrueJets")
        if not any(row["result"]["status"] == "evaluable" for row in rows):
            raise hard("smoke_falsification_failed", "no event exercised full hybrid path")
        args.output_dir.mkdir(parents=True)
        smoke_rows = []
        for row in rows:
            result = row["result"]
            smoke_rows.append(
                {
                    "source_file_id": row["source_file_id"],
                    "original_local_index": row["original_local_index"],
                    "filtered_local_index": row["filtered_local_index"],
                    "run_number": row["run_number"],
                    "event_number": row["event_number"],
                    "status": result["status"],
                    "reason": result["reason"],
                    "direct_b_truejet_multiplicity": result.get("direct_b_truejet_multiplicity", ""),
                    "selected_top_truejet_stable": json.dumps(
                        result.get("selected_top_truejet_stable", []), sort_keys=True
                    ),
                    "selected_top_truejet_object_ids_nonpersistent": json.dumps(
                        result.get("selected_top_truejet_object_ids_nonpersistent", [])
                    ),
                    "higgs_indices": json.dumps(result.get("higgs_indices", [])),
                    "truth_pairs": json.dumps(result.get("truth_partition", {}).get("pairs", {}), sort_keys=True),
                    "flags": json.dumps(result.get("flags", {}), sort_keys=True),
                    "original_filtered_identical": 1,
                }
            )
        smoke_csv = args.output_dir / "smoke_events.csv"
        write_csv(smoke_csv, smoke_rows)
        summary_path = args.output_dir / "smoke_summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "passed",
                    "events": len(rows),
                    "per_source": args.smoke_per_source,
                    "full_path_evaluable": sum(row["result"]["status"] == "evaluable" for row in rows),
                    "direct_b_multiplicity_gt2": sum(
                        int(row["result"].get("direct_b_truejet_multiplicity", 0)) > 2 for row in rows
                    ),
                    "comparison": (
                        "exact status/reason/bridge/stable selected-top-TrueJet tuples/"
                        "selected refined top indices and Dice/fixed-H indices/truth partition/flags; "
                        "raw LCIO object IDs are non-persistent and excluded"
                    ),
                    "smoke_events_csv": {"path": str(smoke_csv.resolve()), "sha256": sha256(smoke_csv)},
                    "elapsed_seconds": time.monotonic() - started,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"status": "passed", "events": len(rows), "output": str(summary_path)}))
        return 0

    per_source = {}
    for source_id, data in inputs.items():
        per_source[source_id] = analyze_filtered_source(
            source_id, data, helper, whizard_truth, chi2_reco, IOIMPL, UTIL
        )
    totals, reasons, diagnostics, roles = aggregate(per_source)
    evaluable = int(totals["evaluable"])
    coverage = evaluable / BASE.BASE_DENOMINATOR
    status = "hybrid_truth_cross_generator_diagnostic" if coverage >= 0.95 else "conditional_hybrid_truth_diagnostic"
    metrics = {
        "method": METHOD,
        "candidate_pool": "signed-flavor-preselected Top10",
        "truth_definition": TRUTH_DEFINITION,
        "status": status,
        "selection_base_denominator": BASE.BASE_DENOMINATOR,
        "evaluable_denominator": evaluable,
        "coverage": coverage,
        **{f"{name}_correct": int(totals[f"{name}_correct"]) for name in ("W", "top", "H", "all")},
        **{
            f"A_{name}": int(totals[f"{name}_correct"]) / evaluable if evaluable else None
            for name in ("W", "top", "H", "all")
        },
    }
    args.output_dir.mkdir(parents=True)
    provenance_paths = create_provenance(args.output_dir, args.test_file)
    accuracy_csv = args.output_dir / "assignment_accuracy.csv"
    rejection_csv = args.output_dir / "rejection_summary.csv"
    role_csv = args.output_dir / "truejet_role_counts.csv"
    summary_json = args.output_dir / "summary.json"
    manifest_json = args.output_dir / "manifest.json"
    write_csv(accuracy_csv, [metrics])
    rejection_rows = []
    role_rows = []
    for source_id, (_counts, source_reasons, source_diagnostics, source_roles) in per_source.items():
        rejection_rows.extend(
            {"source_file_id": source_id, "category": "truth_unresolved_exclusive", "reason": reason, "count": int(count)}
            for reason, count in sorted(source_reasons.items())
        )
        rejection_rows.extend(
            {"source_file_id": source_id, "category": "diagnostic_nonexclusive", "reason": reason, "count": int(count)}
            for reason, count in sorted(source_diagnostics.items())
        )
        role_rows.extend(
            {"source_file_id": source_id, "measure": measure, "count": int(count)}
            for measure, count in sorted(source_roles.items())
        )
    rejection_rows.extend(
        {"source_file_id": "total", "category": "truth_unresolved_exclusive", "reason": reason, "count": int(count)}
        for reason, count in sorted(reasons.items())
    )
    rejection_rows.extend(
        {"source_file_id": "total", "category": "diagnostic_nonexclusive", "reason": reason, "count": int(count)}
        for reason, count in sorted(diagnostics.items())
    )
    role_rows.extend(
        {"source_file_id": "total", "measure": measure, "count": int(count)}
        for measure, count in sorted(roles.items())
    )
    write_csv(rejection_csv, rejection_rows)
    write_csv(role_csv, role_rows)
    output_paths = [accuracy_csv, rejection_csv, role_csv]
    if evaluable > 0:
        png = args.output_dir / "assignment_accuracy_hybrid_truth_qreco.png"
        pdf = args.output_dir / "assignment_accuracy_hybrid_truth_qreco.pdf"
        render_plot(metrics, png, pdf)
        output_paths.extend([png, pdf])
    elapsed = time.monotonic() - started
    summary = {
        "schema_version": 1,
        "status": status,
        "method": METHOD,
        "truth_definition": TRUTH_DEFINITION,
        "selection_base_denominator": BASE.BASE_DENOMINATOR,
        "evaluable_denominator": evaluable,
        "coverage": coverage,
        "numerators": {name: int(totals[f"{name}_correct"]) for name in ("W", "top", "H", "all")},
        "accuracies": {name: metrics[f"A_{name}"] for name in ("W", "top", "H", "all")},
        "truth_unresolved_exclusive": dict(sorted(reasons.items())),
        "diagnostic_nonexclusive": dict(sorted(diagnostics.items())),
        "truejet_role_counts": dict(sorted(roles.items())),
        "integrity_failures": [],
        "per_source": {
            source_id: {
                "counts": dict(counts),
                "exclusive_rejections": dict(sorted(source_reasons.items())),
                "diagnostic_nonexclusive": dict(sorted(source_diagnostics.items())),
                "truejet_role_counts": dict(sorted(source_roles.items())),
            }
            for source_id, (counts, source_reasons, source_diagnostics, source_roles) in per_source.items()
        },
        "closure": f"{BASE.BASE_DENOMINATOR} = {evaluable} evaluable + {sum(reasons.values())} truth-unresolved",
        "physics_contract": {
            "interpretation": (
                "CONDITIONAL HYBRID-TRUTH DIAGNOSTIC" if coverage < 0.95
                else "HYBRID-TRUTH CROSS-GENERATOR DIAGNOSTIC"
            ),
            "historical_conditioning": (
                "common4730 was preconditioned on old Whizard all-six-positive-Dice truth; not reapplied"
            ),
        },
        "elapsed_seconds": elapsed,
    }
    summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_paths.append(summary_json)
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "contract": {
            "sample": "Whizard eL.pR frozen common4730",
            "event_key": ["source_file_id", "local_index", "run_number", "event_number"],
            "candidate": METHOD,
            "candidate_selection": "accepted=1 && fit_success=1 && best_combo_id==kinfit_signed_combo_id",
            "fit_collection": COLLECTIONS["fit"],
            "truth_collection": COLLECTIONS["refined"],
            "bridge_minimum_dice": BRIDGE_MINIMUM_DICE,
            "top_minimum_dice": TOP_MINIMUM_DICE,
            "truth_definition": TRUTH_DEFINITION,
            "base_conditioning": "historical Whizard six-positive-Dice gate only; not reapplied",
        },
        "inputs": {
            "selected_common_csv": {"path": str(selected_path), "sha256": sha256(selected_path)},
            "sources_json": {"path": str(args.sources_json.resolve()), "sha256": sha256(args.sources_json)},
            "filtered_manifest": {"path": str(args.filtered_manifest.resolve()), "sha256": sha256(args.filtered_manifest)},
            "physsim_truth_helper": {"path": str(args.physsim_truth_helper.resolve()), "sha256": sha256(args.physsim_truth_helper)},
            "whizard_truth_helper": {"path": str(args.whizard_truth_helper.resolve()), "sha256": sha256(args.whizard_truth_helper)},
            "chi2_reco": {"path": str(args.chi2_reco.resolve()), "sha256": sha256(args.chi2_reco)},
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
            "path": str(path.resolve()), "sha256": sha256(path)
        }
    manifest_json.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "metrics": metrics, "output_dir": str(args.output_dir)}, sort_keys=True))
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
