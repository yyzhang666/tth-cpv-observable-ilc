#!/usr/bin/env python3
"""Replace only the first two common4730 assignment bars with full180 results."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path


KEY_FIELDS = ("source_file_id", "local_index", "run_number", "event_number")
NUMERIC_FIELDS = (
    "denominator", "W_correct", "top_correct", "H_correct", "all_correct",
    "A_W", "A_top", "A_H", "A_all",
)
DISPLAY = (
    {
        "display_label": "mass constraint-only [full180]",
        "internal_mode": "price2014_prefit",
        "candidate_pool": "full180",
        "stage": "PREFIT",
    },
    {
        "display_label": "kinfit-only [full180]",
        "internal_mode": "kinfit_chi2_only",
        "candidate_pool": "full180",
        "stage": "POSTFIT",
    },
    {
        "display_label": "mass constraint-only + q_flavor minimize [signed-flavor-preselected Top10]",
        "internal_mode": "price2014_prefit_bcharge1p00",
        "candidate_pool": "signed-flavor-preselected Top10",
        "stage": "PREFIT",
    },
    {
        "display_label": "q_reco minimize [signed-flavor-preselected Top10]",
        "internal_mode": "authoritative_best_tree",
        "candidate_pool": "signed-flavor-preselected Top10",
        "stage": "POSTFIT",
    },
)
COPIED_METHODS = (
    "mass-constraint-only + signed flavor",
    "kinfit + signed flavor",
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


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fields=None):
    fields = fields or list(rows[0])
    with Path(path).open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def selected_keys(path, expected_hash):
    if sha256(path) != expected_hash:
        raise RuntimeError("selected-common CSV hash mismatch")
    rows = read_csv(path)
    keys = {
        (
            row["source_file_id"], int(row["local_index"]),
            int(row["run_number"]), int(row["event_number"]),
        )
        for row in rows
    }
    if len(rows) != 4730 or len(keys) != 4730:
        raise RuntimeError(f"expected 4730 unique frozen keys, found {len(keys)}")
    return keys


def read_mapping(path, source_id):
    rows = read_csv(path)
    mapping = {}
    for row in rows:
        if row["source_file_id"] != source_id:
            raise RuntimeError(f"{path}: unexpected source id")
        filtered = int(row["filtered_local_index"])
        if filtered in mapping:
            raise RuntimeError(f"{source_id}: duplicate filtered index {filtered}")
        mapping[filtered] = (
            source_id,
            int(row["original_local_index"]),
            int(row["run_number"]),
            int(row["event_number"]),
        )
    if set(mapping) != set(range(len(rows))):
        raise RuntimeError(f"{source_id}: filtered indices are not contiguous")
    return mapping


def validate_first10(full_scores, top10_scores, mapping, source_id):
    compared = 0
    for filtered_index, key in mapping.items():
        original_index = key[1]
        full = full_scores.get(filtered_index, {}).get("combo_ids", [])
        old = top10_scores.get(original_index, {}).get("combo_ids", [])
        if len(full) != 180 or len(set(full)) != 180:
            raise RuntimeError(f"{source_id}: non-full180 payload at {filtered_index}")
        if len(old) != 10 or full[:10] != old:
            raise RuntimeError(f"{source_id}: first-10 overlap failed at {key}")
        compared += 1
    return compared


def build_truth(filtered_lcio, mapping, source_id, rerank, legacy_cm, boundary):
    cfg = rerank.cfg_for_matching(str(filtered_lcio), "OutputErrorFlowJets6")
    cfg["min_truejet_dice"] = math.nextafter(0.0, 1.0)
    reader = legacy_cm.IOIMPL.LCFactory.getInstance().createLCReader()
    reader.open(str(filtered_lcio))
    truth = {}
    counters = Counter()
    index = 0
    try:
        while True:
            event = reader.readNextEvent()
            if not bool(event):
                break
            if index not in mapping:
                raise RuntimeError(f"{source_id}: filtered LCIO has extra event {index}")
            key = mapping[index]
            if (int(event.getRunNumber()), int(event.getEventNumber())) != key[2:]:
                raise RuntimeError(f"{source_id}: filtered LCIO/mapping key mismatch at {index}")
            state, context = boundary.relation_context(
                event, "OutputErrorFlowJets6", legacy_cm
            )
            counters[state] += 1
            if state != "relation_eligible":
                raise RuntimeError(f"{source_id}: frozen common key is not relation eligible: {key}")
            assignment_state, _, _ = boundary.positive_dice_assignment(context, legacy_cm)
            counters[assignment_state] += 1
            if assignment_state != "accepted_six_positive":
                raise RuntimeError(f"{source_id}: frozen common key fails positive-Dice gate: {key}")
            summary = Counter()
            truth_info, matched = rerank.match_semileptonic_event_by_role_source(
                event, context["reco"], cfg, summary, role_source="truejet_direct"
            )
            if truth_info is None or matched is None:
                raise RuntimeError(f"{source_id}: frozen common key has no truth match: {key}")
            flags = {}
            for combo_id, assignment in rerank.ASSIGNMENT_BY_ID.items():
                result = rerank.truth_flags_semileptonic(assignment, matched)
                flags[int(combo_id)] = {
                    "truth_match_W": int(result["W"]),
                    "truth_match_t": int(result["top"]),
                    "truth_match_H": int(result["H"]),
                    "truth_match_all": int(result["all"]),
                }
            truth[index] = flags
            index += 1
    finally:
        reader.close()
    if index != len(mapping):
        raise RuntimeError(f"{source_id}: read {index} filtered events, expected {len(mapping)}")
    return truth, counters


def select_source(source, frozen_keys, rerank, legacy_cm, boundary, price):
    source_id = source["source_file_id"]
    for field in ("full180_root", "top10_root", "filtered_lcio", "mapping_csv"):
        observed = sha256(source[field])
        expected = source[f"{field}_sha256"]
        if observed != expected:
            raise RuntimeError(f"{source_id}: {field} hash mismatch")
    mapping = read_mapping(source["mapping_csv"], source_id)
    if set(mapping.values()) != {key for key in frozen_keys if key[0] == source_id}:
        raise RuntimeError(f"{source_id}: mapping keys differ from frozen selected-common keys")
    full_scores, full_accepted = rerank.read_top_score_map(source["full180_root"])
    top10_scores, _ = rerank.read_top_score_map(source["top10_root"])
    if full_accepted != set(mapping):
        raise RuntimeError(f"{source_id}: full180 accepted indices differ from filtered inputs")
    overlap = validate_first10(full_scores, top10_scores, mapping, source_id)
    rows = rerank.read_candidate_rows(source["full180_root"], source_id, full_scores)
    by_event = defaultdict(list)
    for row in rows:
        by_event[int(row["event_index"])].append(row)
    truth, counters = build_truth(
        source["filtered_lcio"], mapping, source_id, rerank, legacy_cm, boundary
    )
    attached = rerank.attach_scores_and_truth(rows, truth, price)
    attached_by_event = defaultdict(list)
    for row in attached:
        attached_by_event[int(row["event_index"])].append(row)
    selected = {"price2014_prefit": {}, "kinfit_chi2_only": {}}
    event_rows = []
    for filtered_index, key in sorted(mapping.items()):
        candidates = attached_by_event[filtered_index]
        mass_valid = [
            row for row in candidates
            if math.isfinite(rerank.mode_score(row, "price2014_prefit")[0])
        ]
        kinfit_valid = [
            row for row in candidates
            if int(row.get("fit_success", 0)) == 1
            and math.isfinite(rerank.mode_score(row, "kinfit_chi2_only")[0])
        ]
        if not mass_valid or not kinfit_valid:
            raise RuntimeError(f"{source_id}: no valid full180 candidate for {key}")
        mass = min(mass_valid, key=lambda row: rerank.mode_score(row, "price2014_prefit"))
        kinfit = min(kinfit_valid, key=lambda row: rerank.mode_score(row, "kinfit_chi2_only"))
        selected["price2014_prefit"][key] = mass
        selected["kinfit_chi2_only"][key] = kinfit
        event_rows.append(
            {
                "source_file_id": key[0], "original_local_index": key[1],
                "run_number": key[2], "event_number": key[3],
                "filtered_local_index": filtered_index,
                "mass_combo_id": int(mass["combo_id"]),
                "mass_candidate_rank": int(mass["candidate_rank"]),
                "mass_truth_W": int(mass["truth_match_W"]),
                "mass_truth_top": int(mass["truth_match_t"]),
                "mass_truth_H": int(mass["truth_match_H"]),
                "mass_truth_all": int(mass["truth_match_all"]),
                "kinfit_combo_id": int(kinfit["combo_id"]),
                "kinfit_candidate_rank": int(kinfit["candidate_rank"]),
                "kinfit_truth_W": int(kinfit["truth_match_W"]),
                "kinfit_truth_top": int(kinfit["truth_match_t"]),
                "kinfit_truth_H": int(kinfit["truth_match_H"]),
                "kinfit_truth_all": int(kinfit["truth_match_all"]),
            }
        )
    return selected, event_rows, {
        "source_file_id": source_id,
        "events": len(mapping),
        "first10_overlap_events": overlap,
        "candidate_rows": len(rows),
        "positive_dice_events": counters["accepted_six_positive"],
    }


def metric_row(meta, rows):
    denominator = len(rows)
    raw = {
        "W": sum(int(row["truth_match_W"]) for row in rows.values()),
        "top": sum(int(row["truth_match_t"]) for row in rows.values()),
        "H": sum(int(row["truth_match_H"]) for row in rows.values()),
        "all": sum(int(row["truth_match_all"]) for row in rows.values()),
    }
    return {
        **meta, "denominator": str(denominator),
        "W_correct": str(raw["W"]), "top_correct": str(raw["top"]),
        "H_correct": str(raw["H"]), "all_correct": str(raw["all"]),
        "A_W": repr(raw["W"] / denominator),
        "A_top": repr(raw["top"] / denominator),
        "A_H": repr(raw["H"] / denominator),
        "A_all": repr(raw["all"] / denominator),
    }


def copied_rows(path):
    rows = {row["method"]: row for row in read_csv(path)}
    out = []
    for meta, source_method in zip(DISPLAY[2:], COPIED_METHODS):
        source = rows[source_method]
        if source["denominator"] != "4730":
            raise RuntimeError(f"copied Top10 denominator is {source['denominator']}, not 4730")
        out.append({**meta, **{field: source[field] for field in NUMERIC_FIELDS}})
    return out


def plot(rows, png, pdf, plt):
    objects = (("A_W", "W"), ("A_top", "top"), ("A_H", "H"), ("A_all", "all"))
    x = list(range(4))
    width = 0.19
    fig, ax = plt.subplots(figsize=(15, 7), dpi=180)
    for offset, (field, label) in enumerate(objects):
        positions = [value + (offset - 1.5) * width for value in x]
        bars = ax.bar(positions, [float(row[field]) for row in rows], width, label=label)
        ax.bar_label(bars, fmt="%.3f", fontsize=8, padding=2)
    ax.set_xticks(x)
    ax.set_xticklabels([row["display_label"] for row in rows], rotation=11, ha="right")
    ax.set_ylim(0.0, 0.9)
    ax.set_ylabel("assignment accuracy")
    ax.set_title("Whizard eL.pR jet-assignment accuracy; fixed common 4730-event denominator")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(ncol=4)
    fig.tight_layout()
    fig.savefig(png, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selected-common-csv", type=Path, required=True)
    parser.add_argument("--expected-selected-common-sha256", required=True)
    parser.add_argument("--current-accuracy-csv", type=Path, required=True)
    parser.add_argument("--expected-current-accuracy-sha256", required=True)
    parser.add_argument("--sources-json", type=Path, required=True)
    parser.add_argument("--legacy-rerank", type=Path, required=True)
    parser.add_argument("--legacy-cm", type=Path, required=True)
    parser.add_argument("--chi2-module-dir", type=Path, required=True)
    parser.add_argument("--model-bundle", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() or args.output_dir.is_symlink():
        raise RuntimeError(f"refusing to reuse output directory: {args.output_dir}")
    if sha256(args.current_accuracy_csv) != args.expected_current_accuracy_sha256:
        raise RuntimeError("current Top10 accuracy CSV hash mismatch")
    frozen_keys = selected_keys(
        args.selected_common_csv, args.expected_selected_common_sha256
    )
    sys.path.insert(0, str(args.chi2_module_dir.resolve(strict=True)))
    rerank = load_module("frozen_full180_rerank", args.legacy_rerank.resolve(strict=True))
    legacy_cm = load_module("frozen_full180_cm", args.legacy_cm.resolve(strict=True))
    boundary = load_module(
        "full180_positive_dice_boundary",
        Path(__file__).resolve().with_name("report_whizard_jet_cm.py"),
    )
    price = rerank.load_price2014(str(args.model_bundle.resolve(strict=True)))
    sources = json.loads(args.sources_json.read_text(encoding="utf-8"))["sources"]
    selected = {"price2014_prefit": {}, "kinfit_chi2_only": {}}
    event_rows = []
    source_summaries = []
    for source in sources:
        source_selected, source_events, summary = select_source(
            source, frozen_keys, rerank, legacy_cm, boundary, price
        )
        for mode in selected:
            overlap = set(selected[mode]) & set(source_selected[mode])
            if overlap:
                raise RuntimeError(f"duplicate source-aware keys: {sorted(overlap)[:2]}")
            selected[mode].update(source_selected[mode])
        event_rows.extend(source_events)
        source_summaries.append(summary)
    if any(set(rows) != frozen_keys for rows in selected.values()):
        raise RuntimeError("full180 selections do not cover the exact common4730 key set")
    metrics = [metric_row(meta, selected[meta["internal_mode"]]) for meta in DISPLAY[:2]]
    metrics.extend(copied_rows(args.current_accuracy_csv))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    args.output_dir.mkdir(parents=True)
    csv_path = args.output_dir / "assignment_accuracy_common4730_full180_first2.csv"
    json_path = args.output_dir / "assignment_accuracy_common4730_full180_first2.json"
    events_path = args.output_dir / "full180_selected_events.csv"
    png = args.output_dir / "assignment_accuracy_common4730_full180_first2.png"
    pdf = args.output_dir / "assignment_accuracy_common4730_full180_first2.pdf"
    fields = [*DISPLAY[0], *NUMERIC_FIELDS]
    write_csv(csv_path, metrics, fields)
    write_csv(events_path, event_rows)
    plot(metrics, png, pdf, plt)
    payload = {
        "denominator": 4730,
        "event_key": list(KEY_FIELDS),
        "metrics": metrics,
        "source_summaries": source_summaries,
        "last_two_numeric_fields_copied_from_top10": True,
        "selected_common_sha256": sha256(args.selected_common_csv),
        "current_accuracy_sha256": sha256(args.current_accuracy_csv),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    outputs = (csv_path, json_path, events_path, png, pdf)
    manifest = {
        "status": "Whizard fixed-common4730 correction: full180 only for first two modes",
        "contract": {
            "first_two_candidate_pool": "all 180 base assignments; all SLD rows retained",
            "mass_mode": "price2014_prefit over all rows without fit-success requirement",
            "kinfit_mode": "kinfit_chi2_only over fit_success=1 rows",
            "truth_collection": "OutputErrorFlowJets6",
            "truth_gate": "all six assigned Dice values strictly greater than zero",
            "last_two": "numeric fields copied unchanged from frozen Top10 common4730 CSV",
        },
        "command": [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
        "script": {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
        "sources_json": {"path": str(args.sources_json.resolve()), "sha256": sha256(args.sources_json)},
        "selected_common_csv": {"path": str(args.selected_common_csv.resolve()), "sha256": sha256(args.selected_common_csv)},
        "current_accuracy_csv": {"path": str(args.current_accuracy_csv.resolve()), "sha256": sha256(args.current_accuracy_csv)},
        "legacy_rerank": {"path": str(args.legacy_rerank.resolve()), "sha256": sha256(args.legacy_rerank)},
        "legacy_cm": {"path": str(args.legacy_cm.resolve()), "sha256": sha256(args.legacy_cm)},
        "model_bundle": {"path": str(args.model_bundle.resolve()), "sha256": sha256(args.model_bundle)},
        "outputs": {path.name: {"path": str(path), "sha256": sha256(path)} for path in outputs},
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"metrics": metrics, "output_dir": str(args.output_dir)}, sort_keys=True))


if __name__ == "__main__":
    main()
