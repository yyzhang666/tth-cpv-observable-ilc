#!/usr/bin/env python3
"""Report event-level truth composition after exactly-one-lepton selection."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path


EXPECTED_EVENTS = 124982
FOUR_CLASSES = (
    "direct_semilep_emu",
    "semilep_tau",
    "fully_hadronic",
    "dileptonic",
)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_legacy(path):
    spec = importlib.util.spec_from_file_location("legacy_had_truth_composition", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def open_reader(path):
    from pyLCIO import IOIMPL

    reader = IOIMPL.LCFactory.getInstance().createLCReader()
    reader.open(str(path))
    return reader


def four_class(channel):
    if channel in ("semilep_e", "semilep_mu"):
        return "direct_semilep_emu"
    return {
        "semilep_tau": "semilep_tau",
        "had": "fully_hadronic",
        "dilep": "dileptonic",
    }.get(channel)


def scan_tagger(complete_paths, legacy, max_events=-1, reader_opener=open_reader):
    counts = Counter()
    processed = 0
    selected_hbb_all = 0
    missing_collections = 0
    for path in complete_paths:
        reader = reader_opener(path)
        try:
            while max_events < 0 or processed < max_events:
                event = reader.readNextEvent()
                if not event:
                    break
                processed += 1
                if legacy.truth_h_to_bb(event, colMC="MCParticlesSkimmed") is not True:
                    continue
                mu_name, nmu = legacy.get_n_reco(
                    event, "ISOMuons", ["ISOMuons", "IsolatedMuons"]
                )
                el_name, nel = legacy.get_n_reco(
                    event, "ISOElectrons", ["ISOElectrons", "IsolatedElectrons"]
                )
                if mu_name is None or el_name is None:
                    missing_collections += 1
                    continue
                if nmu + nel != 1:
                    continue
                selected_hbb_all += 1
                channel, _ = legacy.truth_ttbar_channel_and_tau(
                    event, colMC="MCParticlesSkimmed"
                )
                category = four_class(channel)
                if category is not None:
                    counts[category] += 1
                elif channel == "semilep_lep":
                    counts["semilep_lep"] += 1
                else:
                    counts["unclassified"] += 1
        finally:
            reader.close()
        if max_events >= 0 and processed >= max_events:
            break
    result = method_result(
        "Tagger",
        counts,
        selected_hbb_all=selected_hbb_all,
        semilep_lep=counts["semilep_lep"],
        unclassified=counts["unclassified"],
    )
    result["events_processed"] = processed
    result["missing_required_collection_events"] = missing_collections
    return result


def finder_from_counts(payload):
    multiplicity = payload.get("multiplicity", {})
    if multiplicity.get("events_processed") != EXPECTED_EVENTS:
        raise RuntimeError(
            f"Finder JSON events_processed must be {EXPECTED_EVENTS}, got "
            f"{multiplicity.get('events_processed')}"
        )
    blocks = multiplicity.get("semileptonic_logic", {})
    source_categories = {
        "direct_semilep_emu": ("semilep_e", "semilep_mu"),
        "semilep_tau": ("semilep_tau",),
        "fully_hadronic": ("had",),
        "dileptonic": ("dilep",),
    }
    counts = Counter()
    denominators = {}
    for target, categories in source_categories.items():
        for category in categories:
            key = f"HBB|{category}"
            if key not in blocks:
                raise RuntimeError(f"Finder JSON missing required category block {key}")
            block = blocks[key]
            if "n" not in block or "cnt" not in block:
                raise RuntimeError(f"Finder JSON category block is incomplete: {key}")
            denominators[key] = int(block["n"])
            counts[target] += int(block["cnt"].get("Isolep==1", 0))
    semilep_lep_key = "HBB|semilep_lep"
    if semilep_lep_key in blocks:
        semilep_lep = int(blocks[semilep_lep_key]["cnt"].get("Isolep==1", 0))
        semilep_lep_status = "recorded"
    else:
        semilep_lep = 0
        semilep_lep_status = "tracked_block_absent_zero"
    result = method_result(
        "Finder",
        counts,
        selected_hbb_all=None,
        semilep_lep=semilep_lep,
        unclassified=None,
    )
    result.update(
        {
            "events_processed": EXPECTED_EVENTS,
            "source_category_denominators": denominators,
            "semilep_lep_status": semilep_lep_status,
            "unclassified_status": "not_recorded_by_source_JSON",
            "overall_closure": None,
        }
    )
    return result


def method_result(method, counts, selected_hbb_all, semilep_lep, unclassified):
    raw = {category: int(counts.get(category, 0)) for category in FOUR_CLASSES}
    denominator = sum(raw.values())
    if denominator <= 0:
        raise RuntimeError(f"zero four-class denominator for {method}")
    percentages = {
        category: 100.0 * count / denominator for category, count in raw.items()
    }
    percentage_sum = sum(percentages.values())
    if abs(percentage_sum - 100.0) > 1e-9:
        raise RuntimeError(f"four-class percentages do not close for {method}: {percentage_sum}")
    if selected_hbb_all is not None:
        expected = denominator + int(semilep_lep) + int(unclassified)
        if selected_hbb_all != expected:
            raise RuntimeError(
                f"selected HBB closure failed for {method}: {selected_hbb_all} != {expected}"
            )
        overall_closure = True
    else:
        overall_closure = None
    return {
        "method": method,
        "selected_total_4class": denominator,
        "raw_counts": raw,
        "percent_of_method_4class": percentages,
        "percentage_sum": percentage_sum,
        "selected_hbb_all": selected_hbb_all,
        "semilep_lep": semilep_lep,
        "unclassified": unclassified,
        "overall_closure": overall_closure,
    }


def write_outputs(output_dir, tagger, finder, inputs):
    output_dir = Path(output_dir).resolve(strict=False)
    if output_dir.exists() or output_dir.is_symlink():
        raise RuntimeError(f"refusing to reuse output directory: {output_dir}")
    output_dir.mkdir(parents=True)
    payload = {
        "selection": {
            "truth": "H_to_bb",
            "tagger": "n(ISOElectrons)+n(ISOMuons)==1",
            "finder": "Isolep==1_from_existing_lepton_counts_JSON",
            "denominator": "selected_total_4class_per_method",
            "candidate_origin_purity_used": False,
        },
        "inputs": inputs,
        "methods": [tagger, finder],
    }
    (output_dir / "lepton_selection_truth_composition.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    fieldnames = (
        "method",
        "category",
        "raw_count",
        "selected_total_4class",
        "percent_of_method_4class",
        "percentage_sum",
        "selected_hbb_all",
        "semilep_lep",
        "unclassified",
        "overall_closure",
    )
    with (output_dir / "lepton_selection_truth_composition.csv").open(
        "x", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for method in (tagger, finder):
            for category in FOUR_CLASSES:
                writer.writerow(
                    {
                        "method": method["method"],
                        "category": category,
                        "raw_count": method["raw_counts"][category],
                        "selected_total_4class": method["selected_total_4class"],
                        "percent_of_method_4class": (
                            f"{method['percent_of_method_4class'][category]:.6f}"
                        ),
                        "percentage_sum": f"{method['percentage_sum']:.6f}",
                        "selected_hbb_all": method["selected_hbb_all"],
                        "semilep_lep": method["semilep_lep"],
                        "unclassified": method["unclassified"],
                        "overall_closure": method["overall_closure"],
                    }
                )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--complete", type=Path, action="append", required=True)
    parser.add_argument("--counts-json", type=Path, required=True)
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-events", type=int, default=-1)
    args = parser.parse_args()
    if args.max_events == 0 or args.max_events < -1:
        raise ValueError("max-events must be -1 or positive")
    if len(args.complete) != 10:
        raise ValueError("exactly ten canonical complete-reco inputs are required")
    complete_paths = [path.resolve(strict=True) for path in args.complete]
    counts_path = args.counts_json.resolve(strict=True)
    legacy_path = args.legacy.resolve(strict=True)
    legacy = load_legacy(legacy_path)
    tagger = scan_tagger(complete_paths, legacy, args.max_events)
    if args.max_events < 0 and tagger["events_processed"] != EXPECTED_EVENTS:
        raise RuntimeError(
            f"Tagger complete-reco scan processed {tagger['events_processed']} "
            f"events, expected {EXPECTED_EVENTS}"
        )
    finder = finder_from_counts(json.loads(counts_path.read_text(encoding="utf-8")))
    write_outputs(
        args.output_dir,
        tagger,
        finder,
        {
            "complete_reco": [str(path) for path in complete_paths],
            "counts_json": {"path": str(counts_path), "sha256": sha256(counts_path)},
            "legacy": {"path": str(legacy_path), "sha256": sha256(legacy_path)},
        },
    )


if __name__ == "__main__":
    main()
