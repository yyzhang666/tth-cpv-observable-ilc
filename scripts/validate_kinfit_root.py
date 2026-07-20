#!/usr/bin/env python3
"""Validate one TTHSemiLepKinFit ROOT output before accepting a job."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DEFAULT_BRANCHES = (
    "accepted",
    "fit_success",
    "fit_status",
    "fitchi2",
    "ndof",
    "fitprob",
    "final_selection_mode",
    "flavor_weight",
    "final_selection_score",
    "final_fit_score",
    "final_flavor_score",
)


def root_error(message: str) -> int:
    print(f"[validate_kinfit_root] FAILED: {message}", file=sys.stderr)
    return 1


def branch_names(tree) -> set[str]:
    return {str(branch.GetName()) for branch in tree.GetListOfBranches()}


def count_selected(tree, branches: set[str]) -> int | None:
    if not {"accepted", "fit_success"}.issubset(branches):
        return None
    selected = 0
    for idx in range(int(tree.GetEntries())):
        tree.GetEntry(idx)
        try:
            if int(getattr(tree, "accepted")) == 1 and int(getattr(tree, "fit_success")) == 1:
                selected += 1
        except Exception:
            return None
    return selected


def final_selection_report(
    tree,
    branches: set[str],
    expected_mode: str | None,
    expected_weight: float | None,
    tolerance: float,
) -> dict:
    needed = {
        "final_selection_mode",
        "flavor_weight",
        "final_selection_score",
        "final_fit_score",
        "final_flavor_score",
    }
    report = {
        "checked": False,
        "modes": [],
        "flavor_weights": [],
        "max_abs_score_residual": None,
        "problems": [],
    }
    if not needed.issubset(branches):
        return report

    modes = set()
    weights = set()
    max_residual = 0.0
    for idx in range(int(tree.GetEntries())):
        tree.GetEntry(idx)
        mode = str(getattr(tree, "final_selection_mode"))
        weight = float(getattr(tree, "flavor_weight"))
        score = float(getattr(tree, "final_selection_score"))
        fit_score = float(getattr(tree, "final_fit_score"))
        flavor_score = float(getattr(tree, "final_flavor_score"))
        modes.add(mode)
        weights.add(round(weight, 8))
        max_residual = max(max_residual, abs(score - (fit_score + weight * flavor_score)))

    report["checked"] = True
    report["modes"] = sorted(modes)
    report["flavor_weights"] = sorted(weights)
    report["max_abs_score_residual"] = max_residual
    if expected_mode and modes != {expected_mode}:
        report["problems"].append(
            f"final_selection_mode is {sorted(modes)}, expected {expected_mode!r}"
        )
    if expected_weight is not None:
        for weight in weights:
            if abs(weight - expected_weight) > tolerance:
                report["problems"].append(
                    f"flavor_weight includes {weight}, expected {expected_weight}"
                )
                break
    if max_residual > tolerance:
        report["problems"].append(
            "final_selection_score inconsistent with "
            f"final_fit_score + flavor_weight*final_flavor_score "
            f"(max residual {max_residual:g})"
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="ROOT file to validate")
    parser.add_argument("--tree", default="TTHSemiLepKinFit")
    parser.add_argument("--min-entries", type=int, default=1)
    parser.add_argument("--require-branches", nargs="*", default=list(DEFAULT_BRANCHES))
    parser.add_argument("--expected-final-selection-mode", default="logchi2_plus_flavor",
                        help="empty string disables the mode check")
    parser.add_argument("--expected-flavor-weight", type=float, default=0.3,
                        help="set negative to disable the weight check")
    parser.add_argument("--score-tolerance", type=float, default=1.0e-5)
    parser.add_argument("--out", default=None, help="write validation JSON")
    args = parser.parse_args()

    root_path = Path(args.root)
    if not root_path.exists():
        return root_error(f"missing file: {root_path}")
    if root_path.stat().st_size <= 0:
        return root_error(f"empty file: {root_path}")

    try:
        import ROOT  # type: ignore
    except Exception as exc:
        return root_error(f"cannot import ROOT; source env/setup.sh first ({exc})")

    handle = ROOT.TFile.Open(str(root_path))
    if not handle or handle.IsZombie():
        return root_error(f"cannot open ROOT file: {root_path}")
    tree = handle.Get(args.tree)
    if tree is None:
        handle.Close()
        return root_error(f"missing tree {args.tree!r} in {root_path}")

    entries = int(tree.GetEntries())
    branches = branch_names(tree)
    missing = [name for name in args.require_branches if name not in branches]
    selected_entries = count_selected(tree, branches)
    expected_mode = args.expected_final_selection_mode or None
    expected_weight = (
        args.expected_flavor_weight
        if args.expected_flavor_weight >= 0.0
        else None
    )
    selection_report = final_selection_report(
        tree,
        branches,
        expected_mode,
        expected_weight,
        args.score_tolerance,
    )
    payload = {
        "root": str(root_path),
        "tree": args.tree,
        "entries": entries,
        "min_entries": args.min_entries,
        "required_branches": list(args.require_branches),
        "missing_branches": missing,
        "selected_entries": selected_entries,
        "final_selection_report": selection_report,
        "ok": entries >= args.min_entries and not missing and not selection_report["problems"],
    }
    handle.Close()

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)

    if not payload["ok"]:
        if entries < args.min_entries:
            return root_error(f"tree {args.tree!r} has {entries} entries")
        if missing:
            return root_error(f"missing required branches: {', '.join(missing)}")
        return root_error("; ".join(selection_report["problems"]))

    suffix = (
        f", selected={selected_entries}"
        if selected_entries is not None
        else ""
    )
    score_suffix = ""
    if selection_report["checked"]:
        score_suffix = (
            f", mode={','.join(selection_report['modes'])}"
            f", max_score_residual={selection_report['max_abs_score_residual']:.3g}"
        )
    print(f"[validate_kinfit_root] OK: entries={entries}{suffix}{score_suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
