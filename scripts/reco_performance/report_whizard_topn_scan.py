#!/usr/bin/env python3
"""Aggregate Whizard Top1/5/10 accuracy and measured Marlin runtime."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


TOP_NS = (1, 5, 10)
METHODS = {
    "mass constraint-only + q_flavor minimize": {
        "internal_mode": "price2014_prefit_bcharge1p00",
        "stage": "PREFIT",
        "candidate_pool": "signed-flavor-preselected TopN",
    },
    "q_reco minimize": {
        "internal_mode": "authoritative_best_tree",
        "stage": "POSTFIT",
        "candidate_pool": "signed-flavor-preselected TopN",
    },
}


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


def verify_root(run):
    observed = sha256(run["root"])
    if observed != run.get("root_sha256"):
        raise RuntimeError(f"ROOT hash mismatch: {run['root']}")
    return observed


def topn_rows_aligned(rows, combo_ids, top_n):
    if len(combo_ids) != top_n or len(set(int(value) for value in combo_ids)) != top_n:
        return False
    ranks = set()
    for row in rows:
        rank = int(row["candidate_rank"])
        if rank < 0 or rank >= top_n or int(row["combo_id"]) != int(combo_ids[rank]):
            return False
        ranks.add(rank)
    return ranks == set(range(top_n))


def parse_marlin_runtime(path, expected_top_n, expected_events):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    configured = re.findall(r"\bTopN:\s+(\d+)\s*$", text, flags=re.MULTILINE)
    processed = re.findall(
        r"TTHSemiLepKinFit processed\s+(\d+)\s+events", text
    )
    processor = re.findall(
        r"^\[ MESSAGE \"Marlin\"\] MyTTHSemiLepKinFit\s+([0-9.eE+-]+) s in\s+(\d+) events",
        text,
        flags=re.MULTILINE,
    )
    total = re.findall(
        r"^\[ MESSAGE \"Marlin\"\]\s+Total:\s+([0-9.eE+-]+) s in\s+(\d+) events",
        text,
        flags=re.MULTILINE,
    )
    if configured != [str(expected_top_n)]:
        raise RuntimeError(f"TopN timing-log mismatch in {path}: {configured}")
    if processed != [str(expected_events)]:
        raise RuntimeError(f"processed-event timing-log mismatch in {path}: {processed}")
    if len(processor) != 1 or len(total) != 1:
        raise RuntimeError(f"missing or duplicate Marlin timing lines in {path}")
    processor_seconds, processor_events = float(processor[0][0]), int(processor[0][1])
    total_seconds, total_events = float(total[0][0]), int(total[0][1])
    if processor_events != expected_events or total_events != expected_events:
        raise RuntimeError(f"timing denominator mismatch in {path}")
    return {
        "processor_seconds": processor_seconds,
        "total_seconds": total_seconds,
        "events": expected_events,
    }


def analyze_source(source, rerank, legacy_cm, boundary, phase1, price, counters):
    source_id = source["source_file_id"]
    expected_events = int(source["expected_events"])
    per_n = {}
    union_accepted = set()
    for top_n in TOP_NS:
        run = source["runs"][str(top_n)]
        verify_root(run)
        top_scores, accepted = rerank.read_top_score_map(run["root"])
        authoritative = phase1.read_authoritative_best_map(run["root"], rerank)
        rows = rerank.read_candidate_rows(run["root"], f"top{top_n}", top_scores)
        rows_by_event = defaultdict(list)
        for row in rows:
            rows_by_event[int(row["event_index"])].append(row)
        per_n[top_n] = {
            "top_scores": top_scores,
            "accepted": accepted,
            "authoritative": authoritative,
            "rows": rows,
            "rows_by_event": rows_by_event,
        }
        union_accepted.update(accepted)
        counters[f"top{top_n}_best_rows"] += len(accepted)
        counters[f"top{top_n}_candidate_rows"] += len(rows)

    cfg = rerank.cfg_for_matching(source["lcio"], "OutputErrorFlowJets6")
    truth = {}
    source_keys = {}
    reader = legacy_cm.IOIMPL.LCFactory.getInstance().createLCReader()
    reader.open(source["lcio"])
    local_index = 0
    try:
        while local_index < expected_events:
            event = reader.readNextEvent()
            if not bool(event):
                break
            if local_index in union_accepted:
                key = boundary.source_event_key(source_id, local_index, event)
                source_keys[local_index] = key
                state, context = boundary.relation_context(
                    event, "OutputErrorFlowJets6", legacy_cm
                )
                counters[state] += 1
                if state == "relation_eligible":
                    assignment_state, _, _ = boundary.positive_dice_assignment(
                        context, legacy_cm
                    )
                    counters[assignment_state] += 1
                    if assignment_state == "accepted_six_positive":
                        truth_summary = Counter()
                        cfg["min_truejet_dice"] = math.nextafter(0.0, 1.0)
                        truth_info, matched = rerank.match_semileptonic_event_by_role_source(
                            event,
                            context["reco"],
                            cfg,
                            truth_summary,
                            role_source="truejet_direct",
                        )
                        if truth_info is not None and matched is not None:
                            truth[local_index] = {
                                int(combo_id): {
                                    f"truth_match_{name}": int(value)
                                    for name, value in (
                                        ("W", flags["W"]),
                                        ("t", flags["top"]),
                                        ("H", flags["H"]),
                                        ("all", flags["all"]),
                                    )
                                }
                                for combo_id, assignment in rerank.ASSIGNMENT_BY_ID.items()
                                for flags in [rerank.truth_flags_semileptonic(assignment, matched)]
                            }
            local_index += 1
    finally:
        reader.close()
    if local_index != expected_events:
        raise RuntimeError(
            f"{source_id} readable event count {local_index} != expected ceiling {expected_events}"
        )
    if not union_accepted.issubset(source_keys):
        raise RuntimeError(f"{source_id}: ROOT event index lies outside LCIO ceiling")

    flavor_priors, flavor_summary = rerank.build_flavor_prior_map(
        source["lcio"], union_accepted, "RefinedJets6"
    )
    for name, value in flavor_summary.items():
        counters[f"flavor_{name}"] += int(value)

    selected = {
        top_n: {method: {} for method in METHODS} for top_n in TOP_NS
    }
    prefit_label = "mass constraint-only + q_flavor minimize"
    postfit_label = "q_reco minimize"
    mode = METHODS[prefit_label]["internal_mode"]
    for top_n in TOP_NS:
        data = per_n[top_n]
        attached = rerank.attach_scores_and_truth(
            data["rows"], truth, price, flavor_priors
        )
        attached_by_event = defaultdict(list)
        for row in attached:
            attached_by_event[int(row["event_index"])].append(row)
        for event_index in sorted(data["accepted"]):
            raw_rows = data["rows_by_event"].get(event_index, [])
            combo_ids = data["top_scores"].get(event_index, {}).get("combo_ids", [])
            if not topn_rows_aligned(raw_rows, combo_ids, top_n):
                counters[f"top{top_n}_alignment_failed"] += 1
                continue
            if event_index not in truth or event_index not in data["authoritative"]:
                continue
            best = rerank.select_best_by_mode(
                attached_by_event.get(event_index, []), [mode], require_converged=False
            )
            if mode not in best:
                continue
            authoritative = data["authoritative"][event_index]
            authoritative_flags = truth[event_index].get(authoritative["combo_id"])
            if authoritative_flags is None:
                continue
            key = source_keys[event_index]
            selected[top_n][prefit_label][key] = best[mode]
            selected[top_n][postfit_label][key] = {
                **authoritative,
                **authoritative_flags,
            }
    return selected


def plot_results(metrics, runtimes, png, pdf, plt):
    fig, (accuracy_axis, runtime_axis) = plt.subplots(1, 2, figsize=(13.5, 5.4), dpi=180)
    colors = ("#6a51a3", "#2a9d8f")
    for color, method in zip(colors, METHODS):
        rows = [row for row in metrics if row["display_label"] == method]
        accuracy_axis.plot(
            [row["top_n"] for row in rows],
            [row["A_all"] for row in rows],
            marker="o",
            linewidth=2,
            color=color,
            label=method,
        )
    accuracy_axis.set_xlabel("TopN base combo_id values retained")
    accuracy_axis.set_ylabel("A_all")
    accuracy_axis.set_xticks(TOP_NS)
    accuracy_axis.grid(alpha=0.3)
    accuracy_axis.legend(fontsize=8)
    runtime_axis.plot(
        [row["top_n"] for row in runtimes],
        [row["total_seconds"] for row in runtimes],
        color="#d95f02",
        marker="s",
        linewidth=2,
        label="Marlin Total",
    )
    runtime_axis.set_xlabel("TopN")
    runtime_axis.set_ylabel("measured seconds; four chunks summed")
    runtime_axis.set_xticks(TOP_NS)
    runtime_axis.grid(alpha=0.3)
    runtime_axis.legend(fontsize=8)
    denominator = metrics[0]["denominator"]
    fig.suptitle(
        f"Whizard eL.pR TopN accuracy and measured Marlin runtime; common {denominator}-event denominator"
    )
    fig.tight_layout()
    fig.savefig(png, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
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
    rerank = load_module("topn_frozen_rerank", args.legacy_rerank.resolve(strict=True))
    legacy_cm = load_module("topn_frozen_cm", args.legacy_cm.resolve(strict=True))
    boundary = load_module(
        "topn_positive_dice_boundary",
        Path(__file__).resolve().with_name("report_whizard_jet_cm.py"),
    )
    phase1 = load_module(
        "topn_phase1_helpers",
        Path(__file__).resolve().with_name("report_whizard_assignment_common.py"),
    )
    sources = json.loads(args.sources_json.read_text(encoding="utf-8"))["sources"]
    price = rerank.load_price2014(str(args.model_bundle.resolve(strict=True)))
    counters = Counter()
    selected = {top_n: {method: {} for method in METHODS} for top_n in TOP_NS}
    for source in sources:
        source_selected = analyze_source(
            source, rerank, legacy_cm, boundary, phase1, price, counters
        )
        for top_n in TOP_NS:
            for method in METHODS:
                overlap = set(selected[top_n][method]) & set(source_selected[top_n][method])
                if overlap:
                    raise RuntimeError(f"duplicate source-aware TopN keys: {overlap}")
                selected[top_n][method].update(source_selected[top_n][method])
    common = set.intersection(
        *(set(selected[top_n][method]) for top_n in TOP_NS for method in METHODS)
    )
    if not common:
        raise RuntimeError("empty Top1/5/10 two-method common denominator")
    metrics = []
    for top_n in TOP_NS:
        for method in METHODS:
            rows = selected[top_n][method]
            correct = {
                name: sum(int(rows[key][f"truth_match_{name}"]) for key in common)
                for name in ("W", "t", "H", "all")
            }
            metrics.append(
                {
                    "top_n": top_n,
                    "display_label": method,
                    "internal_mode": METHODS[method]["internal_mode"],
                    "stage": METHODS[method]["stage"],
                    "candidate_pool": METHODS[method]["candidate_pool"],
                    "denominator": len(common),
                    "W_correct": correct["W"],
                    "top_correct": correct["t"],
                    "H_correct": correct["H"],
                    "all_correct": correct["all"],
                    "A_W": correct["W"] / len(common),
                    "A_top": correct["t"] / len(common),
                    "A_H": correct["H"] / len(common),
                    "A_all": correct["all"] / len(common),
                }
            )
    runtimes = []
    runtime_chunks = []
    for top_n in TOP_NS:
        records = []
        for source in sources:
            log = Path(source["runs"][str(top_n)]["log"])
            record = parse_marlin_runtime(log, top_n, int(source["expected_events"]))
            records.append(record)
            runtime_chunks.append(
                {
                    "top_n": top_n,
                    "source_file_id": source["source_file_id"],
                    "events": record["events"],
                    "total_seconds": record["total_seconds"],
                    "total_seconds_per_event": record["total_seconds"] / record["events"],
                    "log": str(log),
                    "log_sha256": sha256(log),
                }
            )
        events = sum(row["events"] for row in records)
        processor_seconds = sum(row["processor_seconds"] for row in records)
        total_seconds = sum(row["total_seconds"] for row in records)
        runtimes.append(
            {
                "top_n": top_n,
                "chunks": len(records),
                "events": events,
                "processor_seconds": processor_seconds,
                "total_seconds": total_seconds,
                "processor_seconds_per_event": processor_seconds / events,
                "total_seconds_per_event": total_seconds / events,
            }
        )
    args.output_dir.mkdir(parents=True)
    accuracy_csv = args.output_dir / "topn_accuracy.csv"
    runtime_csv = args.output_dir / "topn_runtime.csv"
    runtime_chunks_csv = args.output_dir / "topn_runtime_per_chunk.csv"
    png = args.output_dir / "whizard_topn_accuracy_runtime.png"
    pdf = args.output_dir / "whizard_topn_accuracy_runtime.pdf"
    write_csv(accuracy_csv, metrics)
    write_csv(runtime_csv, runtimes)
    write_csv(runtime_chunks_csv, runtime_chunks)
    plot_results(metrics, runtimes, png, pdf, legacy_cm.plt)
    command = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]]
    payload = {
        "status": "NAF diagnostic from canonical TopN workflow ROOTs and measured Marlin logs",
        "top_n": list(TOP_NS),
        "methods": METHODS,
        "candidate_pool": "TopN counts unique base combo_id values; all persisted SLD/neutrino rows retained",
        "truth": "OutputErrorFlowJets6 to TrueJets; all six assigned Dice values strictly greater than zero",
        "event_key": ["source_file_id", "local_index", "run_number", "event_number"],
        "denominator": len(common),
        "common_event_keys": [list(key) for key in sorted(common)],
        "metrics": metrics,
        "runtimes": runtimes,
        "runtime_per_chunk": runtime_chunks,
        "runtime_definition": "Marlin Total log seconds summed over four 12499-event chunks",
        "counters": dict(counters),
        "sources": sources,
    }
    result_json = args.output_dir / "topn_accuracy_runtime.json"
    result_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "command": command,
        "sources_json": {"path": str(args.sources_json.resolve()), "sha256": sha256(args.sources_json)},
        "model_bundle": {"path": str(args.model_bundle.resolve()), "sha256": sha256(args.model_bundle)},
        "legacy_rerank": {"path": str(args.legacy_rerank.resolve()), "sha256": sha256(args.legacy_rerank)},
        "legacy_cm": {"path": str(args.legacy_cm.resolve()), "sha256": sha256(args.legacy_cm)},
        "script": {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
        "denominator": len(common),
        "root_inputs": [
            {
                "source_file_id": source["source_file_id"],
                "top_n": top_n,
                "path": source["runs"][str(top_n)]["root"],
                "sha256": source["runs"][str(top_n)]["root_sha256"],
                "log": source["runs"][str(top_n)]["log"],
                "log_sha256": sha256(source["runs"][str(top_n)]["log"]),
            }
            for source in sources
            for top_n in TOP_NS
        ],
    }
    manifest["outputs"] = {
        path.name: {"path": str(path), "sha256": sha256(path)}
        for path in (accuracy_csv, runtime_csv, runtime_chunks_csv, result_json, png, pdf)
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"denominator": len(common), "output_dir": str(args.output_dir)}, sort_keys=True))


if __name__ == "__main__":
    main()
