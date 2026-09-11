#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rerank TTHSemiLepKinFit candidate trees with explicit flavor terms.

This is an analysis-level diagnostic.  It does not rerun Marlin and does not
modify the TTHSemiLepKinFit processor.  The goal is to test whether the current
kinfit candidate pool becomes useful once the signed flavor likelihood is part
of the final objective instead of only a top-N preselection.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import ROOT


DEFAULT_LCIO = (
    "/data/dust/user/zhangyuy/analysis/tth/events_whizard/complete_reco/"
    "complete_reco_kinfit_ready_whizard_tth_PERF_kinfit_ready1000_20260602a_sgv.slcio"
)
DEFAULT_AUDIT_DIR = (
    "/data/dust/user/zhangyuy/analysis/tth/chi2_clustering/outputs/workflow_runs/"
    "tth_semilep_correction_effect_audit"
)
DEFAULT_CURRENT_ROOT = (
    DEFAULT_AUDIT_DIR
    + "/tth_semilep_top45_refined_debug_current_whizard_tth_PERF1000_20260608.root"
)
DEFAULT_SLD_ROOT = (
    DEFAULT_AUDIT_DIR
    + "/tth_semilep_top45_refined_debug_sld_whizard_tth_PERF1000_20260608.root"
)
DEFAULT_MODEL_BUNDLE = (
    "/data/dust/user/zhangyuy/analysis/tth/chi2_clustering/outputs/current_baseline/"
    "mcancestor_mass_response_chi2/fit_models_mcancestor_mass_response.json"
)
DEFAULT_OUTDIR = (
    "/data/dust/user/zhangyuy/analysis/tth/chi2_clustering/outputs/workflow_runs/"
    "tth_semilep_kinfit_flavor_rerank"
)

SENTINEL = -999.0


def add_module_path() -> None:
    candidates = [
        Path("/data/dust/user/zhangyuy/analysis/tth/chi2_clustering"),
        Path(__file__).resolve().parent,
        Path.cwd(),
    ]
    for path in candidates:
        if (path / "chi2_reco.py").exists() and str(path) not in sys.path:
            sys.path.insert(0, str(path))


add_module_path()

import chi2_reco  # noqa: E402
from combinations import SIX_ASSIGNMENTS  # noqa: E402
from scoring import flavor_charge_prior_semileptonic, flavor_prior_semileptonic  # noqa: E402
from truth_matching import match_semileptonic_event_by_role_source, truth_flags_semileptonic  # noqa: E402


ASSIGNMENT_BY_ID = {int(a["combo_id"]): a for a in SIX_ASSIGNMENTS}


def vec_to_list(vec) -> List:
    if vec is None:
        return []
    try:
        return [vec[i] for i in range(vec.size())]
    except Exception:
        pass
    try:
        return list(vec)
    except Exception:
        return []


def branch_names(tree) -> set[str]:
    if tree is None:
        return set()
    return {str(branch.GetName()) for branch in tree.GetListOfBranches()}


def finite(values: Iterable[float]) -> List[float]:
    return [float(x) for x in values if math.isfinite(float(x))]


def quantile(values: Sequence[float], q: float) -> float:
    vals = finite(values)
    if not vals:
        return float("nan")
    return float(sorted(vals)[min(len(vals) - 1, max(0, int(round(q * (len(vals) - 1)))) )])


def mean(values: Sequence[float]) -> float:
    vals = finite(values)
    return float(sum(vals) / len(vals)) if vals else float("nan")


def ensure_dir(path: str | Path) -> Path:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def write_csv(path: Path, rows: Sequence[Mapping], fieldnames: Optional[Sequence[str]] = None) -> None:
    if fieldnames is None:
        keys = []
        seen = set()
        for row in rows:
            for key in row.keys():
                if key not in seen:
                    keys.append(key)
                    seen.add(key)
        fieldnames = keys
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def load_price2014(path: str) -> Dict[str, Dict[str, float]]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    block = payload.get("price2014", payload)
    particles = block.get("particles", block)
    out = {}
    for key, particle in (("W", "W"), ("top", "top"), ("H", "H")):
        src = particles.get(particle) or particles.get("Higgs" if particle == "H" else particle) or {}
        out[key] = {
            "mass": float(src.get("M_nom", {"W": 80.4, "top": 172.5, "H": 125.0}[key])),
            "sigma": max(1.0e-6, float(src.get("sigma_std", src.get("sigma", 1.0)))),
        }
    return out


