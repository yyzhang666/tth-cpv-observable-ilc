#!/usr/bin/env python3
"""Plot the frozen historical 830-event assignment-mass diagnostic."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path


SOURCE_MODE = "sld_enumeration"
EXPECTED_COMMON = 830
PRICE_MODE = "price2014_prefit_bcharge1p00"
KINFIT_MODE = "logchi2_plus_flavor_x0p3"
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
BINS = 60
TITLE = "Historical 830-event Whizard eL.pR diagnostic; offline rerank"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assert_new_output_dir(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise RuntimeError(f"refusing to reuse output directory: {path}")


def read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise RuntimeError("selected CSV has no header")
        return list(reader), list(reader.fieldnames)


def validate_common_rows(
    rows: list[dict[str, str]], fieldnames: list[str], expected_common: int = EXPECTED_COMMON
) -> tuple[dict[str, dict[int, dict[str, str]]], list[int], dict[str, object]]:
    required = {"source_mode", "rerank_mode", "event_index"}
    for spec in MODE_SPECS.values():
        required.update(spec["columns"].values())
    missing = sorted(required - set(fieldnames))
    if missing:
        raise RuntimeError(f"selected CSV missing required columns: {missing}")

    selected: dict[str, dict[int, dict[str, str]]] = {mode: {} for mode in MODE_SPECS}
    for row in rows:
        if row["source_mode"] != SOURCE_MODE or row["rerank_mode"] not in selected:
            continue
        mode = row["rerank_mode"]
        try:
            event_index = int(row["event_index"])
        except Exception as exc:
            raise RuntimeError(f"invalid event_index for {mode}: {row['event_index']!r}") from exc
        if event_index in selected[mode]:
            raise RuntimeError(f"duplicate row for mode={mode}, event_index={event_index}")
        selected[mode][event_index] = row

    common = sorted(set(selected[PRICE_MODE]) & set(selected[KINFIT_MODE]))
    if len(common) != expected_common:
        raise RuntimeError(
            f"common event intersection has {len(common)} events, expected {expected_common}"
        )

    for mode, spec in MODE_SPECS.items():
        for event_index in common:
            row = selected[mode][event_index]
            for column in spec["columns"].values():
                try:
                    value = float(row[column])
                except Exception as exc:
                    raise RuntimeError(
                        f"non-numeric {column} for mode={mode}, event_index={event_index}"
                    ) from exc
                if not math.isfinite(value):
                    raise RuntimeError(
                        f"non-finite {column} for mode={mode}, event_index={event_index}"
                    )

    combo_available = "combo_id" in fieldnames
    combo_differences = None
    if combo_available:
        combo_differences = 0
        for event_index in common:
            price_combo = selected[PRICE_MODE][event_index].get("combo_id", "")
            kinfit_combo = selected[KINFIT_MODE][event_index].get("combo_id", "")
            if price_combo == "" or kinfit_combo == "":
                raise RuntimeError(f"blank combo_id for common event_index={event_index}")
            combo_differences += int(price_combo != kinfit_combo)

    return selected, common, {
        "combo_id_available": combo_available,
        "differing_combo_id_events": combo_differences,
        "selected_key_counts": {mode: len(by_event) for mode, by_event in selected.items()},
    }


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


def gnuplot_quote(value: str | Path) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_plot(histograms: dict[str, dict[str, dict[str, object]]], output: Path, terminal: str) -> None:
    with tempfile.TemporaryDirectory(prefix="historical_assignment_masses_") as directory:
        tempdir = Path(directory)
        data_paths = {}
        for obj in OBJECT_SPECS:
            path = tempdir / f"{obj}.dat"
            price = histograms[obj][PRICE_MODE]
            kinfit = histograms[obj][KINFIT_MODE]
            centers = [
                (price["edges"][index] + price["edges"][index + 1]) / 2.0
                for index in range(BINS)
            ]
            lines = [
                f"{center:.12g} {price['counts'][index] / EXPECTED_COMMON:.12g} "
                f"{kinfit['counts'][index] / EXPECTED_COMMON:.12g}"
                for index, center in enumerate(centers)
            ]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            data_paths[obj] = path

        commands = [
            f"set terminal {terminal}",
            f"set output {gnuplot_quote(output)}",
            "set multiplot layout 1,3 title " + gnuplot_quote(TITLE),
            "set grid ytics lc rgb '#cccccc'",
            "set style data steps",
            "set key top right font ',9'",
        ]
        for obj, object_spec in OBJECT_SPECS.items():
            low, high = object_spec["range"]
            commands.extend(
                [
                    f"set xrange [{low}:{high}]",
                    "set yrange [0:*]",
                    f"set title {gnuplot_quote(obj)}",
                    f"set xlabel {gnuplot_quote(f'{obj} mass [GeV]')}",
                    "set ylabel " + gnuplot_quote("fraction of common events / bin"),
                    f"set arrow 1 from {object_spec['target']}, graph 0 to {object_spec['target']}, graph 1 nohead dt 2 lc rgb '#222222'",
                    "plot "
                    + f"{gnuplot_quote(data_paths[obj])} using 1:2 with steps lw 2 lc rgb '#2364aa' title "
                    + gnuplot_quote(MODE_SPECS[PRICE_MODE]["label"])
                    + ", '' using 1:3 with steps lw 2 lc rgb '#d95f02' title "
                    + gnuplot_quote(MODE_SPECS[KINFIT_MODE]["label"]),
                    "unset arrow 1",
                ]
            )
        commands.extend(["unset multiplot", "unset output"])
        script = tempdir / "plot.gnuplot"
        script.write_text("\n".join(commands) + "\n", encoding="utf-8")
        subprocess.run(["gnuplot", str(script)], check=True)


def generate(input_csv: Path, output_dir: Path) -> dict[str, object]:
    assert_new_output_dir(output_dir)
    rows, fieldnames = read_rows(input_csv)
    selected, common, combo_summary = validate_common_rows(rows, fieldnames)
    output_dir.mkdir(parents=True)

    summary_rows = []
    histograms: dict[str, dict[str, dict[str, object]]] = {}
    for obj, object_spec in OBJECT_SPECS.items():
        histograms[obj] = {}
        low, high = object_spec["range"]
        for mode, mode_spec in MODE_SPECS.items():
            column = mode_spec["columns"][obj]
            values = [float(selected[mode][event_index][column]) for event_index in common]
            accounting = histogram_accounting(values, low, high, BINS, len(common))
            histograms[obj][mode] = accounting
            summary_rows.append(
                {
                    "object": obj,
                    "mode": mode,
                    "stage": "PREFIT" if mode == PRICE_MODE else "POSTFIT",
                    "column": column,
                    "common_events": len(common),
                    "underflow": accounting["underflow"],
                    "in_range": accounting["in_range"],
                    "overflow": accounting["overflow"],
                    "closure_count": accounting["closure_count"],
                    "underflow_fraction": accounting["underflow_fraction"],
                    "in_range_fraction": accounting["in_range_fraction"],
                    "overflow_fraction": accounting["overflow_fraction"],
                    "closure_fraction": accounting["closure_fraction"],
                }
            )
    prefix = output_dir / "historical830_price_prefit_vs_kinfit_postfit"
    png = prefix.with_suffix(".png")
    pdf = prefix.with_suffix(".pdf")
    render_plot(histograms, png, "pngcairo size 2376,756 font 'Arial,18'")
    render_plot(histograms, pdf, "pdfcairo enhanced color size 13.2in,4.2in font 'Arial,12'")

    summary_csv = output_dir / "summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)

    manifest = {
        "diagnostic_label": TITLE,
        "input_csv": str(input_csv.resolve()),
        "input_sha256": sha256(input_csv),
        "source_mode": SOURCE_MODE,
        "expected_common_events": EXPECTED_COMMON,
        "common_events": len(common),
        "common_event_index_min": min(common),
        "common_event_index_max": max(common),
        "common_event_indices_sha256": hashlib.sha256(
            ",".join(str(value) for value in common).encode("ascii")
        ).hexdigest(),
        **combo_summary,
        "bins": BINS,
        "objects": OBJECT_SPECS,
        "modes": MODE_SPECS,
        "histogram_accounting": histograms,
        "outputs": {
            "png": {"path": str(png), "sha256": sha256(png)},
            "pdf": {"path": str(pdf), "sha256": sha256(pdf)},
            "summary_csv": {"path": str(summary_csv), "sha256": sha256(summary_csv)},
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = generate(args.input_csv, args.output_dir)
    print(json.dumps({
        "common_events": manifest["common_events"],
        "differing_combo_id_events": manifest["differing_combo_id_events"],
        "output_dir": str(args.output_dir),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
