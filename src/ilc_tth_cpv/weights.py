"""Signed CP-interference weights: sidecar reading and stdhep alignment.

Ported from analysis/tth/generator_study/compute_tthcpv_ma2018_observables.py
(read_sidecar, parse_skipped_events_from_log). See docs/SAMPLE_PROVENANCE.md
for the alignment rule.

Sidecar CSV columns (tthcpv_me.csv):
    event                  1-based accepted-event number
    sign                   +1 / -1 sign of the interference term
    event_weight_signed    sign * sigma_absint / n_generated  [fb]
    sigma_absint           |interference| cross-section [fb]
    n_generated            total generated events
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Optional

SKIP_PATTERN = re.compile(r"requested the event\s+(\d+)\s+to be skipped")

SIDECAR_COLUMNS = (
    "event",
    "sign",
    "event_weight_signed",
    "sigma_absint",
    "n_generated",
)


def read_sidecar(path: Path) -> list:
    """Read the matrix-element sidecar with a strict event-order check."""
    with Path(path).open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    out = []
    for seq, row in enumerate(rows, start=1):
        csv_event = int(row["event"])
        if csv_event != seq:
            raise RuntimeError(
                f"Sidecar event order mismatch at row {seq}: event={csv_event}"
            )
        out.append(
            {
                "event": csv_event,
                "sign": int(row["sign"]),
                "event_weight_signed": float(row["event_weight_signed"]),
                "sigma_absint": float(row["sigma_absint"]),
                "n_generated": int(row["n_generated"]),
            }
        )
    return out


def parse_skipped_events_from_log(path: Optional[Path]) -> set:
    """Event numbers skipped by JSFHadronizer, parsed from the physsim log."""
    if path is None:
        return set()
    path = Path(path)
    if not path.exists():
        return set()
    skipped = set()
    with path.open(errors="replace") as stream:
        for line in stream:
            match = SKIP_PATTERN.search(line)
            if match:
                skipped.add(int(match.group(1)))
    return skipped


def align_sidecar_to_stdhep(sidecar_rows: list, skipped_events: set) -> list:
    """Remove skipped rows so the list order matches the stdhep event order."""
    return [row for row in sidecar_rows if row["event"] not in skipped_events]


def validate_signed_weights(rows: list, tolerance: float = 1.0e-9) -> dict:
    """Consistency checks used before any physics filling.

    - sign column matches the sign of event_weight_signed;
    - |event_weight_signed| = sigma_absint / n_generated within tolerance;
    - constant sigma_absint and n_generated across the sample.
    """
    problems = []
    sigma_values = {row["sigma_absint"] for row in rows}
    ngen_values = {row["n_generated"] for row in rows}
    if len(sigma_values) > 1:
        problems.append(f"sigma_absint not constant: {sorted(sigma_values)[:5]} ...")
    if len(ngen_values) > 1:
        problems.append(f"n_generated not constant: {sorted(ngen_values)[:5]} ...")
    for row in rows:
        expected_abs = row["sigma_absint"] / row["n_generated"]
        if abs(abs(row["event_weight_signed"]) - expected_abs) > tolerance * max(
            1.0, expected_abs
        ):
            problems.append(
                f"event {row['event']}: |w|={abs(row['event_weight_signed'])} "
                f"!= sigma/n={expected_abs}"
            )
            break
        if row["sign"] * row["event_weight_signed"] < 0:
            problems.append(f"event {row['event']}: sign/weight mismatch")
            break
    n_pos = sum(1 for row in rows if row["sign"] > 0)
    n_neg = sum(1 for row in rows if row["sign"] < 0)
    signed_sum = sum(row["event_weight_signed"] for row in rows)
    return {
        "ok": not problems,
        "problems": problems,
        "n_rows": len(rows),
        "n_pos": n_pos,
        "n_neg": n_neg,
        "signed_sum_fb": signed_sum,
    }


def training_weight(event_weight_signed: float) -> float:
    """Training weight is |w_int| (class balancing applied later, in training
    code only). Physics templates must keep the signed weight."""
    return abs(float(event_weight_signed))