def price2014_score(row: Mapping, price: Mapping[str, Mapping[str, float]]) -> float:
    specs = [
        ("W", "mW_had_prefit"),
        ("top", "mt_had_prefit"),
        ("H", "mH_prefit"),
    ]
    score = 0.0
    for key, branch in specs:
        value = float(row.get(branch, SENTINEL))
        if value < -900.0 or not math.isfinite(value):
            return float("inf")
        center = float(price[key]["mass"])
        sigma = float(price[key]["sigma"])
        score += ((value - center) / sigma) ** 2
    return float(score)


def cfg_for_matching(input_lcio: str, jet_collection: str) -> Dict:
    return {
        "input_files": [input_lcio],
        "jet_collection": jet_collection,
        "lepton_collections": ["ISOElectrons", "ISOMuons"],
        "mc_collection": "MCParticlesSkimmed",
        "truejet_collection": "TrueJets",
        "truejet_pfo_link": "TrueJetPFOLink",
        "truejet_mc_link": "TrueJetMCParticleLink",
        "allowed_truth_leptons": ["e", "mu"],
        "min_truejet_dice": 0.0,
        "weaver_name": "weaver",
        "weaver_order": [
            "mc_b",
            "mc_bbar",
            "mc_c",
            "mc_cbar",
            "mc_d",
            "mc_dbar",
            "mc_g",
            "mc_s",
            "mc_sbar",
            "mc_u",
            "mc_ubar",
        ],
    }


def read_top_score_map(root_path: str) -> Tuple[Dict[int, Dict[str, List[float]]], set[int]]:
    f = ROOT.TFile.Open(root_path)
    if not f or f.IsZombie():
        raise RuntimeError(f"Cannot open ROOT file: {root_path}")
    tree = f.Get("TTHSemiLepKinFit")
    if tree is None:
        f.Close()
        raise RuntimeError(f"Missing TTHSemiLepKinFit in {root_path}")
    out = {}
    accepted = set()
    try:
        for row in tree:
            event_index = int(row.event_index)
            accepted.add(event_index)
            out[event_index] = {
                "combo_ids": [int(x) for x in vec_to_list(row.top_combo_ids)],
                "scores": [float(x) for x in vec_to_list(row.top_preselect_scores)],
                "best_combo_id": int(row.best_combo_id),
            }
    finally:
        f.Close()
    return out, accepted


