#!/usr/bin/env python3
"""Run the frozen Whizard TrueJet/Weaver confusion-matrix analysis."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path


RELATION_STATES = (
    "relation_missing",
    "relation_empty",
    "relation_no_overlap",
    "relation_eligible",
)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_matrix_csv(path, matrix, labels, formatter):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["predicted\\true", *labels])
        for index, label in enumerate(labels):
            writer.writerow([label, *[formatter(matrix[index, column]) for column in range(len(labels))]])


def source_event_key(source_file_id, local_index, event):
    return (
        source_file_id,
        int(local_index),
        int(event.getRunNumber()),
        int(event.getEventNumber()),
    )


def relation_state(relation, shared_matrix):
    if relation is None:
        return "relation_missing"
    if int(relation.getNumberOfElements()) == 0:
        return "relation_empty"
    if not any(float(value) > 0.0 for row in shared_matrix for value in row):
        return "relation_no_overlap"
    return "relation_eligible"


def relation_context(event, reco_collection_name, legacy):
    relation = legacy.get_col(event, "TrueJetPFOLink")
    if relation is None:
        return "relation_missing", None
    if int(relation.getNumberOfElements()) == 0:
        return "relation_empty", None
    reco = legacy.get_col(event, reco_collection_name)
    if reco is None:
        return "missing_reco_jets", None
    if int(reco.getNumberOfElements()) != 6:
        return "wrong_reco_multiplicity", None
    truejets = legacy.get_col(event, "TrueJets")
    if truejets is None:
        return "missing_truejets", None
    quarks = legacy.collect_truejet_quark_jets(truejets)
    if len(quarks) != 6:
        return "wrong_truejet_multiplicity", None
    navigator = legacy.UTIL.LCRelationNavigator(relation)
    true_map = legacy.build_truejet_pfo_map(quarks, navigator)
    reco_infos = legacy.build_reco_jet_pfo_map(reco)
    true_ids = sorted(true_map)
    score = legacy.np.zeros((6, 6), dtype=float)
    shared = legacy.np.zeros((6, 6), dtype=float)
    for reco_index in range(6):
        for true_index in range(6):
            true_info = true_map[true_ids[true_index]]
            overlap = legacy.shared_energy(reco_infos[reco_index], true_info)
            shared[reco_index, true_index] = overlap
            score[reco_index, true_index] = legacy.dice_score(
                overlap,
                reco_infos[reco_index]["energy"],
                true_info["energy"],
            )
    state = relation_state(relation, shared)
    if state != "relation_eligible":
        return state, None
    return state, {
        "reco": reco,
        "reco_infos": reco_infos,
        "true_map": true_map,
        "true_ids": true_ids,
        "score": score,
    }


def add_counter(target, source, name, amount=1):
    target[source][name] += amount
    target["total"][name] += amount


def complete_six_jet_entries(entries):
    return list(entries) if len(entries) == 6 else None


def positive_dice_assignment(context, legacy):
    """Return an assignment only when all six assigned Dice values are positive."""
    permutation, _ = legacy.best_assignment(context["score"])
    if permutation is None:
        return "no_assignment", None, []
    assigned = [
        float(context["score"][reco_index, permutation[reco_index]])
        for reco_index in range(6)
    ]
    if not all(value > 0.0 for value in assigned):
        return "relation_nonpositive_assigned_dice", None, assigned
    return "accepted_six_positive", permutation, assigned


def run_cm(sources, legacy, expected_events, selected_indices=None):
    counts = legacy.init_matrix()
    counters = {source["source_file_id"]: Counter() for source in sources}
    counters["total"] = Counter()
    seen_keys = set()
    used_keys = []
    probe = []

    for source in sources:
        source_id = source["source_file_id"]
        wanted = None if selected_indices is None else set(selected_indices[source_id])
        reader = legacy.IOIMPL.LCFactory.getInstance().createLCReader()
        reader.open(source["lcio"])
        local_index = 0
        try:
            while True:
                event = reader.readNextEvent()
                if not bool(event):
                    break
                add_counter(counters, source_id, "events_read")
                key = source_event_key(source_id, local_index, event)
                if key in seen_keys:
                    raise RuntimeError(f"duplicate source-aware event key: {key}")
                seen_keys.add(key)
                analyze = wanted is None or local_index in wanted
                if analyze:
                    add_counter(counters, source_id, "events_analyzed")
                    if wanted is not None:
                        probe_state, probe_context = relation_context(event, "RefinedJets6", legacy)
                        assigned_state = None
                        assigned_dice = []
                        if probe_state == "relation_eligible":
                            assigned_state, _, assigned_dice = positive_dice_assignment(
                                probe_context, legacy
                            )
                        probe.append(
                            {
                                "source_file_id": source_id,
                                "local_index": local_index,
                                "run": key[2],
                                "event": key[3],
                                "relation_state": probe_state,
                                "assigned_dice_state": assigned_state,
                                "assigned_dice": assigned_dice,
                            }
                        )
                    channel = legacy.truth_ttbar_channel(event, colMC="MCParticlesSkimmed")
                    if channel is not None and legacy.keep_semilep_channel(channel, "all"):
                        hbb = legacy.truth_h_to_bb(event, colMC="MCParticlesSkimmed")
                        if hbb is True:
                            add_counter(counters, source_id, "truth_selected")
                            state, context = relation_context(event, "RefinedJets6", legacy)
                            add_counter(counters, source_id, state)
                            if state == "relation_eligible":
                                assignment_state, permutation, _ = positive_dice_assignment(
                                    context, legacy
                                )
                                add_counter(counters, source_id, assignment_state)
                                if assignment_state == "accepted_six_positive":
                                    try:
                                        algorithm_id, _ = legacy.get_weaver_alg_id(
                                            context["reco"], weaver_name="weaver"
                                        )
                                    except Exception:
                                        add_counter(counters, source_id, "missing_weaver_algorithm")
                                    else:
                                        entries = []
                                        for reco_index in range(6):
                                            predicted, _ = legacy.get_weaver_pred_label_quark10(
                                                context["reco_infos"][reco_index]["obj"],
                                                algorithm_id,
                                            )
                                            if predicted is None:
                                                entries = []
                                                break
                                            true_info = context["true_map"][
                                                context["true_ids"][permutation[reco_index]]
                                            ]
                                            entries.append((predicted, true_info["label"]))
                                        entries = complete_six_jet_entries(entries)
                                        if entries is None:
                                            add_counter(counters, source_id, "missing_weaver_pid")
                                        else:
                                            for predicted, truth in entries:
                                                legacy.fill_matrix(counts, predicted, truth)
                                            add_counter(counters, source_id, "cm_events_used")
                                            add_counter(counters, source_id, "cm_jets_used", 6)
                                            used_keys.append(key)
                local_index += 1
        finally:
            reader.close()
        if local_index != int(expected_events):
            raise RuntimeError(
                f"{source_id} readable event count {local_index} != expected {expected_events}"
            )
        if wanted is not None and {row["local_index"] for row in probe if row["source_file_id"] == source_id} != wanted:
            raise RuntimeError(f"{source_id} did not expose every requested smoke index")

    if int(counts.sum()) != int(counters["total"]["cm_jets_used"]):
        raise RuntimeError("confusion-matrix entries do not match atomic six-jet counter")
    if int(counts.sum()) != 6 * int(counters["total"]["cm_events_used"]):
        raise RuntimeError("one or more CM events did not contribute exactly six jets")
    return counts, counters, used_keys, probe


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources-json", type=Path, required=True)
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-events", type=int, default=12500)
    parser.add_argument("--indices-json", type=Path)
    parser.add_argument("--expected-relations-json", type=Path)
    args = parser.parse_args()
    if args.output_dir.exists() or args.output_dir.is_symlink():
        raise RuntimeError(f"refusing to reuse output directory: {args.output_dir}")
    sources = json.loads(args.sources_json.read_text(encoding="utf-8"))["sources"]
    selected = None
    if args.indices_json:
        selected = json.loads(args.indices_json.read_text(encoding="utf-8"))
    legacy = load_module("frozen_whizard_cm", args.legacy.resolve(strict=True))
    counts, counters, used_keys, probe = run_cm(
        sources, legacy, args.expected_events, selected_indices=selected
    )
    if args.expected_relations_json:
        expected = json.loads(args.expected_relations_json.read_text(encoding="utf-8"))
        observed = {
            f"{row['source_file_id']}:{row['local_index']}": row["relation_state"]
            for row in probe
        }
        if observed != expected:
            raise RuntimeError(f"relation-state smoke mismatch: {observed} != {expected}")

    args.output_dir.mkdir(parents=True)
    normalized = legacy.normalize_by_true_columns(counts)
    prefix = args.output_dir / "whizard_truejet_weaver_cm10"
    raw_csv = args.output_dir / "whizard_truejet_weaver_cm10_raw.csv"
    normalized_csv = args.output_dir / "whizard_truejet_weaver_cm10_normalized.csv"
    png = prefix.with_suffix(".png")
    pdf = prefix.with_suffix(".pdf")
    legacy.np.savez(
        str(prefix) + ".npz",
        counts=counts,
        norm=normalized,
        class_order=legacy.np.array(legacy.CLASS_ORDER, dtype=object),
    )
    legacy.save_csv(str(prefix) + ".csv", counts, normalized)
    write_matrix_csv(raw_csv, counts, legacy.CLASS_ORDER, lambda value: str(int(value)))
    write_matrix_csv(normalized_csv, normalized, legacy.CLASS_ORDER, lambda value: f"{float(value):.9g}")
    legacy.plot_confusion(
        normalized,
        str(png),
        title=r"$t\bar t H,\ H\to b\bar b,\ \mathrm{semileptonic}$"
        + "\nRefinedJets6–TrueJets six-positive-Dice matching; Weaver 10x10",
    )
    legacy.plot_confusion(
        normalized,
        str(pdf),
        title=r"$t\bar t H,\ H\to b\bar b,\ \mathrm{semileptonic}$"
        + "\nRefinedJets6–TrueJets six-positive-Dice matching; Weaver 10x10",
    )
    payload = {
        "sources": sources,
        "expected_events_per_source": args.expected_events,
        "counters": {name: dict(value) for name, value in counters.items()},
        "cm_used_event_keys": [list(key) for key in used_keys],
        "probe": probe,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    command = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]]
    outputs = (
        prefix.with_suffix(".npz"),
        prefix.with_suffix(".csv"),
        raw_csv,
        normalized_csv,
        png,
        pdf,
        args.output_dir / "summary.json",
    )
    manifest = {
        "status": "formal full-sample Whizard jet-flavor confusion matrix",
        "observable": "column-normalized predicted Weaver flavor versus matched TrueJet quark flavor",
        "collection": "RefinedJets6",
        "truth_collection": "TrueJets via TrueJetPFOLink",
        "selection": "truth H->bb and semileptonic ttbar; all six assigned Dice values strictly greater than zero",
        "denominator": "all selected jets from atomically accepted six-jet events",
        "sources": sources,
        "sources_json": {"path": str(args.sources_json.resolve()), "sha256": sha256(args.sources_json)},
        "legacy": {"path": str(args.legacy.resolve()), "sha256": sha256(args.legacy)},
        "script": {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
        "command": command,
        "outputs": {path.name: {"path": str(path), "sha256": sha256(path)} for path in outputs},
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
