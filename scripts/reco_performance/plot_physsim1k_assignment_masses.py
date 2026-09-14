#!/usr/bin/env python3
"""Reproduce the frozen Physsim-1k assignment-mass diagnostic."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

SOURCE_ID = "physsim_eLpR_chunk0_first1000_hbb_semilep_emu"
SOURCE_MODE = "sld_enumeration"
EXPECTED_FILTERED_EVENTS = 159
EXPECTED_COMMON = 150
BINS = 60
PRICE_MODE = "price2014_prefit_bcharge1p00"
KINFIT_MODE = "logchi2_plus_flavor_x0p3"
MODES = (PRICE_MODE, KINFIT_MODE)
TITLE = "Historical Physsim 1k validation; TopN10 SLD1 SA2.6 offline rerank"
DISCLAIMER = "Assignment truth not evaluated; no assignment-accuracy claim"
MODE_SPECS = {
    PRICE_MODE: {
        "label": "Price2014 + signed flavor (PREFIT)",
        "color": "#2364aa",
        "columns": {"W": "mW_had_prefit", "top": "mt_had_prefit", "H": "mH_prefit"},
    },
    KINFIT_MODE: {
        "label": "Kinfit + signed flavor (POSTFIT)",
        "color": "#d95f02",
        "columns": {"W": "mW_had_postfit", "top": "mt_had_postfit", "H": "mH_postfit"},
    },
}
OBJECT_SPECS = {
    "W": {"range": (40.0, 130.0), "target": 80.4},
    "top": {"range": (100.0, 240.0), "target": 172.5},
    "H": {"range": (40.0, 210.0), "target": 125.0},
}
TOP_REQUIRED_BRANCHES = {
    "event_index",
    "top_combo_ids",
    "top_preselect_scores",
    "best_combo_id",
}
CANDIDATE_REQUIRED_BRANCHES = {
    "event_index",
    "candidate_rank",
    "combo_id",
    "fit_status",
    "fit_success",
    "fitprob",
    "fitchi2",
    "mW_had_prefit",
    "mt_had_prefit",
    "mH_prefit",
    "mW_had_postfit",
    "mt_had_postfit",
    "mt_lep_postfit",
    "mH_postfit",
    "post4c_residual_px",
    "post4c_residual_py",
    "post4c_residual_pz",
    "post4c_residual_E",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assert_new_output_dir(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise RuntimeError(f"refusing to reuse output directory: {path}")


def histogram_accounting(
    values: list[float], low: float, high: float, bins: int, denominator: int
) -> dict[str, object]:
    if denominator <= 0 or bins <= 0 or high <= low:
        raise ValueError("invalid histogram definition")
    counts = [0] * bins
    underflow = 0
    overflow = 0
    width = (high - low) / bins
    for value in values:
        if value < low:
            underflow += 1
        elif value > high:
            overflow += 1
        else:
            index = bins - 1 if value == high else int((value - low) / width)
            counts[index] += 1
    in_range = sum(counts)
    closure = underflow + in_range + overflow
    if closure != len(values):
        raise RuntimeError("histogram accounting does not close to input values")
    return {
        "counts": counts,
        "edges": [low + index * width for index in range(bins + 1)],
        "underflow": underflow,
        "in_range": in_range,
        "overflow": overflow,
        "closure_count": closure,
        "underflow_fraction": underflow / denominator,
        "in_range_fraction": in_range / denominator,
        "overflow_fraction": overflow / denominator,
        "closure_fraction": closure / denominator,
    }


def load_legacy(path: Path, chi2_dir: Path):
    sys.path.insert(0, str(chi2_dir.resolve(strict=True)))
    spec = importlib.util.spec_from_file_location("frozen_physsim_rerank", path.resolve(strict=True))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_root_schema(root_path: Path, legacy) -> dict[str, object]:
    handle = legacy.ROOT.TFile.Open(str(root_path))
    if not handle or handle.IsZombie():
        raise RuntimeError(f"cannot open ROOT file: {root_path}")
    try:
        top = handle.Get("TTHSemiLepKinFit")
        candidates = handle.Get("TTHSemiLepKinFit_candidates")
        if top is None or candidates is None:
            raise RuntimeError("missing TTHSemiLepKinFit or TTHSemiLepKinFit_candidates")
        top_branches = legacy.branch_names(top)
        candidate_branches = legacy.branch_names(candidates)
        missing_top = sorted(TOP_REQUIRED_BRANCHES - top_branches)
        missing_candidates = sorted(CANDIDATE_REQUIRED_BRANCHES - candidate_branches)
        if missing_top or missing_candidates:
            raise RuntimeError(
                f"ROOT schema missing top={missing_top}, candidates={missing_candidates}"
            )
        return {
            "top_entries": int(top.GetEntries()),
            "candidate_entries": int(candidates.GetEntries()),
            "top_required_branches": sorted(TOP_REQUIRED_BRANCHES),
            "candidate_required_branches": sorted(CANDIDATE_REQUIRED_BRANCHES),
        }
    finally:
        handle.Close()


def particle_mass(particle) -> float:
    energy = float(particle.getEnergy())
    momentum = particle.getMomentum()
    momentum2 = sum(float(momentum[index]) ** 2 for index in range(3))
    mass2 = energy * energy - momentum2
    if mass2 < -1.0e-8:
        raise RuntimeError(f"parent four-vector has negative mass squared: {mass2}")
    return math.sqrt(max(0.0, mass2))


def build_truth_and_source_map(filtered_lcio: Path, legacy) -> dict[int, dict[str, object]]:
    cfg = {
        "mc_collection": "MCParticlesSkimmed",
        "allowed_truth_leptons": ["e", "mu"],
    }
    mapping: dict[int, dict[str, object]] = {}
    seen_source_keys = set()
    for _, local_index, global_index, run, event, evt in legacy.chi2_reco.iter_lcio_events(
        [str(filtered_lcio)], max_events=None
    ):
        if local_index != global_index or global_index in mapping:
            raise RuntimeError(f"filtered LCIO event-index mapping is not one-to-one at {global_index}")
        source_key = (SOURCE_ID, int(run), int(event))
        if source_key in seen_source_keys:
            raise RuntimeError(f"duplicate source-aware key: {source_key}")
        seen_source_keys.add(source_key)
        truth = legacy.chi2_reco.truth_event_info(evt, cfg)
        if truth is None:
            raise RuntimeError(f"filtered LCIO event_index={global_index} fails frozen truth topology")
        masses = {
            "W": particle_mass(truth["had_w"]),
            "top": particle_mass(truth["had_top"]),
            "H": particle_mass(truth["higgs"]),
        }
        if not all(math.isfinite(value) for value in masses.values()):
            raise RuntimeError(f"non-finite parent truth mass at event_index={global_index}")
        mapping[int(global_index)] = {
            "source_file_id": SOURCE_ID,
            "run": int(run),
            "event": int(event),
            "truth": masses,
        }
    if len(mapping) != EXPECTED_FILTERED_EVENTS:
        raise RuntimeError(
            f"filtered LCIO has {len(mapping)} readable events, expected {EXPECTED_FILTERED_EVENTS}"
        )
    return mapping


def unique_by_event(rows: list[dict], mode: str) -> dict[int, dict]:
    out = {}
    for row in rows:
        event_index = int(row["event_index"])
        if event_index in out:
            raise RuntimeError(f"duplicate selected row for mode={mode}, event_index={event_index}")
        out[event_index] = row
    return out


def build_presence_only_assignment_map(
    candidate_rows: list[dict],
) -> tuple[dict[int, dict[int, dict[str, str]]], dict[str, int]]:
    presence = defaultdict(dict)
    pairs = set()
    for row in candidate_rows:
        event_index = int(row["event_index"])
        combo_id = int(row["combo_id"])
        pairs.add((event_index, combo_id))
        presence[event_index][combo_id] = {
            "assignment_truth_status": "not_evaluated_for_mass_plot"
        }
    for row in candidate_rows:
        payload = presence[int(row["event_index"])][int(row["combo_id"])]
        if payload != {"assignment_truth_status": "not_evaluated_for_mass_plot"}:
            raise RuntimeError("candidate presence map payload changed")
    return presence, {
        "presence_map_events": len(presence),
        "presence_map_event_combo_pairs": len(pairs),
    }


def validate_common_selection(
    selected_by_mode: dict[str, list[dict]],
    truth_by_event: dict[int, dict[str, object]],
    expected_common: int = EXPECTED_COMMON,
) -> tuple[dict[str, dict[int, dict]], list[int]]:
    indexed = {mode: unique_by_event(selected_by_mode.get(mode, []), mode) for mode in MODES}
    common = sorted(set(indexed[PRICE_MODE]) & set(indexed[KINFIT_MODE]) & set(truth_by_event))
    if len(common) != expected_common:
        raise RuntimeError(f"common finite-truth intersection has {len(common)}, expected {expected_common}")
    for event_index in common:
        source = truth_by_event[event_index]
        if not all(math.isfinite(float(source["truth"][obj])) for obj in OBJECT_SPECS):
            raise RuntimeError(f"non-finite truth mass at event_index={event_index}")
        for mode, spec in MODE_SPECS.items():
            row = indexed[mode][event_index]
            for column in spec["columns"].values():
                if not math.isfinite(float(row[column])):
                    raise RuntimeError(
                        f"non-finite {column} for mode={mode}, event_index={event_index}"
                    )
    if any(int(row.get("fit_success", 0)) != 1 for row in indexed[KINFIT_MODE].values()):
        raise RuntimeError("kinfit selection contains a fit_success != 1 row")
    return indexed, common


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_plot(histograms: dict, output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(13.4, 4.3))
    for axis, (obj, object_spec) in zip(axes, OBJECT_SPECS.items()):
        for curve, label, color in (
            (PRICE_MODE, MODE_SPECS[PRICE_MODE]["label"], MODE_SPECS[PRICE_MODE]["color"]),
            (KINFIT_MODE, MODE_SPECS[KINFIT_MODE]["label"], MODE_SPECS[KINFIT_MODE]["color"]),
            ("truth", "Physsim generator truth (parent p4)", "#2a9d8f"),
        ):
            payload = histograms[obj][curve]
            heights = [count / EXPECTED_COMMON for count in payload["counts"]]
            axis.stairs(heights, payload["edges"], linewidth=2.0, color=color, label=label)
        axis.axvline(
            object_spec["target"],
            color="#666666",
            linestyle=":",
            linewidth=1.2,
            label="nominal reference",
        )
        axis.set_xlim(*object_spec["range"])
        axis.set_title(obj)
        axis.set_xlabel(f"{obj} mass [GeV]")
        axis.grid(alpha=0.25)
    axes[0].set_ylabel("fraction of common events / bin")
    axes[-1].legend(fontsize=7.8)
    fig.suptitle(f"{TITLE}\n{DISCLAIMER}")
    fig.tight_layout()
    fig.savefig(output.with_suffix(".png"), dpi=180)
    fig.savefig(output.with_suffix(".pdf"))
    plt.close(fig)


def run(args: argparse.Namespace) -> dict[str, object]:
    assert_new_output_dir(args.output_dir)
    legacy = load_legacy(args.legacy, args.chi2_dir)
    schema = validate_root_schema(args.candidate_root, legacy)
    truth_by_event = build_truth_and_source_map(args.filtered_lcio, legacy)

    top_scores, accepted_events = legacy.read_top_score_map(str(args.candidate_root))
    root_indices = set(top_scores)
    if set(accepted_events) != root_indices or not root_indices.issubset(truth_by_event):
        raise RuntimeError("ROOT accepted event indices do not map one-to-one into filtered LCIO")
    candidate_rows = legacy.read_candidate_rows(
        str(args.candidate_root), SOURCE_MODE, top_scores
    )
    candidate_indices = {int(row["event_index"]) for row in candidate_rows}
    if candidate_indices != root_indices:
        raise RuntimeError("ROOT candidate event indices do not match accepted ROOT event indices")
    flavor_priors, flavor_counters = legacy.build_flavor_prior_map(
        str(args.filtered_lcio), set(accepted_events), "RefinedJets6"
    )
    presence_map, presence_counters = build_presence_only_assignment_map(candidate_rows)
    attached = legacy.attach_scores_and_truth(
        candidate_rows,
        presence_map,
        legacy.load_price2014(str(args.model_bundle)),
        flavor_priors,
    )
    if len(candidate_rows) != 4380 or len(attached) != 4380:
        raise RuntimeError(
            f"candidate/attached row count is {len(candidate_rows)}/{len(attached)}, expected 4380/4380"
        )
    if any(key.startswith("truth_match_") for row in attached for key in row):
        raise RuntimeError("assignment truth fields entered mass-only rerank rows")
    grouped = defaultdict(list)
    for row in attached:
        grouped[int(row["event_index"])].append(row)
    selected_by_mode = {mode: [] for mode in MODES}
    for event_index, event_rows in grouped.items():
        best = legacy.select_best_by_mode(event_rows, MODES, require_converged=False)
        for mode, row in best.items():
            payload = dict(row)
            payload.update(truth_by_event[event_index])
            selected_by_mode[mode].append(payload)

    indexed, common = validate_common_selection(selected_by_mode, truth_by_event)
    if len(indexed[PRICE_MODE]) != EXPECTED_COMMON or len(indexed[KINFIT_MODE]) != EXPECTED_COMMON:
        raise RuntimeError(
            f"selected counts are {len(indexed[PRICE_MODE])}/{len(indexed[KINFIT_MODE])}, expected 150/150"
        )
    combo_differences = sum(
        int(indexed[PRICE_MODE][event]["combo_id"] != indexed[KINFIT_MODE][event]["combo_id"])
        for event in common
    )
    price_fit_success = sum(
        int(row.get("fit_success", 0)) == 1 for row in indexed[PRICE_MODE].values()
    )
    kinfit_failed = sum(
        int(row.get("fit_success", 0)) != 1 for row in indexed[KINFIT_MODE].values()
    )
    if kinfit_failed != 0:
        raise RuntimeError(f"kinfit selection contains {kinfit_failed} failed-fit rows")
    flavor_source_rows = defaultdict(int)
    flavor_source_events = defaultdict(set)
    for row in attached:
        source = str(row["flavor_score_source"])
        flavor_source_rows[source] += 1
        flavor_source_events[source].add(int(row["event_index"]))

    joined_rows = []
    for event_index in common:
        source = truth_by_event[event_index]
        price_row = indexed[PRICE_MODE][event_index]
        kinfit_row = indexed[KINFIT_MODE][event_index]
        joined_rows.append(
            {
                "source_file_id": source["source_file_id"],
                "run": source["run"],
                "event": source["event"],
                "event_index": event_index,
                "price_combo_id": price_row["combo_id"],
                "kinfit_combo_id": kinfit_row["combo_id"],
                "price_fit_success": price_row["fit_success"],
                "kinfit_fit_success": kinfit_row["fit_success"],
                "mW_had_prefit": price_row["mW_had_prefit"],
                "mt_had_prefit": price_row["mt_had_prefit"],
                "mH_prefit": price_row["mH_prefit"],
                "mW_had_postfit": kinfit_row["mW_had_postfit"],
                "mt_had_postfit": kinfit_row["mt_had_postfit"],
                "mH_postfit": kinfit_row["mH_postfit"],
                "mW_truth_parent_p4": source["truth"]["W"],
                "mt_truth_parent_p4": source["truth"]["top"],
                "mH_truth_parent_p4": source["truth"]["H"],
            }
        )

    histograms = {}
    summary_rows = []
    for obj, object_spec in OBJECT_SPECS.items():
        histograms[obj] = {}
        low, high = object_spec["range"]
        for curve in (PRICE_MODE, KINFIT_MODE, "truth"):
            if curve == "truth":
                values = [float(truth_by_event[event]["truth"][obj]) for event in common]
            else:
                column = MODE_SPECS[curve]["columns"][obj]
                values = [float(indexed[curve][event][column]) for event in common]
            accounting = histogram_accounting(values, low, high, BINS, EXPECTED_COMMON)
            histograms[obj][curve] = accounting
            summary_rows.append(
                {
                    "object": obj,
                    "curve": curve,
                    "events": len(values),
                    "underflow": accounting["underflow"],
                    "in_range": accounting["in_range"],
                    "overflow": accounting["overflow"],
                    "closure_count": accounting["closure_count"],
                    "closure_fraction": accounting["closure_fraction"],
                    "median": legacy.quantile(values, 0.5),
                }
            )

    args.output_dir.mkdir(parents=True)
    selected_rows = []
    for mode in MODES:
        selected_rows.extend(sorted(indexed[mode].values(), key=lambda row: int(row["event_index"])))
    write_csv(args.output_dir / "rerank_selected.csv", selected_rows)
    write_csv(args.output_dir / "joined_common_events.csv", joined_rows)
    write_csv(args.output_dir / "summary.csv", summary_rows)
    plot_prefix = args.output_dir / "physsim1k_price_prefit_vs_kinfit_postfit_truth"
    render_plot(histograms, plot_prefix)

    output_paths = [
        plot_prefix.with_suffix(".png"),
        plot_prefix.with_suffix(".pdf"),
        args.output_dir / "rerank_selected.csv",
        args.output_dir / "joined_common_events.csv",
        args.output_dir / "summary.csv",
    ]
    manifest = {
        "title": TITLE,
        "assignment_truth_statement": DISCLAIMER,
        "source_file_id": SOURCE_ID,
        "source_mode": SOURCE_MODE,
        "require_converged": False,
        "jet_collection": "OutputErrorFlowJets6",
        "flavor_jet_collection": "RefinedJets6",
        "role_source": "truejet_direct",
        "upstream_complete_reco": str(args.upstream_complete_reco),
        "filtered_lcio": str(args.filtered_lcio),
        "candidate_root": str(args.candidate_root),
        "model_bundle": str(args.model_bundle),
        "input_sha256": {
            "upstream_complete_reco": sha256(args.upstream_complete_reco),
            "filtered_lcio": sha256(args.filtered_lcio),
            "candidate_root": sha256(args.candidate_root),
            "model_bundle": sha256(args.model_bundle),
        },
        "root_schema": schema,
        "filtered_events": len(truth_by_event),
        "candidate_rows": len(candidate_rows),
        "rows_after_attach": len(attached),
        **presence_counters,
        "selected_counts": {mode: len(indexed[mode]) for mode in MODES},
        "common_events": len(common),
        "price_selected_fit_success": price_fit_success,
        "price_selected_failed_fit": len(indexed[PRICE_MODE]) - price_fit_success,
        "kinfit_selected_fit_success": sum(
            int(row["fit_success"]) == 1 for row in indexed[KINFIT_MODE].values()
        ),
        "kinfit_selected_failed_fit": kinfit_failed,
        "flavor_score_source_rows": dict(flavor_source_rows),
        "flavor_score_source_events": {
            source: len(events) for source, events in flavor_source_events.items()
        },
        "differing_combo_id_events": combo_differences,
        "flavor_counters": dict(flavor_counters),
        "truth_medians": {
            obj: legacy.quantile([truth_by_event[event]["truth"][obj] for event in common], 0.5)
            for obj in OBJECT_SPECS
        },
        "histogram_accounting": histograms,
        "outputs": {path.name: {"path": str(path), "sha256": sha256(path)} for path in output_paths},
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-complete-reco", type=Path, required=True)
    parser.add_argument("--filtered-lcio", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--model-bundle", type=Path, required=True)
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--chi2-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = run(args)
    print(
        json.dumps(
            {
                "common_events": manifest["common_events"],
                "differing_combo_id_events": manifest["differing_combo_id_events"],
                "output_dir": str(args.output_dir),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