def read_candidate_rows(root_path: str, mode_label: str, top_scores: Mapping[int, Mapping]) -> List[Dict]:
    f = ROOT.TFile.Open(root_path)
    if not f or f.IsZombie():
        raise RuntimeError(f"Cannot open ROOT file: {root_path}")
    tree = f.Get("TTHSemiLepKinFit_candidates")
    if tree is None:
        f.Close()
        raise RuntimeError(f"Missing TTHSemiLepKinFit_candidates in {root_path}")
    branches = branch_names(tree)
    rows = []
    try:
        for entry in tree:
            event_index = int(entry.event_index)
            rank = int(entry.candidate_rank)
            score_payload = top_scores.get(event_index, {})
            flavor_scores = score_payload.get("scores", [])
            combo_ids = score_payload.get("combo_ids", [])
            flavor_score = float(flavor_scores[rank]) if rank < len(flavor_scores) else float("nan")
            expected_combo = int(combo_ids[rank]) if rank < len(combo_ids) else -1
            combo_id = int(entry.combo_id)
            if expected_combo >= 0 and expected_combo != combo_id:
                # Keep the row, but make the mismatch visible in diagnostics.
                flavor_score = float("nan")
            row = {
                "source_mode": mode_label,
                "event_index": event_index,
                "candidate_rank": rank,
                "combo_id": combo_id,
                "sld_combo_index": int(getattr(entry, "sld_combo_index", 0)),
                "sld_used": int(getattr(entry, "sld_used", 0)),
                "sld_combination_count": int(getattr(entry, "sld_combination_count", 1)),
                "fit_status": int(entry.fit_status),
                "fit_success": int(entry.fit_success),
                "fitprob": float(entry.fitprob),
                "fitchi2": float(entry.fitchi2),
                "flavor_score": flavor_score,
                "max_mass_constraint_residual": float(getattr(entry, "max_mass_constraint_residual", float("nan"))),
                "max_post4c_residual": max(
                    abs(float(getattr(entry, name, float("nan"))))
                    for name in ("post4c_residual_px", "post4c_residual_py", "post4c_residual_pz", "post4c_residual_E")
                    if name in branches
                ),
                "mW_had_prefit": float(entry.mW_had_prefit),
                "mt_had_prefit": float(entry.mt_had_prefit),
                "mH_prefit": float(entry.mH_prefit),
                "mW_had_postfit": float(entry.mW_had_postfit),
                "mt_had_postfit": float(entry.mt_had_postfit),
                "mt_lep_postfit": float(entry.mt_lep_postfit),
                "mH_postfit": float(entry.mH_postfit),
                "jet_pull_chi2": float(getattr(entry, "jet_pull_chi2", float("nan"))),
                "lepton_pull_chi2": float(getattr(entry, "lepton_pull_chi2", float("nan"))),
                "neutrino_pull_chi2": float(getattr(entry, "neutrino_pull_chi2", float("nan"))),
                "isr_pull_chi2": float(getattr(entry, "isr_pull_chi2", float("nan"))),
            }
            rows.append(row)
    finally:
        f.Close()
    return rows


def build_truth_map(input_lcio: str, accepted_events: set[int], jet_collection: str, role_source: str) -> Tuple[Dict[int, Dict[int, Dict[str, int]]], Counter]:
    cfg = cfg_for_matching(input_lcio, jet_collection)
    summary = Counter()
    truth_by_event = {}
    for _, _, global_idx, _, _, evt in chi2_reco.iter_lcio_events([input_lcio], max_events=None):
        if int(global_idx) not in accepted_events:
            continue
        reco_col = chi2_reco.get_col(evt, jet_collection)
        if reco_col is None or reco_col.getNumberOfElements() != 6:
            summary["missing_or_wrong_njets"] += 1
            continue
        truth_info, matched = match_semileptonic_event_by_role_source(
            evt, reco_col, cfg, summary, role_source=role_source
        )
        if truth_info is None or matched is None:
            summary["no_truth_match_for_accepted_event"] += 1
            continue
        event_flags = {}
        for combo_id, assignment in ASSIGNMENT_BY_ID.items():
            flags = truth_flags_semileptonic(assignment, matched)
            event_flags[combo_id] = {
                "truth_match_W": int(flags["W"]),
                "truth_match_t": int(flags["top"]),
                "truth_match_H": int(flags["H"]),
                "truth_match_objects": int(flags["W"] and flags["top"] and flags["H"]),
                "truth_match_all": int(flags["all"]),
            }
        truth_by_event[int(global_idx)] = event_flags
    return truth_by_event, summary


