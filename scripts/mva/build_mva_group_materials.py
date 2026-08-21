#!/usr/bin/env python3
"""Read-only builder for MVA group-meeting evidence."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np

CATEGORIES = ("tth-hbb", "tth-nonbb", "ttz", "ttbb", "6q", "4f2l")
BACKGROUNDS = set(CATEGORIES) - {"tth-hbb"}


def validate_stratified_coverage(rows: list[dict[str, Any]], expected: set[tuple[str, str]]) -> None:
    observed = {(str(row["normalization_key"]), str(row["category"])) for row in rows}
    missing = sorted(expected - observed)
    if missing:
        raise RuntimeError("EXACT_MODE_MISSING_NORMALIZATION_CATEGORY_COVERAGE: " + repr(missing))

try:
    from .selection_mva_common import decode, load_authority, selected_job_keys, validate_job_hdf5, sha256_file
except ImportError:
    from selection_mva_common import decode, load_authority, selected_job_keys, validate_job_hdf5, sha256_file


def read_json(path: Path) -> dict[str, Any]:
    with path.open() as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return value


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def load_table(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.is_file():
        return []
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def sample_cutflow(authority: Any, manifest_path: Path | None, production_path: Path | None,
                   exact: list[dict[str, Any]] | None, threshold: float, source_counts: dict[str, tuple[int, int, int]]) -> list[dict[str, Any]]:
    manifest = load_table(manifest_path)
    production: dict[str, dict[str, Any]] = {}
    if production_path and production_path.is_file():
        payload = read_json(production_path)
        for row in payload.get("jobs", payload.get("records", [])):
            if row.get("job_key"):
                production[str(row["job_key"])] = row
    output = []
    for sample in ("tth-sm", "ttz", "ttbb", "6q", "4f2l", "tth-cpv"):
        jobs = [row for row in authority.catalog_jobs.values() if str(row.get("sample_key")) == sample]
        input_readable = sum(int(float(row.get("input_readable_events", 0) or 0)) for row in manifest if str(row.get("sample_key")) == sample)
        exported = sum(int(row.get("n_events", 0)) for row in jobs)
        test_rows = [row for row in (exact or []) if row["sample_key"] == sample]
        reco_input, accepted, fit = source_counts.get(sample, ("", "", ""))
        denominator_stage = "niso1_reco_skim" if sample in {"6q", "4f2l"} else "all_channel_complete_reco"
        base = {"sample": sample, "denominator_stage": denominator_stage,
                "reco_input_denominator": reco_input, "accepted_events": accepted,
                "fit_success_events": fit, "manifest_input_readable": input_readable,
                "hdf5_exported": exported, "test_events": len(test_rows),
                "threshold_pass": sum(row["score"] >= threshold for row in test_rows),
                "status": "exact" if exact is not None else "test_evaluation_only; frozen handoff counts"}
        output.append(base)
        if sample == "tth-sm":
            for category in ("tth-hbb", "tth-nonbb"):
                subset = [row for row in test_rows if row["category"] == category]
                category_exported = sum(
                    int(row.get("analysis_category_counts", {}).get(category, 0))
                    for row in jobs
                )
                output.append({**base, "sample": f"tth-sm/{category}",
                               "reco_input_denominator": "", "accepted_events": "",
                               "fit_success_events": "", "manifest_input_readable": "",
                               "hdf5_exported": category_exported,
                               "test_events": len(subset),
                               "threshold_pass": sum(row["score"] >= threshold for row in subset)})
    return output


def parse_cutflow_source(path: Path) -> dict[str, tuple[int, int, int]]:
    if not path.is_file():
        raise RuntimeError(f"Missing cutflow source: {path}")
    result: dict[str, tuple[int, int, int]] = {}
    sample_pattern = re.compile(r"(?:`)?(tth-sm|tth-cpv|ttz|ttbb|6q|4f2l|4q2l)(?:`)?")
    for line in path.read_text().splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if cells and not cells[0]: cells.pop(0)
        if cells and not cells[-1]: cells.pop()
        if len(cells) < 5:
            continue
        match = sample_pattern.search(cells[0])
        if match:
            try:
                values = tuple(int(re.sub(r"[^0-9]", "", cells[i])) for i in (2, 3, 4))
            except ValueError:
                continue
            sample = "4f2l" if match.group(1) == "4q2l" else match.group(1)
            if sample in result and result[sample] != values:
                raise RuntimeError(f"Conflicting 4q2l/4f2l cutflow rows in {path}")
            result[sample] = values
    if set(result) != {"tth-sm", "tth-cpv", "ttz", "ttbb", "6q", "4f2l"}:
        raise RuntimeError(f"Cutflow source missing required sample rows: {path}")
    return result


def verify_production_summary(path: Path, authority: Any) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"Missing production summary: {path}")
    payload = read_json(path); records = payload.get("jobs", payload.get("records", [])); by_job = {str(row.get("job_key")): row for row in records if row.get("job_key")}
    expected_total = sum(int(row["n_events"]) for row in authority.catalog_jobs.values())
    observed_total = sum(int(row.get("exported_events", row.get("n_exported", 0))) for row in records)
    if observed_total != expected_total or int(payload.get("total_exported_events", observed_total)) != expected_total:
        raise RuntimeError(f"production summary total_exported_events mismatch: {observed_total} != {expected_total}")
    for key, catalog_row in authority.catalog_jobs.items():
        if key not in by_job or int(by_job[key].get("exported_events", by_job[key].get("n_exported", 0))) != int(catalog_row["n_events"]):
            raise RuntimeError(f"production summary/catalog exported mismatch: {key}")
    return {"jobs": len(records), "total_exported_events": observed_total, "sha256": sha256_file(path)}


def projection_finalization(missing: list[dict[str, Any]], stratified: list[dict[str, Any]]) -> str:
    if missing:
        for row in stratified:
            row["projection_status"] = "partial_not_publishable"
        return "blocked_missing_strata"
    return "complete_stratified"


def exact_score_digest(rows: list[dict[str, Any]]) -> str:
    payload = sorted((str(row["job_key"]), int(row["event_index"]), float(row["score"])) for row in rows)
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def normalization_inventory(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.is_file():
        return []
    payload = read_json(path)
    rows = payload.get("normalizations", [])
    fields = ("sample_key", "polarization", "process_mask", "normalization_key",
              "generator_events", "cross_section_fb", "cross_section_uncertainty_fb",
              "effective_luminosity_fb_inv", "weight_phys", "normalization_type",
              "denominator_definition", "cross_section_provenance")
    output = []
    for row in rows:
        item = {field: row.get(field, "") for field in fields}
        if isinstance(item["cross_section_provenance"], (dict, list)):
            item["cross_section_provenance"] = json.dumps(
                item["cross_section_provenance"], sort_keys=True, separators=(",", ":")
            )
        output.append(item)
    return output


def efficiency_curve(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for sample in ("tth-sm", "tth-cpv"):
        for polarization in ("eL.pR", "eR.pL"):
            values = np.sort(np.asarray([
                row["score"] for row in rows
                if row["sample_key"] == sample and row["category"] == "tth-hbb"
                and row["polarization"] == polarization
            ], dtype=float))
            for threshold in np.linspace(0.0, 1.0, 1001):
                passed = int(len(values) - np.searchsorted(values, threshold, side="left"))
                output.append({"sample_key": sample, "category": "tth-hbb", "polarization": polarization, "threshold": float(threshold), "events": len(values), "pass": passed, "efficiency": passed / len(values) if len(values) else "", "significance": ""})
    return output


def score_histograms(rows: list[dict[str, Any]], bins: int = 50) -> list[dict[str, Any]]:
    output = []
    edges = np.linspace(0, 1, bins + 1)
    for category in CATEGORIES:
        subset = [row for row in rows if row["sample_key"] != "tth-cpv" and row["category"] == category]
        scores = np.asarray([row["score"] for row in subset], dtype=float)
        weights = np.asarray([row["weight_phys"] for row in subset if row["weight_phys"] != ""], dtype=float)
        weighted_scores = np.asarray([row["score"] for row in subset if row["weight_phys"] != ""], dtype=float)
        counts, _ = np.histogram(scores, edges); weighted, _ = np.histogram(weighted_scores, edges, weights=weights)
        for index in range(bins):
            output.append({"category": category, "bin_low": edges[index], "bin_high": edges[index + 1], "raw_count": int(counts[index]), "raw_density": float(counts[index] / max(len(scores), 1) / (edges[index + 1] - edges[index])), "test_weighted_yield": float(weighted[index])})
    return output


def refuse_overwrite(path: Path) -> None:
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite existing output directory: {path}")
    path.mkdir(parents=True)


def threshold_rows(evaluation: dict[str, Any]) -> list[dict[str, Any]]:
    scan = evaluation.get("threshold_scan")
    if not isinstance(scan, list) or not scan:
        raise RuntimeError("evaluation JSON lacks threshold_scan")
    return [{"threshold": float(row["threshold"]), "signal": float(row["signal"]),
             "background": float(row["background"]),
             "signal_over_background": "" if row.get("signal_over_background") is None else float(row["signal_over_background"]),
             "significance": float(row["signal_over_sqrt_signal_plus_background"])} for row in scan]


def category_cutflow(evaluation: dict[str, Any]) -> list[dict[str, Any]]:
    selected = evaluation.get("test_selected_yields", {}).get("analysis_category", {})
    strata = evaluation.get("strata", {}).get("test", {}).get("analysis_category", {})
    rows = []
    for category in CATEGORIES:
        total = strata.get(category, {}).get("events"); item = selected.get(category, {}); passed = item.get("events")
        rows.append({"category": category, "sample_or_category": category, "stage": "MVA threshold", "split": "test",
                     "denominator": "test events; weight_phys for yield",
                     "events_before_threshold": "" if total is None else int(total),
                     "events_pass": "" if passed is None else int(passed),
                     "efficiency": "" if total in (None, 0) or passed is None else float(passed / total),
                     "test_yield": "" if item.get("expected_yield") is None else float(item["expected_yield"]),
                     "status": "observed_from_evaluation" if total is not None else "missing"})
    return rows


def exact_rows(
    authority: Any,
    score_dir: Path,
    include_cpv: bool = True,
    score_provenance: dict[str, str] | None = None,
    splits: set[str] | None = None,
    normalization_keys: set[str] | None = None,
    excluded_normalization_keys: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Join score-only shards to catalogued frozen HDF5 by job/event index."""
    import h5py
    selected_splits = {"test"} if splits is None else set(splits)
    included_keys = None if normalization_keys is None else set(normalization_keys)
    excluded_keys = set() if excluded_normalization_keys is None else set(excluded_normalization_keys)
    output: list[dict[str, Any]] = []
    for job_key in selected_job_keys(authority, splits=selected_splits, include_cpv=include_cpv):
        row = authority.catalog_jobs[job_key]; shard = score_dir / f"{job_key}.scores.h5"
        normalization_key = str(row["normalization_key"])
        if included_keys is not None and normalization_key not in included_keys:
            continue
        if normalization_key in excluded_keys:
            continue
        if not shard.is_file():
            raise RuntimeError(f"EXACT_MODE_MISSING_SCORE_SHARD: {shard}")
        source_path, catalog_row, _ = validate_job_hdf5(authority, job_key)
        with h5py.File(shard, "r") as score_file:
            checks = {"complete": True, "job_key": job_key, "sample_key": row["sample_key"],
                                   "polarization": row["polarization"], "n_events": row["n_events"],
                                   "source_hdf5": str(source_path), "source_hdf5_sha256": row["hdf5_sha256"],
                                   "weights_catalog_hash": authority.catalog_hash}
            checks.update(score_provenance or {})
            for attr, expected in checks.items():
                if str(score_file.attrs.get(attr, "")) != str(expected):
                    raise RuntimeError(f"{shard}: score provenance mismatch for {attr}")
            event_index = np.asarray(score_file["event_index"][:], dtype=np.int64)
            score = np.asarray(score_file["score"][:], dtype=float)
        if (len(score) != int(row["n_events"]) or not np.isfinite(score).all()
                or np.any(score < 0.0) or np.any(score > 1.0)):
            raise RuntimeError(f"{shard}: invalid score length or non-finite score")
        with h5py.File(source_path, "r") as source:
            source_index = np.asarray(source["event_index"][:], dtype=np.int64)
            categories = np.asarray([decode(x) for x in source["analysis_category"][:]], dtype=object)
        if not np.array_equal(event_index, source_index):
            raise RuntimeError(f"{shard}: event_index/HDF5 mismatch")
        weight = catalog_row.get("weight_phys")
        for index, category in enumerate(categories):
            output.append({"job_key": job_key, "sample_key": row["sample_key"], "normalization_key": row["normalization_key"],
                           "polarization": row["polarization"], "category": str(category), "event_index": int(event_index[index]),
                           "score": float(score[index]), "weight_phys": "" if weight is None else float(weight), "split": str(row["split"])})
    return output


