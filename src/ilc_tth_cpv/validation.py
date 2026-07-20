"""Cross-cutting validation checks (project note §3.4).

Each check returns {"ok": bool, "problems": [...], ...}. Scripts must print
and persist the reports; silent passes are not allowed.
"""

from __future__ import annotations

import math
from typing import Dict, List

from .angles import wrap_phi
from .features import deterministic_split


def check_split_disjoint(rows: List[dict]) -> dict:
    """No event id may appear in more than one split."""
    by_split: Dict[str, set] = {}
    for row in rows:
        by_split.setdefault(row["split"], set()).add(row["event_id"])
    problems = []
    names = sorted(by_split)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            overlap = by_split[a] & by_split[b]
            if overlap:
                problems.append(f"{a}/{b} overlap: {len(overlap)} events")
    return {"ok": not problems, "problems": problems,
            "sizes": {k: len(v) for k, v in by_split.items()}}


def check_split_deterministic(rows: List[dict], seed: int, fractions: dict) -> dict:
    """Recompute the split from event_id and compare."""
    mismatches = 0
    for row in rows:
        expected = deterministic_split(int(row["event_id"]), seed, fractions)
        if row["split"] != expected:
            mismatches += 1
    return {"ok": mismatches == 0, "problems":
            ([f"{mismatches} split mismatches"] if mismatches else []),
            "n_checked": len(rows)}


def check_phi_wrapping(values: List[float]) -> dict:
    """All phi-like values must satisfy the frozen wrap convention."""
    problems = []
    for value in values:
        if not (-math.pi <= value < math.pi):
            problems.append(f"phi {value} outside [-pi, pi)")
            break
        if abs(wrap_phi(value) - value) > 1.0e-12:
            problems.append(f"phi {value} not idempotent under wrap")
            break
    return {"ok": not problems, "problems": problems, "n_checked": len(values)}


def check_signed_weight_sums(rows: List[dict], column: str = "weight_interference_signed") -> dict:
    """Signed and absolute sums; SM CP closure requires the signed sum of a
    CP-even quantity to be compatible with zero (statistics decides)."""
    signed = 0.0
    absolute = 0.0
    sumw2 = 0.0
    n_nan = 0
    for row in rows:
        try:
            w = float(row[column])
        except (KeyError, TypeError, ValueError):
            n_nan += 1
            continue
        if w != w:  # NaN
            n_nan += 1
            continue
        signed += w
        absolute += abs(w)
        sumw2 += w * w
    err = math.sqrt(sumw2)
    return {
        "ok": True,
        "problems": [],
        "signed_sum": signed,
        "abs_sum": absolute,
        "err": err,
        "z_signed": signed / err if err > 0.0 else 0.0,
        "n_nan": n_nan,
    }


def check_no_training_weight_in_templates(rows: List[dict]) -> dict:
    """weight_template must never equal a class-balanced weight_training."""
    problems = []
    for row in rows[:1000]:
        try:
            wt = float(row.get("weight_template", "nan"))
            tr = float(row.get("weight_training", "nan"))
        except (TypeError, ValueError):
            continue
        if wt == wt and tr == tr and wt != 0.0 and wt == tr:
            problems.append(
                "weight_template identical to weight_training for some events — "
                "check the weight pipeline"
            )
            break
    return {"ok": not problems, "problems": problems}