def build_flavor_prior_map(
    input_lcio: str,
    accepted_events: set[int],
    flavor_jet_collection: str,
) -> Tuple[Dict[int, Dict[int, Dict[str, float]]], Counter]:
    cfg = cfg_for_matching(input_lcio, flavor_jet_collection)
    summary = Counter()
    out: Dict[int, Dict[int, Dict[str, float]]] = {}
    if not flavor_jet_collection:
        return out, summary
    for _, _, global_idx, _, _, evt in chi2_reco.iter_lcio_events([input_lcio], max_events=None):
        event_index = int(global_idx)
        if event_index not in accepted_events:
            continue
        jets = chi2_reco.get_col(evt, flavor_jet_collection)
        if jets is None:
            summary["missing_flavor_jets"] += 1
            continue
        if jets.getNumberOfElements() != 6:
            summary[f"flavor_njet_{jets.getNumberOfElements()}"] += 1
            continue
        jet_scores = chi2_reco.weaver_score_dicts(jets, cfg)
        if not jet_scores or all(float(s.get("b", SENTINEL)) < -900.0 for s in jet_scores):
            summary["missing_weaver_scores"] += 1
            continue
        leptons = chi2_reco.collect_leptons(evt, cfg)
        lepton_charge = float(leptons[0]["charge"]) if leptons else SENTINEL
        event_map: Dict[int, Dict[str, float]] = {}
        for assignment in SIX_ASSIGNMENTS:
            unsigned, unsigned_comp, _ = flavor_prior_semileptonic(assignment, jet_scores)
            signed, signed_comp, _ = flavor_charge_prior_semileptonic(assignment, jet_scores, lepton_charge)
            event_map[int(assignment["combo_id"])] = {
                "flavor_prior_total": float(unsigned),
                "flavor_prior_W": float(unsigned_comp["W"]),
                "flavor_prior_t": float(unsigned_comp["top"]),
                "flavor_prior_H": float(unsigned_comp["H"]),
                "flavor_charge_prior_total": float(signed),
                "flavor_charge_prior_W": float(signed_comp["W"]),
                "flavor_charge_prior_t": float(signed_comp["top"]),
                "flavor_charge_prior_H": float(signed_comp["H"]),
                "lepton_charge_for_flavor": float(lepton_charge),
            }
        out[event_index] = event_map
        summary["events_with_flavor_priors"] += 1
    return out, summary


def attach_scores_and_truth(
    rows: Sequence[Dict],
    truth: Mapping[int, Mapping[int, Mapping]],
    price: Mapping[str, Mapping[str, float]],
    flavor_priors: Optional[Mapping[int, Mapping[int, Mapping[str, float]]]] = None,
) -> List[Dict]:
    out = []
    for row in rows:
        event_index = int(row["event_index"])
        combo_id = int(row["combo_id"])
        flags = truth.get(event_index, {}).get(combo_id)
        if flags is None:
            continue
        payload = dict(row)
        payload.update(flags)
        payload["root_preselect_score"] = float(row["flavor_score"])
        flavor_payload = (flavor_priors or {}).get(event_index, {}).get(combo_id)
        if flavor_payload is not None:
            payload.update(flavor_payload)
            payload["flavor_score"] = float(flavor_payload["flavor_charge_prior_total"])
            payload["flavor_score_source"] = "lcio_flavor_charge_prior"
        else:
            payload["flavor_prior_total"] = float(row["flavor_score"])
            payload["flavor_charge_prior_total"] = float(row["flavor_score"])
            payload["flavor_score_source"] = "root_top_preselect_score"
        mass = price2014_score(row, price)
        payload["price2014_prefit"] = mass
        payload["price2014_prefit_btag1p00"] = mass + float(payload["flavor_prior_total"])
        payload["price2014_prefit_bcharge0p25"] = mass + 0.25 * float(payload["flavor_charge_prior_total"])
        payload["price2014_prefit_bcharge0p50"] = mass + 0.5 * float(payload["flavor_charge_prior_total"])
        payload["price2014_prefit_bcharge1p00"] = mass + float(payload["flavor_charge_prior_total"])
        payload["kinfit_neglogprob"] = -math.log(max(float(row["fitprob"]), 1.0e-300))
        payload["kinfit_log1pchi2"] = math.log1p(max(0.0, float(row["fitchi2"])))
        out.append(payload)
    return out


KINFit_DEPENDENT_PREFIXES = (
    "kinfit_",
    "flavor_plus_halfchi2_",
    "flavortop",
    "halfchi2_plus_flavor_",
    "neglogprob_plus_flavor_",
    "logchi2_plus_flavor_",
)


def split_flavor_top_mode(mode: str) -> Tuple[Optional[int], str]:
    if not mode.startswith("flavortop"):
        return None, mode
    prefix, _, base = mode.partition("_")
    try:
        top_n = int(prefix.replace("flavortop", ""))
    except ValueError:
        top_n = 0
    return top_n if top_n > 0 else None, base