def catalog_strata(authority: Any) -> dict[tuple[str, str], dict[str, Any]]:
    """Summarize the frozen MVA-input population by normalization layer."""
    output: dict[tuple[str, str], dict[str, Any]] = {}
    for record in authority.catalog_jobs.values():
        if record.get("sample_key") == "tth-cpv" or record.get("weight_phys") is None:
            continue
        split = str(record["split"])
        for category, count_value in record.get("analysis_category_counts", {}).items():
            count = int(count_value)
            if count <= 0:
                continue
            key = (str(record["normalization_key"]), str(category))
            if key not in output:
                output[key] = {
                    "normalization_key": key[0],
                    "category": key[1],
                    "sample_key": str(record["sample_key"]),
                    "process_mask": "" if record.get("process_mask") is None else str(record["process_mask"]),
                    "polarization": str(record["polarization"]),
                    "train_jobs": 0,
                    "train_events": 0,
                    "validation_jobs": 0,
                    "validation_events": 0,
                    "test_jobs": 0,
                    "test_events": 0,
                    "full_mva_input_events": 0,
                    "full_pre_mva_expected_yield_8ab": 0.0,
                }
            row = output[key]
            row[f"{split}_jobs"] += 1
            row[f"{split}_events"] += count
            row["full_mva_input_events"] += count
            row["full_pre_mva_expected_yield_8ab"] += count * float(record["weight_phys"])
    return output


