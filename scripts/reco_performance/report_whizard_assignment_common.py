#!/usr/bin/env python3
"""Report frozen Top10 jet-assignment accuracies on one common event set."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path


MODES = {
    "mass-constraint-only": "price2014_prefit",
    "kinfit-only": "kinfit_chi2_only",
    "mass-constraint-only + signed flavor": "price2014_prefit_bcharge1p00",
    "kinfit + signed flavor": "authoritative_best_tree",
}

OFFLINE_MODES = {
    label: mode for label, mode in MODES.items() if mode != "authoritative_best_tree"
}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def method_key_sets(selected):
    sets = {method: set(rows) for method, rows in selected.items()}
    if sets and len({frozenset(keys) for keys in sets.values()}) != 1:
        raise RuntimeError(f"assignment method denominator mismatch: {sets}")
    return sets


def add_counter(counters, source, name, amount=1):
    counters[source][name] += amount
    counters["total"][name] += amount


def top10_rows_aligned(rows, combo_ids):
    if len(combo_ids) != 10 or len(set(int(value) for value in combo_ids)) != 10:
        return False
    for row in rows:
        rank = int(row["candidate_rank"])
        if rank < 0 or rank >= 10 or int(row["combo_id"]) != int(combo_ids[rank]):
            return False
    return bool(rows)


def write_csv(path, rows):
    fields = list(rows[0]) if rows else ["method", "denominator", "W_correct", "top_correct", "H_correct", "all_correct", "A_W", "A_top", "A_H", "A_all"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_authoritative_best_map(root_path, rerank):
    handle = rerank.ROOT.TFile.Open(root_path)
    if not handle or handle.IsZombie():
        raise RuntimeError(f"cannot open authoritative ROOT: {root_path}")
    tree = handle.Get("TTHSemiLepKinFit")
    if tree is None:
        handle.Close()
        raise RuntimeError(f"missing authoritative best tree in {root_path}")
    branches = rerank.branch_names(tree)
    required = {"event_index", "accepted", "fit_success", "best_combo_id"}
    missing = sorted(required - branches)
    if missing:
        handle.Close()
        raise RuntimeError(f"authoritative best tree missing branches: {missing}")
    out = {}
    try:
        for row in tree:
            event_index = int(row.event_index)
            if int(row.accepted) == 1 and int(row.fit_success) == 1:
                out[event_index] = int(row.best_combo_id)
    finally:
        handle.Close()
    return out


def analyze_source(source, rerank, legacy_cm, boundary, price, counters):
    source_id = source["source_file_id"]
    lcio = source["lcio"]
    root = source["root"]
    expected_events = int(source["expected_events"])
    top_scores, accepted = rerank.read_top_score_map(root)
    authoritative = read_authoritative_best_map(root, rerank)
    candidate_rows = rerank.read_candidate_rows(root, source_id, top_scores)
    add_counter(counters, source_id, "top10_accepted", len(accepted))
    rows_by_event = defaultdict(list)
    for row in candidate_rows:
        rows_by_event[int(row["event_index"])].append(row)

    cfg = rerank.cfg_for_matching(lcio, "OutputErrorFlowJets6")
    truth = {}
    source_keys = {}
    seen_keys = set()
    reader = legacy_cm.IOIMPL.LCFactory.getInstance().createLCReader()
    reader.open(lcio)
    local_index = 0
    try:
        while True:
            event = reader.readNextEvent()
            if not bool(event):
                break
            add_counter(counters, source_id, "events_read")
            key = boundary.source_event_key(source_id, local_index, event)
            if key in seen_keys:
                raise RuntimeError(f"duplicate source-aware event key: {key}")
            seen_keys.add(key)
            if local_index in accepted:
                source_keys[local_index] = key
                state, context = boundary.relation_context(
                    event, "OutputErrorFlowJets6", legacy_cm
                )
                add_counter(counters, source_id, state)
                if state == "relation_eligible":
                    assignment_state, _, _ = boundary.positive_dice_assignment(
                        context, legacy_cm
                    )
                    add_counter(counters, source_id, assignment_state)
                    if assignment_state != "accepted_six_positive":
                        local_index += 1
                        continue
                    truth_summary = Counter()
                    cfg["min_truejet_dice"] = math.nextafter(0.0, 1.0)
                    truth_info, matched = rerank.match_semileptonic_event_by_role_source(
                        event,
                        context["reco"],
                        cfg,
                        truth_summary,
                        role_source="truejet_direct",
                    )
                    if truth_info is not None:
                        add_counter(counters, source_id, "truth_selected")
                    if truth_info is not None and matched is not None:
                        event_flags = {}
                        for combo_id, assignment in rerank.ASSIGNMENT_BY_ID.items():
                            flags = rerank.truth_flags_semileptonic(assignment, matched)
                            event_flags[int(combo_id)] = {
                                "truth_match_W": int(flags["W"]),
                                "truth_match_t": int(flags["top"]),
                                "truth_match_H": int(flags["H"]),
                                "truth_match_all": int(flags["all"]),
                            }
                        truth[local_index] = event_flags
                        add_counter(counters, source_id, "truth_match_success")
            local_index += 1
    finally:
        reader.close()
    if local_index != expected_events:
        raise RuntimeError(
            f"{source_id} readable event count {local_index} != expected {expected_events}"
        )
    if not accepted.issubset(source_keys):
        raise RuntimeError(f"{source_id} ROOT event_index lies outside its LCIO input")

    flavor_priors, flavor_summary = rerank.build_flavor_prior_map(
        lcio, accepted, "RefinedJets6"
    )
    for name, value in flavor_summary.items():
        add_counter(counters, source_id, f"flavor_{name}", int(value))
    attached = rerank.attach_scores_and_truth(candidate_rows, truth, price, flavor_priors)
    attached_by_event = defaultdict(list)
    for row in attached:
        attached_by_event[int(row["event_index"])].append(row)

    selected = {method: {} for method in MODES}
    for event_index in sorted(accepted):
        raw_rows = rows_by_event.get(event_index, [])
        rows = attached_by_event.get(event_index, [])
        combo_ids = top_scores.get(event_index, {}).get("combo_ids", [])
        if not top10_rows_aligned(raw_rows, combo_ids):
            add_counter(counters, source_id, "top10_alignment_failed")
            continue
        fit_rows = [row for row in rows if int(row.get("fit_success", 0)) == 1]
        if fit_rows:
            add_counter(counters, source_id, "fit_success")
        score_valid = {}
        for label, mode in OFFLINE_MODES.items():
            candidate_rows_for_mode = (
                fit_rows if rerank.mode_uses_kinfit(mode) else rows
            )
            score_valid[label] = any(
                math.isfinite(rerank.mode_score(row, mode)[0])
                for row in candidate_rows_for_mode
            )
        score_valid["kinfit + signed flavor"] = event_index in authoritative
        for name, valid in score_valid.items():
            if valid:
                add_counter(counters, source_id, f"{name}_valid")
        if event_index not in truth or not all(score_valid.values()):
            continue
        best = rerank.select_best_by_mode(
            rows, list(OFFLINE_MODES.values()), require_converged=False
        )
        if set(best) != set(OFFLINE_MODES.values()):
            continue
        authoritative_combo = authoritative[event_index]
        authoritative_flags = truth[event_index].get(authoritative_combo)
        if authoritative_flags is None:
            continue
        key = source_keys[event_index]
        for method, mode in MODES.items():
            selected_flags = (
                authoritative_flags if mode == "authoritative_best_tree" else best[mode]
            )
            selected[method][key] = selected_flags
            for name in ("W", "t", "H", "all"):
                add_counter(
                    counters,
                    source_id,
                    f"{method}_{name}_correct",
                    int(selected_flags[f"truth_match_{name}"]),
                )
        add_counter(counters, source_id, "common_eligible")
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources-json", type=Path, required=True)
    parser.add_argument("--legacy-rerank", type=Path, required=True)
    parser.add_argument("--legacy-cm", type=Path, required=True)
    parser.add_argument("--chi2-module-dir", type=Path, required=True)
    parser.add_argument("--model-bundle", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() or args.output_dir.is_symlink():
        raise RuntimeError(f"refusing to reuse output directory: {args.output_dir}")
    sys.path.insert(0, str(args.chi2_module_dir.resolve(strict=True)))
    rerank = load_module("frozen_whizard_rerank", args.legacy_rerank.resolve(strict=True))
    legacy_cm = load_module("frozen_whizard_cm", args.legacy_cm.resolve(strict=True))
    boundary = load_module(
        "normalized_whizard_cm_boundary",
        Path(__file__).resolve().with_name("report_whizard_jet_cm.py"),
    )
    sources = json.loads(args.sources_json.read_text(encoding="utf-8"))["sources"]
    price = rerank.load_price2014(str(args.model_bundle.resolve(strict=True)))
    counters = {source["source_file_id"]: Counter() for source in sources}
    counters["total"] = Counter()
    selected = {method: {} for method in MODES}
    for source in sources:
        source_selected = analyze_source(
            source, rerank, legacy_cm, boundary, price, counters
        )
        for method in MODES:
            overlap = set(selected[method]) & set(source_selected[method])
            if overlap:
                raise RuntimeError(f"duplicate source-aware assignment keys: {overlap}")
            selected[method].update(source_selected[method])
    key_sets = method_key_sets(selected)
    denominator = len(next(iter(key_sets.values()))) if key_sets else 0

    metrics = []
    for method, rows in selected.items():
        raw = {
            name: sum(int(row[f"truth_match_{name}"]) for row in rows.values())
            for name in ("W", "t", "H", "all")
        }
        metrics.append(
            {
                "method": method,
                "denominator": denominator,
                "W_correct": raw["W"],
                "top_correct": raw["t"],
                "H_correct": raw["H"],
                "all_correct": raw["all"],
                "A_W": raw["W"] / denominator if denominator else None,
                "A_top": raw["t"] / denominator if denominator else None,
                "A_H": raw["H"] / denominator if denominator else None,
                "A_all": raw["all"] / denominator if denominator else None,
            }
        )
        for name, value in raw.items():
            if counters["total"][f"{method}_{name}_correct"] != value:
                raise RuntimeError(f"{method} {name} raw counter aggregation mismatch")

    args.output_dir.mkdir(parents=True)
    write_csv(args.output_dir / "assignment_accuracy_common.csv", metrics)
    payload = {
        "sources": sources,
        "modes": MODES,
        "denominator": denominator,
        "common_event_keys": [list(key) for key in sorted(next(iter(key_sets.values())))],
        "method_event_keys_identical": True,
        "metrics": metrics,
        "counters": {name: dict(value) for name, value in counters.items()},
    }
    (args.output_dir / "assignment_accuracy_common.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