def base_mode(mode: str) -> str:
    return split_flavor_top_mode(mode)[1]


def mode_uses_kinfit(mode: str) -> bool:
    base = base_mode(str(mode))
    return any(base.startswith(prefix) for prefix in KINFit_DEPENDENT_PREFIXES if prefix != "flavortop")


def valid_for_ranking(row: Mapping, require_converged: bool, mode: str) -> bool:
    if not mode_uses_kinfit(mode):
        return True
    if int(row.get("fit_success", 0)) != 1:
        return False
    if require_converged:
        mass_res = abs(float(row.get("max_mass_constraint_residual", float("inf"))))
        c4_res = abs(float(row.get("max_post4c_residual", float("inf"))))
        if mass_res > 1.0e-3 or c4_res > 1.0e-3:
            return False
    return True


def flavor_top_combo_rows(rows: Sequence[Dict], top_n: int) -> List[Dict]:
    """Keep all rows belonging to the top-N base jet permutations by flavor.

    With SLD/neutrino enumeration, one base combo can have multiple candidate
    rows.  The top-N preselection must therefore count unique ``combo_id``
    values, not physical rows, otherwise "top45" becomes only a few base
    permutations with many SLD solutions.
    """

    ordered_combo_ids: List[int] = []
    seen = set()
    for row in sorted(
        rows,
        key=lambda item: (
            float(item.get("flavor_charge_prior_total", item.get("flavor_score", float("inf")))),
            int(item["candidate_rank"]),
            int(item["combo_id"]),
        ),
    ):
        combo_id = int(row["combo_id"])
        if combo_id in seen:
            continue
        seen.add(combo_id)
        ordered_combo_ids.append(combo_id)
        if len(ordered_combo_ids) >= top_n:
            break
    allowed = set(ordered_combo_ids)
    return [row for row in rows if int(row["combo_id"]) in allowed]


def mode_score(row: Mapping, mode: str) -> Tuple[float, float, int, int]:
    mode = base_mode(mode)
    flavor = float(row["flavor_score"])
    chi2 = float(row["fitchi2"])
    if mode == "flavor_signed_only":
        return (flavor, 0.0, int(row["candidate_rank"]), int(row["combo_id"]))
    if mode == "kinfit_current_cxx":
        return (-float(row["fitprob"]), chi2, int(row["candidate_rank"]), int(row["combo_id"]))
    if mode == "kinfit_chi2_only":
        return (chi2, 0.0, int(row["candidate_rank"]), int(row["combo_id"]))
    if mode == "kinfit_neglogprob_only":
        return (float(row["kinfit_neglogprob"]), chi2, int(row["candidate_rank"]), int(row["combo_id"]))
    if mode in (
        "price2014_prefit",
        "price2014_prefit_btag1p00",
        "price2014_prefit_bcharge0p25",
        "price2014_prefit_bcharge0p50",
        "price2014_prefit_bcharge1p00",
    ):
        return (float(row[mode]), 0.0, int(row["candidate_rank"]), int(row["combo_id"]))
    if mode.startswith("flavor_plus_halfchi2_x"):
        alpha = float(mode.rsplit("x", 1)[1].replace("p", "."))
        return (flavor + alpha * 0.5 * chi2, 0.0, int(row["candidate_rank"]), int(row["combo_id"]))
    if mode.startswith("halfchi2_plus_flavor_x"):
        weight = float(mode.rsplit("x", 1)[1].replace("p", "."))
        return (0.5 * chi2 + weight * flavor, 0.0, int(row["candidate_rank"]), int(row["combo_id"]))
    if mode.startswith("neglogprob_plus_flavor_x"):
        weight = float(mode.rsplit("x", 1)[1].replace("p", "."))
        return (float(row["kinfit_neglogprob"]) + weight * flavor, chi2, int(row["candidate_rank"]), int(row["combo_id"]))
    if mode.startswith("logchi2_plus_flavor_x"):
        weight = float(mode.rsplit("x", 1)[1].replace("p", "."))
        return (float(row["kinfit_log1pchi2"]) + weight * flavor, 0.0, int(row["candidate_rank"]), int(row["combo_id"]))
    raise KeyError(mode)