def missing_strata_details(
    strata: dict[tuple[str, str], dict[str, Any]],
    fallback_rows: list[dict[str, Any]],
    threshold: float,
) -> list[dict[str, Any]]:
    """Describe every non-empty physical stratum with zero test coverage."""
    output: list[dict[str, Any]] = []
    for key, source in sorted(strata.items()):
        if int(source["test_events"]) > 0:
            continue
        efficiency_source = "validation" if int(source["validation_events"]) > 0 else "train"
        subset = [
            row for row in fallback_rows
            if row["split"] == efficiency_source
            and (str(row["normalization_key"]), str(row["category"])) == key
        ]
        expected_events = int(source[f"{efficiency_source}_events"])
        if len(subset) != expected_events:
            raise RuntimeError(
                f"FALLBACK_SCORE_COVERAGE_MISMATCH: {key} {efficiency_source} "
                f"{len(subset)} != {expected_events}"
            )
        passed = sum(float(row["score"]) >= threshold for row in subset)
        efficiency = passed / len(subset) if subset else 0.0
        pre_yield = float(source["full_pre_mva_expected_yield_8ab"])
        output.append({
            **source,
            "coverage_class": f"{efficiency_source}_only",
            "efficiency_source": efficiency_source,
            "efficiency_source_events": len(subset),
            "pass_at_threshold": passed,
            "threshold": threshold,
            "efficiency_at_threshold": efficiency,
            "projected_post_mva_yield_8ab": pre_yield * efficiency,
        })
    return output


def weighted_threshold_scan(rows: list[dict[str, Any]]) -> list[dict[str, float | str]]:
    """Scan S/sqrt(S+B) using positive physical weights without Python event loops."""
    thresholds = np.linspace(0.0, 1.0, 1001)

    def cumulative_yield(signal: bool) -> np.ndarray:
        selected = [
            row for row in rows
            if row["sample_key"] != "tth-cpv"
            and ((row["category"] == "tth-hbb") == signal)
            and row["weight_phys"] != ""
        ]
        scores = np.asarray([row["score"] for row in selected], dtype=float)
        weights = np.asarray([row["weight_phys"] for row in selected], dtype=float)
        order = np.argsort(scores)
        scores = scores[order]
        weights = weights[order]
        suffix = np.cumsum(weights[::-1])[::-1]
        indices = np.searchsorted(scores, thresholds, side="left")
        result = np.zeros_like(thresholds)
        valid = indices < len(scores)
        result[valid] = suffix[indices[valid]]
        return result

    signal = cumulative_yield(True)
    background = cumulative_yield(False)
    denominator = np.sqrt(signal + background)
    significance = np.divide(signal, denominator, out=np.zeros_like(signal), where=denominator > 0)
    signal_efficiency = signal / signal[0] if signal[0] > 0 else np.zeros_like(signal)
    return [
        {
            "threshold": float(thresholds[index]),
            "signal": float(signal[index]),
            "background": float(background[index]),
            "signal_efficiency": float(signal_efficiency[index]),
            "significance": float(significance[index]),
            "status": "validation_only_missing_test_normalization_keys_excluded",
        }
        for index in range(len(thresholds))
    ]


def coverage_closed_projection(
    strata: dict[tuple[str, str], dict[str, Any]],
    test_rows: list[dict[str, Any]],
    missing_details: list[dict[str, Any]],
    threshold: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Project full exposure with test-first and held-out-validation fallback efficiencies."""
    missing_by_key = {
        (str(row["normalization_key"]), str(row["category"])): row
        for row in missing_details
    }
    test_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in test_rows:
        if row["sample_key"] == "tth-cpv":
            continue
        key = (str(row["normalization_key"]), str(row["category"]))
        test_by_key.setdefault(key, []).append(row)

    projection: list[dict[str, Any]] = []
    for key, source in sorted(strata.items()):
        if int(source["test_events"]) > 0:
            values = test_by_key.get(key, [])
            if len(values) != int(source["test_events"]):
                raise RuntimeError(f"TEST_SCORE_COVERAGE_MISMATCH: {key}")
            passed = sum(float(row["score"]) >= threshold for row in values)
            efficiency_source = "test"
            source_events = len(values)
            efficiency = passed / source_events
            independence_status = "independent_test"
        else:
            detail = missing_by_key[key]
            passed = int(detail["pass_at_threshold"])
            efficiency_source = str(detail["efficiency_source"])
            source_events = int(detail["efficiency_source_events"])
            efficiency = float(detail["efficiency_at_threshold"])
            independence_status = (
                "held_out_validation_excluded_from_threshold_optimization"
                if efficiency_source == "validation"
                else "train_apparent_efficiency_bounded_separately"
            )
        pre_yield = float(source["full_pre_mva_expected_yield_8ab"])
        projection.append({
            "normalization_key": key[0],
            "category": key[1],
            "full_pre_mva_expected_yield_8ab": pre_yield,
            "efficiency_source": efficiency_source,
            "efficiency_source_events": source_events,
            "pass_at_threshold": passed,
            "threshold": threshold,
            "efficiency_at_threshold": efficiency,
            "projected_post_mva_yield_8ab": pre_yield * efficiency,
            "independence_status": independence_status,
        })

    signal = sum(float(row["projected_post_mva_yield_8ab"]) for row in projection if row["category"] == "tth-hbb")
    background = sum(float(row["projected_post_mva_yield_8ab"]) for row in projection if row["category"] in BACKGROUNDS)
    train_only = [row for row in projection if row["efficiency_source"] == "train"]
    train_selected_background = sum(float(row["projected_post_mva_yield_8ab"]) for row in train_only if row["category"] in BACKGROUNDS)
    train_full_background = sum(float(row["full_pre_mva_expected_yield_8ab"]) for row in train_only if row["category"] in BACKGROUNDS)

    def summary_row(name: str, background_yield: float, status: str) -> dict[str, Any]:
        z = signal / math.sqrt(signal + background_yield) if signal + background_yield > 0 else 0.0
        return {
            "projection": name,
            "signal_Hbb": signal,
            "background": background_yield,
            "Z": z,
            "threshold": threshold,
            "status": status,
        }

    summary = [
        summary_row("coverage_closed_central", background, "test_first_validation_fallback_4_train_only_central"),
        summary_row("train_only_zero", background - train_selected_background, "extreme_bound"),
        summary_row("train_only_all_pass", background - train_selected_background + train_full_background, "extreme_bound"),
    ]
    return projection, summary


def exact_cutflow(rows: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    output = []
    for category in CATEGORIES:
        values = [row for row in rows if row["sample_key"] != "tth-cpv" and row["category"] == category]; passed = [row for row in values if row["score"] >= threshold]
        weight = sum(float(row["weight_phys"]) for row in passed if row["weight_phys"] != "")
        output.append({"category": category, "sample_or_category": category, "stage": "MVA threshold", "split": "test", "denominator": "catalogued test HDF5 events",
                       "events_before_threshold": len(values), "events_pass": len(passed), "efficiency": len(passed) / len(values) if values else "",
                       "test_yield": weight, "status": "exact_score_HDF5_join"})
    return output


def projection_rows(authority: Any, rows: list[dict[str, Any]], threshold: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    full: dict[str, float] = {category: 0.0 for category in CATEGORIES}; strata_full: dict[tuple[str, str], float] = {}
    for record in authority.catalog_jobs.values():
        if record.get("sample_key") == "tth-cpv" or record.get("weight_phys") is None: continue
        for category, count in record.get("analysis_category_counts", {}).items():
            full[category] = full.get(category, 0.0) + int(count) * float(record["weight_phys"])
            key = (str(record["normalization_key"]), str(category)); strata_full[key] = strata_full.get(key, 0.0) + int(count) * float(record["weight_phys"])
    naive = []
    for category in CATEGORIES:
        subset = [row for row in rows if row["sample_key"] != "tth-cpv" and row["category"] == category]; eff = sum(row["score"] >= threshold for row in subset) / len(subset) if subset else None
        naive.append({"category": category, "full_pre_mva_yield": full[category], "test_efficiency": eff, "test_events": len(subset),
                      "projected_yield": "" if eff is None else full[category] * eff, "projection_status": "preliminary_naive"})
    stratified = []; missing = []
    for key, pre_yield in sorted(strata_full.items()):
        subset = [row for row in rows if row["sample_key"] != "tth-cpv" and (str(row["normalization_key"]), row["category"]) == key]
        if not subset: missing.append({"normalization_key": key[0], "category": key[1], "full_pre_mva_yield": pre_yield, "reason": "no test score/HDF5 rows"}); continue
        eff = sum(row["score"] >= threshold for row in subset) / len(subset)
        stratified.append({"normalization_key": key[0], "category": key[1], "full_pre_mva_yield": pre_yield, "test_efficiency": eff,
                           "projected_yield": pre_yield * eff, "projection_status": "complete_stratified"})
    projection_finalization(missing, stratified)
    return naive, stratified, missing


def plot_threshold(rows: list[dict[str, Any]], path: Path) -> None:
    import matplotlib.pyplot as plt
    x = [r["threshold"] for r in rows]; fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharex=True)
    best = max(rows, key=lambda row: float(row["significance"]))
    for ax, field, label in zip(axes.flat, ("significance", "signal", "background", "signal_over_background"), ("Z=S/sqrt(S+B)", "S", "B", "S/B")):
        ax.plot(x, [float(r[field]) if r[field] != "" else np.nan for r in rows])
        ax.axvline(best["threshold"], color="black", ls="--", lw=1,
                   label=f"best={best['threshold']:.3f}")
        ax.set_ylabel(label); ax.grid(alpha=.25)
    axes[0, 0].legend(fontsize=8)
    axes[1, 0].set_xlabel("threshold"); axes[1, 1].set_xlabel("threshold"); fig.suptitle("Validation-only threshold scan"); fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)


def plot_training(history: dict[str, Any], path: Path) -> None:
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for name, label in (("validation_0", "train"), ("validation_1", "validation"), ("train", "train"), ("validation", "validation")):
        block = history.get(name)
        if isinstance(block, dict) and block.get("logloss"): ax.plot(block["logloss"], label=label)
    ax.set(xlabel="boosting round", ylabel="logloss", title="XGBoost training diagnostics"); ax.grid(alpha=.25); ax.legend(); fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)


def plot_exact_scores(rows: list[dict[str, Any]], threshold: float, out: Path) -> None:
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for category in CATEGORIES:
        values = [r["score"] for r in rows if r["sample_key"] != "tth-cpv" and r["category"] == category]; color = f"C{CATEGORIES.index(category)}"
        if values: axes[0].hist(values, bins=50, range=(0, 1), density=True, histtype="step", label=category, color=color)
        weighted = [r for r in rows if r["sample_key"] != "tth-cpv" and r["category"] == category and r["weight_phys"] != ""]
        if weighted: axes[1].hist([r["score"] for r in weighted], bins=50, range=(0, 1), weights=[r["weight_phys"] for r in weighted], histtype="step", label=category, color=color)
    for ax, title, ylabel in ((axes[0], "test raw score", "unit-area density"), (axes[1], "test weighted score", "weighted yield")):
        ax.axvline(threshold, color="black", ls="--"); ax.set(xlabel="MVA score", ylabel=ylabel, title=title); ax.grid(alpha=.2); ax.legend(fontsize=7)
    axes[1].set_yscale("log")
    fig.tight_layout(); fig.savefig(out, dpi=160); plt.close(fig)


def plot_efficiency(curve: list[dict[str, Any]], out: Path) -> None:
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for sample, color in (("tth-sm", "C0"), ("tth-cpv", "C1")):
        for polarization, style in (("eL.pR", "-"), ("eR.pL", "--")):
            values = [row for row in curve if row["sample_key"] == sample and row["polarization"] == polarization]
            ax.plot([row["threshold"] for row in values], [row["efficiency"] if row["efficiency"] != "" else np.nan for row in values], color=color, ls=style, label=f"{sample} {polarization}")
    ax.axvline(0.954, color="black", ls=":", lw=1, label="working point 0.954")
    ax.set(xlabel="threshold", ylabel="Hbb test efficiency", title="SM/CPV Hbb efficiency (test only)"); ax.grid(alpha=.25); ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(out, dpi=160); plt.close(fig)


def roc_curve_rows(
    rows: list[dict[str, Any]], threshold: float
) -> tuple[list[dict[str, float]], dict[str, float | int | str]]:
    """Build the unweighted ordinary-test ROC used by the evaluator's headline AUC."""
    selected = [row for row in rows if row["sample_key"] != "tth-cpv"]
    labels = np.asarray([row["category"] == "tth-hbb" for row in selected], dtype=np.int64)
    scores = np.asarray([row["score"] for row in selected], dtype=float)
    positives = int(labels.sum())
    negatives = int(len(labels) - positives)
    if positives == 0 or negatives == 0:
        raise RuntimeError("ROC_REQUIRES_BOTH_SIGNAL_AND_BACKGROUND")

    order = np.argsort(-scores, kind="mergesort")
    ordered_scores = scores[order]
    ordered_labels = labels[order]
    distinct_ends = np.r_[np.flatnonzero(np.diff(ordered_scores)), len(ordered_scores) - 1]
    true_positive = np.cumsum(ordered_labels)[distinct_ends]
    false_positive = distinct_ends + 1 - true_positive
    tpr = np.r_[0.0, true_positive / positives]
    fpr = np.r_[0.0, false_positive / negatives]
    curve_thresholds = np.r_[np.inf, ordered_scores[distinct_ends]]
    curve = [{
        "threshold": float(value),
        "false_positive_rate": float(x),
        "true_positive_rate": float(y),
    } for value, x, y in zip(curve_thresholds, fpr, tpr)]
    auc = float(np.trapz(tpr, fpr))
    selected_at_threshold = scores >= threshold
    operating_tpr = float(np.count_nonzero(selected_at_threshold & (labels == 1)) / positives)
    operating_fpr = float(np.count_nonzero(selected_at_threshold & (labels == 0)) / negatives)
    summary: dict[str, float | int | str] = {
        "auc": auc,
        "threshold": threshold,
        "true_positive_rate": operating_tpr,
        "false_positive_rate": operating_fpr,
        "background_rejection": 1.0 - operating_fpr,
        "signal_events": positives,
        "background_events": negatives,
        "weighting": "unweighted_raw_test_events",
    }
    return curve, summary


def plot_roc_curve(
    curve: list[dict[str, float]], summary: dict[str, float | int | str], out: Path
) -> None:
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.4, 5.5))
    ax.plot(
        [row["false_positive_rate"] for row in curve],
        [row["true_positive_rate"] for row in curve],
        color="C0", lw=2.5, label=f"XGBoost test ROC (AUC={float(summary['auc']):.4f})",
    )
    ax.plot([0, 1], [0, 1], color="0.45", ls="--", lw=1.2, label="random classifier")
    ax.scatter(
        [float(summary["false_positive_rate"])],
        [float(summary["true_positive_rate"])],
        color="C3", marker="o", s=55, zorder=3,
        label=(f"working point={float(summary['threshold']):.3f}\n"
               f"TPR={float(summary['true_positive_rate']):.3f}, "
               f"FPR={float(summary['false_positive_rate']):.3f}"),
    )
    ax.set(
        xlabel="background efficiency (false-positive rate)",
        ylabel="signal efficiency (true-positive rate)",
        title="Independent test ROC (unweighted ordinary MC)",
        xlim=(0.0, 1.0), ylim=(0.0, 1.02),
    )
    ax.grid(alpha=.22); ax.legend(loc="lower right", fontsize=8.5)
    fig.tight_layout(); fig.savefig(out, dpi=180); plt.close(fig)