def select_best_by_mode(rows: Sequence[Dict], modes: Sequence[str], require_converged: bool) -> Dict[str, Dict]:
    out = {}
    for mode in modes:
        valid = [row for row in rows if valid_for_ranking(row, require_converged, mode)]
        if not valid and mode_uses_kinfit(mode):
            valid = [row for row in rows if int(row.get("fit_success", 0)) == 1]
        top_n, _ = split_flavor_top_mode(mode)
        if top_n is not None:
            valid = flavor_top_combo_rows(valid, top_n)
        candidates = [row for row in valid if math.isfinite(mode_score(row, mode)[0])]
        if candidates:
            best = min(candidates, key=lambda row: mode_score(row, mode))
            payload = dict(best)
            payload["rerank_mode"] = mode
            payload["best_score"] = mode_score(best, mode)[0]
            out[mode] = payload
    return out


def metric_row(label: str, mode: str, selected: Sequence[Dict], total_events: int) -> Dict:
    n = len(selected)
    return {
        "source_mode": label,
        "rerank_mode": mode,
        "events": n,
        "total_matched_events": total_events,
        "coverage": float(n / total_events) if total_events else 0.0,
        "A_W": mean([r["truth_match_W"] for r in selected]),
        "A_t": mean([r["truth_match_t"] for r in selected]),
        "A_H": mean([r["truth_match_H"] for r in selected]),
        "A_objects": mean([r["truth_match_objects"] for r in selected]),
        "A_all": mean([r["truth_match_all"] for r in selected]),
        "median_score": quantile([r["best_score"] for r in selected], 0.50),
        "median_candidate_rank": quantile([r["candidate_rank"] for r in selected], 0.50),
        "sld_used_fraction": mean([r.get("sld_used", 0) for r in selected]),
        "median_fit_chi2": quantile([r["fitchi2"] for r in selected], 0.50),
        "median_fitprob": quantile([r["fitprob"] for r in selected], 0.50),
        "median_price2014_prefit": quantile([r["price2014_prefit"] for r in selected], 0.50),
        "median_max_mass_residual": quantile([r["max_mass_constraint_residual"] for r in selected], 0.50),
        "q99_max_mass_residual": quantile([r["max_mass_constraint_residual"] for r in selected], 0.99),
        "median_post4c_residual": quantile([r["max_post4c_residual"] for r in selected], 0.50),
        "q99_post4c_residual": quantile([r["max_post4c_residual"] for r in selected], 0.99),
    }


def summarize(rows_by_source: Mapping[str, List[Dict]], modes: Sequence[str], require_converged: bool) -> Tuple[List[Dict], List[Dict]]:
    selected_rows = []
    metric_rows = []
    for source, rows in rows_by_source.items():
        by_event = defaultdict(list)
        for row in rows:
            by_event[int(row["event_index"])].append(row)
        selected_by_mode = defaultdict(list)
        for event_index, event_rows in by_event.items():
            bests = select_best_by_mode(event_rows, modes, require_converged=require_converged)
            for mode, best in bests.items():
                selected_by_mode[mode].append(best)
                selected_rows.append(best)
        total_events = len(by_event)
        for mode in modes:
            metric_rows.append(metric_row(source, mode, selected_by_mode.get(mode, []), total_events))
    return metric_rows, selected_rows