def plot_efficiency_significance(rows: list[dict[str, Any]], threshold: float, out: Path) -> None:
    """Put the validation signal-efficiency trade-off and threshold statistic on one figure."""
    import matplotlib.pyplot as plt
    x = np.asarray([row["threshold"] for row in rows], dtype=float)
    efficiency = np.asarray([row["signal_efficiency"] for row in rows], dtype=float)
    significance = np.asarray([row["significance"] for row in rows], dtype=float)
    fig, left = plt.subplots(figsize=(8, 5))
    right = left.twinx()
    efficiency_line, = left.plot(x, efficiency, color="C0", lw=2.5, label="signal efficiency")
    significance_line, = right.plot(x, significance, color="C9", lw=2.5, label=r"$S/\sqrt{S+B}$")
    left.axvline(threshold, color="black", ls="--", lw=1.2, label=f"working point={threshold:.3f}")
    left.set(xlabel="MVA score threshold", ylabel="validation signal efficiency", xlim=(0.0, 1.0), ylim=(0.0, 1.04))
    right.set_ylabel(r"validation $S/\sqrt{S+B}$", color="C9")
    right.tick_params(axis="y", colors="C9")
    left.grid(alpha=.22)
    lines = [efficiency_line, significance_line, left.lines[-1]]
    left.legend(lines, [line.get_label() for line in lines], loc="best", fontsize=9)
    left.set_title("Validation working-point trade-off\nmissing-test normalization keys excluded")
    fig.tight_layout(); fig.savefig(out, dpi=180); plt.close(fig)


def model_feature_importance(training_dir: Path) -> list[dict[str, Any]]:
    """Read mean-gain importance from exactly the trees used for prediction."""
    import xgboost as xgb
    provenance = read_json(training_dir / "provenance.json")
    booster = xgb.Booster()
    booster.load_model(training_dir / "model.json")
    best_iteration = int(provenance["best_iteration"])
    if booster.num_boosted_rounds() < best_iteration + 1:
        raise RuntimeError("MODEL_HAS_FEWER_TREES_THAN_BEST_ITERATION")
    # NECESSITY: slicing excludes the early-stopping patience trees that are
    # saved in model.json but are not used by apply_selection.py predictions.
    used = booster[:best_iteration + 1]
    features = [str(value) for value in provenance["features"]]
    gain = used.get_score(importance_type="gain")
    total_gain = used.get_score(importance_type="total_gain")
    split_count = used.get_score(importance_type="weight")
    rows = [{
        "feature": feature,
        "gain": float(gain.get(feature, 0.0)),
        "total_gain": float(total_gain.get(feature, 0.0)),
        "split_count": float(split_count.get(feature, 0.0)),
        "best_iteration": best_iteration,
        "trees_used": best_iteration + 1,
    } for feature in features]
    rows.sort(key=lambda row: float(row["gain"]), reverse=True)
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def plot_feature_importance(rows: list[dict[str, Any]], out: Path) -> None:
    import matplotlib.pyplot as plt
    ordered = list(reversed(rows))
    fig, ax = plt.subplots(figsize=(8.2, 8.0))
    ax.barh([row["feature"] for row in ordered], [row["gain"] for row in ordered], color="C0")
    ax.set(xlabel="XGBoost mean gain", title="Feature importance (best-iteration trees only)")
    ax.grid(axis="x", alpha=.22)
    fig.tight_layout(); fig.savefig(out, dpi=180); plt.close(fig)


def projection_summary(naive: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signal = next((float(row["projected_yield"]) for row in naive if row["category"] == "tth-hbb" and row["projected_yield"] != ""), 0.0)
    background = sum(float(row["projected_yield"]) for row in naive if row["category"] in BACKGROUNDS and row["projected_yield"] != "")
    z = signal / math.sqrt(signal + background) if signal + background else 0.0
    def uncertainty(category: str) -> float:
        row = next((item for item in naive if item["category"] == category), None)
        if not row or row["test_efficiency"] in (None, "") or not row.get("test_events"): return float("nan")
        return float(row["full_pre_mva_yield"]) * math.sqrt(float(row["test_efficiency"]) * (1 - float(row["test_efficiency"])) / int(row["test_events"]))
    sigma_s = uncertainty("tth-hbb"); sigma_b = math.sqrt(sum(uncertainty(c) ** 2 for c in BACKGROUNDS))
    return [{"projection": "naive", "signal_Hbb": signal, "background": background, "Z": z, "signal_mc_uncertainty_binomial_approx": sigma_s, "background_mc_uncertainty_binomial_approx": sigma_b, "status": "preliminary_naive"}]


def build_record(config: Path, evaluation: Path, training_dir: Path, outputs: list[Path]) -> dict[str, Any]:
    ev = read_json(evaluation); selected = ev.get("test_selected_yields", {}).get("analysis_category", {})
    signal = selected.get("tth-hbb", {}).get("expected_yield"); background = sum(float(selected.get(c, {}).get("expected_yield", 0)) for c in BACKGROUNDS if selected.get(c, {}).get("expected_yield") is not None)
    test_z = signal / math.sqrt(signal + background) if signal is not None and signal + background > 0 else None
    inputs = [config, evaluation]
    for file in (training_dir / "provenance.json", training_dir / "model.json", training_dir / "training_history.json"):
        if file.is_file(): inputs.append(file)
    return {"schema_version": 3, "analysis": ev.get("analysis_name"), "inputs": {str(p): sha256_file(p) for p in inputs}, "threshold": ev.get("threshold"), "threshold_status": ev.get("threshold_status"), "test_auc": ev.get("metrics", {}).get("test", {}).get("auc"), "test_S": signal, "test_B": background, "test_Z": test_z, "outputs": [p.name for p in outputs], "red_flags": ["test-only exposure: 13.06 is a test-subset weighted diagnostic, not full 8 ab^-1", "one CPV event was skipped and signed CPV interference is not significance input", "6q/4f2l high-score tails are sparse and need finite-test-MC uncertainty", "coverage-closed projection uses held-out validation for 11 strata and a separately bounded train-only contribution for 4 tiny strata", "yt mapping uses approximate sigma proportional to yt^2 and is statistical-only"]}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(); parser.add_argument("--config", type=Path, default=Path("configs/mva_training.yaml")); parser.add_argument("--evaluation", type=Path, required=True); parser.add_argument("--training-dir", type=Path, required=True); parser.add_argument("--output-dir", type=Path, required=True); parser.add_argument("--scores-dir", type=Path); parser.add_argument("--manifest", type=Path); parser.add_argument("--production-summary", type=Path); parser.add_argument("--inventory", type=Path); parser.add_argument("--weights-catalog", type=Path); parser.add_argument("--cutflow-source", type=Path, required=True); return parser.parse_args()


def main() -> None:
    args = parse_args(); output = args.output_dir.resolve(); refuse_overwrite(output); config = args.config.resolve(); evaluation = args.evaluation.resolve(); training = args.training_dir.resolve(); ev = read_json(evaluation); scan = threshold_rows(ev); threshold = float(ev["threshold"])
    write_csv(output / "threshold_scan.csv", scan, ["threshold", "signal", "background", "signal_over_background", "significance"]); write_csv(output / "cutflow_test.csv", category_cutflow(ev), ["sample_or_category", "stage", "split", "denominator", "events_before_threshold", "events_pass", "efficiency", "test_yield", "status"])
    history = read_json(training / "training_history.json") if (training / "training_history.json").is_file() else {}; train_block = history.get("validation_0", history.get("train", {})); val_block = history.get("validation_1", history.get("validation", {})); train_loss = train_block.get("logloss", []); val_loss = val_block.get("logloss", [])
    write_csv(output / "training_logloss.csv", [{"round": i, "train_logloss": train_loss[i] if i < len(train_loss) else "", "validation_logloss": val_loss[i] if i < len(val_loss) else ""} for i in range(max(len(train_loss), len(val_loss)))], ["round", "train_logloss", "validation_logloss"]); write_csv(output / "auc_table.csv", [{"split": split, "auc": value.get("auc"), "events": value.get("events")} for split, value in ev.get("metrics", {}).items()], ["split", "auc", "events"]); plot_threshold(scan, output / "threshold_scan.png"); plot_training(history, output / "training_logloss.png")
    importance = model_feature_importance(training)
    write_csv(output / "feature_importance_gain.csv", importance, ["rank", "feature", "gain", "total_gain", "split_count", "best_iteration", "trees_used"])
    plot_feature_importance(importance, output / "feature_importance_gain.png")
    projection_status = "not_requested"
    production_audit = None
    source_counts = parse_cutflow_source(args.cutflow_source.resolve())
    authority = load_authority(config) if (args.scores_dir or args.manifest or args.production_summary or args.inventory or args.weights_catalog) else None
    if authority is not None and args.production_summary:
        production_audit = verify_production_summary(args.production_summary.resolve(), authority)
    exact_rows_data = None
    if args.scores_dir:
        authority = authority or load_authority(config)
        provenance_checks = {
            key: str(ev[key]) for key in (
                "model_sha256", "provenance_sha256", "implementation_hash",
                "apply_script_sha256"
            ) if ev.get(key) is not None
        }
        rows = exact_rows(
            authority, args.scores_dir.resolve(), score_provenance=provenance_checks
        ); exact_rows_data = rows
        write_csv(output / "cutflow_test_exact.csv", exact_cutflow(rows, threshold), ["sample_or_category", "stage", "split", "denominator", "events_before_threshold", "events_pass", "efficiency", "test_yield", "status"])
        write_csv(output / "score_histograms.csv", score_histograms(rows), ["category", "bin_low", "bin_high", "raw_count", "raw_density", "test_weighted_yield"]); plot_exact_scores(rows, threshold, output / "score_distributions_exact.png")
        roc_rows, roc_summary = roc_curve_rows(rows, threshold)
        expected_auc = float(ev["metrics"]["test"]["auc"])
        # NECESSITY: fail closed if the plotted rows or weight convention no longer
        # reproduce the evaluator's published independent-test AUC.
        if not math.isclose(float(roc_summary["auc"]), expected_auc, rel_tol=0.0, abs_tol=1e-12):
            raise RuntimeError("EXACT_TEST_ROC_AUC_MISMATCH")
        write_csv(output / "roc_curve_test.csv", roc_rows, ["threshold", "false_positive_rate", "true_positive_rate"])
        write_csv(output / "roc_summary_test.csv", [roc_summary], ["auc", "threshold", "true_positive_rate", "false_positive_rate", "background_rejection", "signal_events", "background_events", "weighting"])
        plot_roc_curve(roc_rows, roc_summary, output / "roc_curve_test.png")
        curve = efficiency_curve(rows); write_csv(output / "sm_cpv_hbb_efficiency.csv", curve, ["sample_key", "category", "polarization", "threshold", "events", "pass", "efficiency", "significance"]); plot_efficiency(curve, output / "sm_cpv_hbb_efficiency.png")
        naive, stratified, missing = projection_rows(authority, rows, threshold); write_csv(output / "projection_naive.csv", naive, ["category", "full_pre_mva_yield", "test_efficiency", "test_events", "projected_yield", "projection_status"]); write_csv(output / "projection_summary.csv", projection_summary(naive), ["projection", "signal_Hbb", "background", "Z", "signal_mc_uncertainty_binomial_approx", "background_mc_uncertainty_binomial_approx", "status"]); write_csv(output / "projection_stratified.csv", stratified, ["normalization_key", "category", "full_pre_mva_yield", "test_efficiency", "projected_yield", "projection_status"]); write_csv(output / "missing_strata.csv", missing, ["normalization_key", "category", "full_pre_mva_yield", "reason"])

        strata = catalog_strata(authority)
        missing_keys = {(str(row["normalization_key"]), str(row["category"])) for row in missing}
        missing_normalization_keys = {key[0] for key in missing_keys}
        validation_scan_rows = exact_rows(
            authority,
            args.scores_dir.resolve(),
            include_cpv=False,
            score_provenance=provenance_checks,
            splits={"validation"},
            excluded_normalization_keys=missing_normalization_keys,
        )
        coverage_scan = weighted_threshold_scan(validation_scan_rows)
        del validation_scan_rows
        coverage_best = max(coverage_scan, key=lambda row: float(row["significance"]))
        coverage_threshold = float(coverage_best["threshold"])
        write_csv(output / "threshold_scan_coverage_closed.csv", coverage_scan, ["threshold", "signal", "background", "signal_efficiency", "significance", "status"])
        plot_efficiency_significance(coverage_scan, coverage_threshold, output / "validation_efficiency_significance.png")

        validation_keys = {key[0] for key in missing_keys if int(strata[key]["validation_events"]) > 0}
        train_only_keys = {key[0] for key in missing_keys if int(strata[key]["validation_events"]) == 0}
        fallback_rows = exact_rows(
            authority,
            args.scores_dir.resolve(),
            include_cpv=False,
            score_provenance=provenance_checks,
            splits={"validation"},
            normalization_keys=validation_keys,
        )
        fallback_rows.extend(exact_rows(
            authority,
            args.scores_dir.resolve(),
            include_cpv=False,
            score_provenance=provenance_checks,
            splits={"train"},
            normalization_keys=train_only_keys,
        ))
        missing_detail_rows = missing_strata_details(strata, fallback_rows, coverage_threshold)
        missing_fields = [
            "normalization_key", "sample_key", "process_mask", "polarization", "category", "coverage_class",
            "train_jobs", "train_events", "validation_jobs", "validation_events", "test_jobs", "test_events",
            "full_mva_input_events", "full_pre_mva_expected_yield_8ab", "efficiency_source",
            "efficiency_source_events", "pass_at_threshold", "threshold", "efficiency_at_threshold",
            "projected_post_mva_yield_8ab",
        ]
        write_csv(output / "missing_strata_detailed.csv", missing_detail_rows, missing_fields)
        closed_rows, closed_summary = coverage_closed_projection(strata, rows, missing_detail_rows, coverage_threshold)
        write_csv(output / "projection_coverage_closed.csv", closed_rows, [
            "normalization_key", "category", "full_pre_mva_expected_yield_8ab", "efficiency_source",
            "efficiency_source_events", "pass_at_threshold", "threshold", "efficiency_at_threshold",
            "projected_post_mva_yield_8ab", "independence_status",
        ])
        write_csv(output / "projection_coverage_closed_summary.csv", closed_summary, ["projection", "signal_Hbb", "background", "Z", "threshold", "status"])
        projection_status = "coverage_closed_with_4_train_only_strata_bounded" if missing else "complete_stratified"
    else:
        missing = []
    if authority is not None:
        write_csv(output / "sample_cutflow.csv", sample_cutflow(authority, args.manifest, args.production_summary, exact_rows_data, threshold, source_counts), ["sample", "denominator_stage", "reco_input_denominator", "accepted_events", "fit_success_events", "manifest_input_readable", "hdf5_exported", "test_events", "threshold_pass", "status"])
    write_csv(output / "normalization_inventory.csv", normalization_inventory(args.inventory), ["sample_key", "polarization", "process_mask", "normalization_key", "generator_events", "cross_section_fb", "cross_section_uncertainty_fb", "effective_luminosity_fb_inv", "weight_phys", "normalization_type", "denominator_definition", "cross_section_provenance"])
    record = build_record(config, evaluation, training, list(output.iterdir())); record["projection_status"] = projection_status; record["authority_paths"] = {name: str(path) for name, path in (("manifest", args.manifest), ("production_summary", args.production_summary), ("inventory", args.inventory), ("weights_catalog", args.weights_catalog), ("cutflow_source", args.cutflow_source)) if path is not None}
    if production_audit is not None:
        record["production_summary_audit"] = production_audit
    record["cutflow_source_sha256"] = sha256_file(args.cutflow_source.resolve()); record["argv"] = sys.argv; record["run_mode"] = "exact" if args.scores_dir else "evaluation_only"
    if authority is not None:
        record["authority_hashes"] = {"split_assignment": sha256_file(authority.split_path), "mva_config": sha256_file(authority.mva_config_path), "manifest": sha256_file(authority.manifest_path), "inventory": sha256_file(authority.inventory_path), "weights_catalog": sha256_file(authority.catalog_path)}
    if args.scores_dir and exact_rows_data is not None:
        record["exact_test"] = {"jobs": len({row["job_key"] for row in exact_rows_data}), "events": len(exact_rows_data), "job_score_hash": exact_score_digest(exact_rows_data), "job_catalog_hash": hashlib.sha256(json.dumps(sorted((row["job_key"], row["normalization_key"]) for row in exact_rows_data), separators=(",", ":")).encode()).hexdigest()}
    for label, path in (("manifest", args.manifest), ("production_summary", args.production_summary), ("inventory", args.inventory), ("weights_catalog", args.weights_catalog)):
        if path is not None and path.is_file(): record["inputs"][str(path.resolve())] = sha256_file(path.resolve())
    provenance_path = training / "provenance.json"
    if provenance_path.is_file():
        provenance = read_json(provenance_path); record["best_iteration"] = provenance.get("best_iteration")
    record["builder_path"] = str(Path(__file__).resolve()); record["builder_sha256"] = sha256_file(Path(__file__).resolve()); record["frozen_cutflow_source"] = "reports/kinfit_full_production_mva_handoff_20260804.md; accepted/fit counts are not inferred"
    (output / "red_flags.csv").write_text("flag\n" + "\n".join('"' + flag.replace('"', '""') + '"' for flag in record["red_flags"]) + "\n")
    (output / "mva_group_record_zh.md").write_text("# MVA 组会材料（中文记录）\n\n输入冻结记录：1150 jobs、5,256,280 exported events；权威 production cutflow 为 10,208,234 input、5,258,351 accepted、5,256,281 fit，production summary exported=5,256,280（差 1 为 CPV）。`sample_cutflow.csv` 的 accepted/fit 权威来源是 `reports/kinfit_full_production_mva_handoff_20260804.md`，不由 exported 数反推。\n\nselection stage 是 nIso1/可读输入→KinFit→导出 HDF5；训练使用固定 25 features：y45,y56,y67,btag_1,btag_2,btag_3,btag_4,ctag_1,ctag_2,ctag_3,ctag_4,mH_postfit,mW_had_postfit,mt_had_postfit,mt_lep_postfit,fitchi2,chi2_over_ndof,fitprob,final_selection_score,final_fit_score,final_flavor_score,lepton_E,lepton_theta,lepton_pt,lepton_charge。信号是 tth-sm/Hbb；背景是 tth-nonbb、ttz、ttbb、6q、4f2l；tth-cpv 不训练、不参与 significance，只做 test efficiency。\n\n`weight_train` 是 train-only 按类别/极化平衡的训练权；`weight_phys=σL/N_gen` 只用于物理 yield 和 validation threshold。split 是 train/validation/test；阈值在 validation 上最大化 `S/sqrt(S+B)`，test 只作一次独立评估。直接 test 的 AUC、六类 count/yield、S/B/Z 在 `cutflow_test.csv` 和 evaluation 输入中；test-only 13.06 不能当完整 8 ab^-1。exact 模式将 test score 按 event_index 与 HDF5/catalog join，给 raw unit-area、weighted yield、SM/CPV Hbb efficiency 曲线。\n\nnaive 8 ab^-1 投影把 category-global test efficiency 乘 full pre-MVA yield，标 preliminary/naive。覆盖修补采用逐 normalization_key×category 的 test-first 规则：51层使用test；11个test空层使用未参与训练且从重算阈值中排除的validation；4个train-only小层单列极端上下界。它不把train+validation+test直接混算。CPV不算significance。\n\n## 五个红旗\n\n" + "\n".join("- " + flag for flag in record["red_flags"]) + "\n")
    cutflow_lines = [
        "| category | test before | pass @0.954 | efficiency | test weighted yield |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in category_cutflow(ev):
        efficiency = row["efficiency"]
        cutflow_lines.append(
            f"| {row['category']} | {row['events_before_threshold']} | {row['events_pass']} | "
            f"{float(efficiency):.4%} | {float(row['test_yield']):.6g} |"
        )
    details = (
        "\n## 直接 test 数值\n\n" + "\n".join(cutflow_lines)
        + f"\n\n其中 Hbb-only S={record['test_S']:.6g}, B={record['test_B']:.6g}, "
          f"Z=S/sqrt(S+B)={record['test_Z']:.6g}，AUC={record['test_auc']:.8f}。"
        + "这些是 held-out test jobs 的直接加权和，不是完整 8 ab^-1。\n\n"
        + "## 分母口径更正\n\n"
        + "`sample_cutflow.csv` 中的 `reco_input_denominator` 是 KinFit 输入分母："
          "Physsim 为 all-channel complete-reco，Whizard 为已经 nIso=1 的 reco skim。"
          "它们都不是 N_gen；真正 generator denominator 逐归一化层列在 "
          "`normalization_inventory.csv`，Whizard process masks 可重叠，不得盲加。\n\n"
        + "## 文献外推（仅估算）\n\n"
        + "arXiv:1104.5132 在 500 GeV、1 ab^-1、(Pe-,Pe+)=(-0.8,+0.3) 下给出："
          "半轻子 Z=3.7、Delta yt/yt=14%，半轻子+全强子 combined Z=5.2、10%。"
          "若只做统计亮度缩放到8 ab^-1，对应约 Z=10.47/14.71，"
          "Delta yt/yt=4.95%/3.54%。arXiv:2503.19983v4 的 550 GeV、8 ab^-1 预期 1.9%"
          "还利用了 500→550 GeV 使 ttH 截面约增大四倍、耦合测量约改善两倍的能量增益，"
          "不是 1 ab^-1 数字的单纯 sqrt(8) 缩放。\n"
    )
    if args.scores_dir:
        summary = projection_summary(naive)[0]
        missing_yield = sum(float(row["full_pre_mva_yield"]) for row in missing)
        central = next(row for row in closed_summary if row["projection"] == "coverage_closed_central")
        zero_bound = next(row for row in closed_summary if row["projection"] == "train_only_zero")
        all_pass_bound = next(row for row in closed_summary if row["projection"] == "train_only_all_pass")
        validation_missing = [row for row in missing_detail_rows if row["coverage_class"] == "validation_only"]
        train_missing = [row for row in missing_detail_rows if row["coverage_class"] == "train_only"]
        validation_missing_yield = sum(float(row["full_pre_mva_expected_yield_8ab"]) for row in validation_missing)
        train_missing_yield = sum(float(row["full_pre_mva_expected_yield_8ab"]) for row in train_missing)
        details += (
            "\n## 8 ab^-1 初步外推审计\n\n"
            f"normalization_key×category test 覆盖 {len(stratified)}/{len(stratified) + len(missing)} 层；"
            f"缺失 {len(missing)} 层，对应 full pre-MVA yield={missing_yield:.6g}。"
            f"category-global naive 值为 S={summary['signal_Hbb']:.6g}, "
            f"B={summary['background']:.6g}, Z={summary['Z']:.6g}。"
            "naive Z 只是带强假设的旧诊断。\n\n"
            "缺层来自logical production shard的独立哈希，而不是先按6q/4f2l大类或事件数分层。"
            f"其中{len(validation_missing)}层有validation、full pre-MVA yield={validation_missing_yield:.6g}；"
            f"{len(train_missing)}层只有train、full pre-MVA yield={train_missing_yield:.6g}。"
            "把所有缺失normalization keys从validation阈值优化中排除后，最佳阈值仍为"
            f"{coverage_threshold:.3f}。51层使用test效率，11层使用held-out validation效率后，"
            f"中央投影为S={central['signal_Hbb']:.6g}, B={central['background']:.6g}, Z={central['Z']:.6g}。"
            f"对4个train-only层取零通过/全通过两个极端，Z范围为"
            f"{all_pass_bound['Z']:.6g}–{zero_bound['Z']:.6g}。"
            "这是coverage-closed统计诊断，不包含系统学或profile likelihood。逐层详情见"
            "`missing_strata_detailed.csv`，完整66层见`projection_coverage_closed.csv`。\n"
        )
        record["stratified_coverage"] = {
            "covered": len(stratified), "total": len(stratified) + len(missing),
            "missing": len(missing), "missing_full_pre_mva_yield": missing_yield,
        }
        record["naive_projection"] = summary
        record["coverage_closed_projection"] = {
            "threshold": coverage_threshold,
            "threshold_unchanged_from_baseline": math.isclose(coverage_threshold, threshold, abs_tol=1e-12),
            "central": central,
            "train_only_extreme_bounds": {"zero": zero_bound, "all_pass": all_pass_bound},
            "validation_fallback_strata": len(validation_missing),
            "train_only_strata": len(train_missing),
            "validation_fallback_full_pre_mva_yield": validation_missing_yield,
            "train_only_full_pre_mva_yield": train_missing_yield,
        }
    report_path = output / "mva_group_record_zh.md"
    report_path.write_text(report_path.read_text() + details)
    record["outputs"] = {p.name: sha256_file(p) for p in output.iterdir() if p.is_file()}; (output / "manifest.json").write_text(json.dumps(record, indent=2) + "\n"); print(json.dumps({"output_dir": str(output), "threshold": threshold, "test_Z": record["test_Z"], "projection_status": projection_status}, indent=2))


if __name__ == "__main__": main()