def write_markdown(outdir: Path, metrics: Sequence[Mapping], counters: Mapping, args: argparse.Namespace) -> None:
    best_by_source = {}
    for source in sorted(set(str(r["source_mode"]) for r in metrics)):
        rows = [r for r in metrics if r["source_mode"] == source and int(r.get("events", 0)) > 0]
        if rows:
            best_by_source[source] = max(rows, key=lambda r: (float(r.get("A_objects", 0.0)), float(r.get("A_all", 0.0))))

    lines = []
    lines.append("# ttH kinfit candidate flavor-informed rerank")
    lines.append("")
    lines.append("## 结论读法")
    lines.append("")
    lines.append("- 这是候选级重排诊断：不重跑 Marlin，不改 processor，只读 candidate debug tree。")
    lines.append("- 若设置 `--flavor-jet-collection`，flavor 项来自该 LCIO jet collection 重新计算的 Weaver prior，而不是 ROOT 里的 preselect score。")
    lines.append("- `flavor_signed_only` 是 signed flavor negative-log likelihood 最小的候选。")
    lines.append("- `kinfit_current_cxx` 是当前 processor 的最终选择逻辑：fit probability 优先，chi2 只作 tie-break。")
    lines.append("- `flavortop45_*` 是先按 signed flavor prior 取 top45，再只用 `*` 指定的非 flavor 最终分数选择。")
    lines.append("- `flavor_plus_halfchi2_x*` 是把 MarlinKinfit pull chi2 按 Gaussian likelihood 形式乘以扫描系数后，加到 signed flavor negative-log likelihood。")
    lines.append("- `price2014_prefit_bcharge*` 是在同一个 top45 candidate pool 上复刻 nominal-mass chi2 + signed flavor penalty，用来和当前 baseline 思路同口径比较。")
    lines.append("")
    lines.append("## Best modes")
    lines.append("")
    lines.append("| source | best mode by A_objects | events | A_objects | A_all | median rank | median fit chi2 | SLD used fraction |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for source, row in best_by_source.items():
        lines.append(
            "| {source_mode} | {rerank_mode} | {events} | {A_objects:.4f} | {A_all:.4f} | {median_candidate_rank:.3g} | {median_fit_chi2:.4g} | {sld_used_fraction:.4f} |".format(**row)
        )
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    lines.append("| source | mode | events | A_W | A_t | A_H | A_objects | A_all | median rank | median score | median chi2 | median mass residual | q99 mass residual |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in metrics:
        if int(row.get("events", 0)) <= 0:
            continue
        lines.append(
            "| {source_mode} | {rerank_mode} | {events} | {A_W:.4f} | {A_t:.4f} | {A_H:.4f} | {A_objects:.4f} | {A_all:.4f} | {median_candidate_rank:.3g} | {median_score:.4g} | {median_fit_chi2:.4g} | {median_max_mass_residual:.4g} | {q99_max_mass_residual:.4g} |".format(**row)
        )
    lines.append("")
    lines.append("## Counters")
    lines.append("")
    for key, value in sorted(counters.items()):
        lines.append(f"- `{key}`: {value}")
    lines.append("")
    lines.append("## Inputs")
    lines.append("")
    lines.append(f"- LCIO: `{args.input_lcio}`")
    lines.append(f"- current ROOT: `{args.current_root}`")
    lines.append(f"- SLD ROOT: `{args.sld_root}`")
    lines.append(f"- truth role source: `{args.role_source}`")
    lines.append(f"- fit/truth jet collection: `{args.jet_collection}`")
    lines.append(f"- flavor jet collection: `{args.flavor_jet_collection}`")
    lines.append(f"- require converged constraints for ranking: `{args.require_converged}`")
    lines.append("")
    lines.append("## Outputs")
    lines.append("")
    lines.append(f"- `{outdir / 'kinfit_flavor_rerank_metrics.csv'}`")
    lines.append(f"- `{outdir / 'kinfit_flavor_rerank_selected.csv'}`")
    (outdir / "kinfit_flavor_rerank_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-lcio", default=DEFAULT_LCIO)
    parser.add_argument("--current-root", default=DEFAULT_CURRENT_ROOT)
    parser.add_argument("--sld-root", default=DEFAULT_SLD_ROOT)
    parser.add_argument("--model-bundle", default=DEFAULT_MODEL_BUNDLE)
    parser.add_argument("--outdir", default=DEFAULT_OUTDIR)
    parser.add_argument("--jet-collection", default="RefinedJets6")
    parser.add_argument(
        "--flavor-jet-collection",
        default="",
        help="Optional LCIO jet collection used to recompute Weaver flavor priors, e.g. RefinedJets6 when the fit uses OutputErrorFlowJets6.",
    )
    parser.add_argument("--role-source", default="legacy_ancestry", choices=["legacy_ancestry", "truejet_direct"])
    parser.add_argument("--require-converged", action="store_true")
    return parser.parse_args()


def main() -> None:
    ROOT.gROOT.SetBatch(True)
    args = parse_args()
    outdir = ensure_dir(args.outdir)
    price = load_price2014(args.model_bundle)
    top_current, accepted_current = read_top_score_map(args.current_root)
    top_sld, accepted_sld = read_top_score_map(args.sld_root)
    accepted_events = set(accepted_current) | set(accepted_sld)
    truth, truth_summary = build_truth_map(args.input_lcio, accepted_events, args.jet_collection, args.role_source)
    flavor_priors, flavor_summary = build_flavor_prior_map(
        args.input_lcio, accepted_events, args.flavor_jet_collection
    )
    current_rows = attach_scores_and_truth(
        read_candidate_rows(args.current_root, "current", top_current), truth, price, flavor_priors
    )
    sld_rows = attach_scores_and_truth(
        read_candidate_rows(args.sld_root, "sld_enumeration", top_sld), truth, price, flavor_priors
    )

    alphas = ["0", "0p0001", "0p0003", "0p001", "0p003", "0p01", "0p03", "0p1", "0p3", "1"]
    flavor_weights = [
        "0", "0p01", "0p03", "0p05", "0p1", "0p2", "0p3", "0p4",
        "0p5", "0p6", "0p75", "0p9", "1", "1p1", "1p25", "1p5", "2", "4",
    ]
    log_weights = [
        "0", "0p01", "0p03", "0p05", "0p1", "0p15", "0p2", "0p25",
        "0p3", "0p4", "0p5", "0p75", "1", "2", "4",
    ]
    modes = [
        "flavor_signed_only",
        "kinfit_current_cxx",
        "kinfit_chi2_only",
        "kinfit_neglogprob_only",
        "flavortop45_kinfit_current_cxx",
        "flavortop45_kinfit_chi2_only",
        "flavortop45_kinfit_neglogprob_only",
        "flavortop45_price2014_prefit",
        "price2014_prefit",
        "price2014_prefit_btag1p00",
        "price2014_prefit_bcharge0p25",
        "price2014_prefit_bcharge0p50",
        "price2014_prefit_bcharge1p00",
    ] + [f"flavor_plus_halfchi2_x{x}" for x in alphas]
    modes += [f"halfchi2_plus_flavor_x{x}" for x in flavor_weights]
    modes += [f"neglogprob_plus_flavor_x{x}" for x in flavor_weights]
    modes += [f"logchi2_plus_flavor_x{x}" for x in log_weights]

    metrics, selected = summarize(
        {"current": current_rows, "sld_enumeration": sld_rows},
        modes,
        require_converged=bool(args.require_converged),
    )
    counters = Counter(truth_summary)
    counters.update({f"flavor_{key}": value for key, value in flavor_summary.items()})
    counters["accepted_events_from_root"] = len(accepted_events)
    counters["truth_matched_accepted_events"] = len(truth)
    counters["flavor_priors_events"] = len(flavor_priors)
    counters["current_candidate_rows_with_truth"] = len(current_rows)
    counters["sld_candidate_rows_with_truth"] = len(sld_rows)
    counters["require_converged"] = int(bool(args.require_converged))

    write_csv(outdir / "kinfit_flavor_rerank_metrics.csv", metrics)
    write_csv(outdir / "kinfit_flavor_rerank_selected.csv", selected)
    (outdir / "kinfit_flavor_rerank_counters.json").write_text(
        json.dumps(dict(counters), indent=2, sort_keys=True), encoding="utf-8"
    )
    write_markdown(outdir, metrics, counters, args)
    print(f"Wrote rerank outputs to {outdir}")


if __name__ == "__main__":
    main()
