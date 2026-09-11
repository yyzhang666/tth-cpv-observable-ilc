#!/usr/bin/env python3
"""Run frozen purity scripts and joined two-branch multiplicity counting."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_tagger_origins(text):
    output = {}
    current = None
    correct = False
    for line in text.splitlines():
        match = re.match(r"^\[HBB\|(SEMI|DI)\] (EL|MU)\s+total=(\d+)", line)
        if match:
            current = (match.group(1), match.group(2))
            output[current] = {"entries": int(match.group(3)), "origins": {}}
            correct = False
            continue
        if current and re.match(r"^\s+tag_correct:", line):
            output[current]["denominator"] = int(re.search(r"tag_correct:\s+(\d+)", line).group(1))
            correct = True
            continue
        if current and re.match(r"^\s+tag_wrong:", line):
            correct = False
            continue
        match = re.match(r"^\s+(origin_from_topW|origin_from_tau|origin_from_hadron)\s*:\s*(\d+)", line)
        if current and correct and match:
            output[current]["origins"][match.group(1).replace("origin_", "")] = int(match.group(2))
    return output


def parse_finder_origins(text):
    output = {}
    channel = None
    current = None
    for line in text.splitlines():
        match = re.match(r"^=+\s+HBB \| (SEMI|DI)\s+=+$", line)
        if match:
            channel = match.group(1)
            current = None
            continue
        match = re.match(r"^-- PID =\s+(e_like|mu_like)\s+entries=(\d+)", line)
        if channel and match:
            flavor = "EL" if match.group(1) == "e_like" else "MU"
            current = (channel, flavor)
            output[current] = {"entries": int(match.group(2)), "denominator": int(match.group(2)), "origins": {}}
            continue
        match = re.match(r"^\s+(from_topW|from_tau|from_hadron)\s*:\s*(\d+)", line)
        if current and match:
            output[current]["origins"][match.group(1)] = int(match.group(2))
    return output


def serializable(value):
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, dict):
        return {str(key): serializable(item) for key, item in value.items()}
    return value


def open_reader(path):
    from pyLCIO import IOIMPL

    reader = IOIMPL.LCFactory.getInstance().createLCReader()
    reader.open(str(path))
    return reader


def joined_multiplicity(complete_paths, finder_paths, source_ids, legacy_dir, max_events):
    had = load_module("legacy_had", legacy_dir / "count_hbb_ttbar_had_iso_pass.py")
    dilep = load_module("legacy_dilep", legacy_dir / "count_hbb_ttbar_dilep_pass.py")
    had_stats = defaultdict(had.init_stat)
    dilep_stats = defaultdict(dilep.init_stat)
    processed = 0
    for complete_path, finder_path, source_id in zip(complete_paths, finder_paths, source_ids):
        complete_reader, finder_reader = open_reader(complete_path), open_reader(finder_path)
        try:
            while max_events < 0 or processed < max_events:
                complete_event = complete_reader.readNextEvent()
                finder_event = finder_reader.readNextEvent()
                if complete_event is None or finder_event is None:
                    if complete_event is not None or finder_event is not None:
                        raise RuntimeError(f"branch length mismatch for {source_id}")
                    break
                complete_key = (source_id, int(complete_event.getRunNumber()), int(complete_event.getEventNumber()))
                finder_key = (source_id, int(finder_event.getRunNumber()), int(finder_event.getEventNumber()))
                if complete_key != finder_key:
                    raise RuntimeError(f"event key mismatch: {complete_key} != {finder_key}")
                nmu_name, nmu = had.get_n_reco(complete_event, "ISOMuons", ["ISOMuons", "IsolatedMuons"])
                nel_name, nel = had.get_n_reco(complete_event, "ISOElectrons", ["ISOElectrons", "IsolatedElectrons"])
                niso_name, niso = had.get_n_reco(finder_event, "Isolep", ["Isolep", "IsolatedLeptons", "IsolatedLepton", "Leptons"])

                channel, tau_direct = had.truth_ttbar_channel_and_tau(complete_event, colMC="MCParticlesSkimmed")
                hbb = had.truth_h_to_bb(complete_event, colMC="MCParticlesSkimmed")
                if channel in ("had", "semilep_e", "semilep_mu", "semilep_tau", "semilep_lep", "dilep"):
                    had.update_stat(had_stats[f"ALL|{channel}"], nmu_name, nmu, nel_name, nel, niso_name, niso, tau_direct=tau_direct, is_dilep=(channel == "dilep"))
                    if hbb is True:
                        had.update_stat(had_stats[f"HBB|{channel}"], nmu_name, nmu, nel_name, nel, niso_name, niso, tau_direct=tau_direct, is_dilep=(channel == "dilep"))

                di_channel, di_tau = dilep.truth_ttbar_channel_and_tau(complete_event, colMC="MCParticlesSkimmed")
                if di_channel == "dilep" and dilep.truth_h_to_bb(complete_event, colMC="MCParticlesSkimmed") is True:
                    group = "HAS_TAU" if di_tau else "NO_TAU"
                    dilep.update_stat(dilep_stats[group], nmu_name, nmu, nel_name, nel, niso_name, niso)
                processed += 1
        finally:
            complete_reader.close()
            finder_reader.close()
        if max_events >= 0 and processed >= max_events:
            break
    return {"events_processed": processed, "semileptonic_logic": serializable(dict(had_stats)), "dileptonic_logic": serializable(dict(dilep_stats))}


def run_frozen(script, inputs, extra, log_path):
    command = [sys.executable, str(script), *[str(path) for path in inputs], *extra]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    log_path.write_text(result.stdout, encoding="utf-8")
    return result.stdout


def purity_rows(tagger, finder):
    rows = []
    for method, payload in (("Tagger", tagger), ("Finder", finder)):
        for channel in ("SEMI", "DI"):
            for flavor in ("EL", "MU"):
                item = payload[(channel, flavor)]
                origins = item["origins"]
                denominator = sum(origins.get(key, 0) for key in ("from_topW", "from_tau", "from_hadron"))
                if denominator <= 0:
                    raise RuntimeError(f"zero three-origin denominator for {method}/{channel}/{flavor}")
                rows.append({
                    "method": method,
                    "channel": channel,
                    "lepton": flavor,
                    "denominator": denominator,
                    **{key: origins.get(key, 0) for key in ("from_topW", "from_tau", "from_hadron")},
                })
    return rows


def percentage(count, denominator):
    return f"{100.0 * count / denominator:.2f}%" if denominator else "n/a"


def write_channel_table(channel, purity, multiplicity, output):
    import matplotlib.pyplot as plt

    selected = [row for row in purity if row["channel"] == channel]
    purity_labels = [f"{row['method']} {row['lepton']}" for row in selected]
    purity_cells = [
        [percentage(row[key], row["denominator"]) for key in ("from_topW", "from_tau", "from_hadron")]
        for row in selected
    ]
    if channel == "SEMI":
        lower_labels, lower_cells = [], []
        lower_columns = ["0 ISOE", "0 ISOMu", "0 ISOE+Mu", "0 Isolep", "1 ISOE", "1 ISOMu", "1 Isolep"]
        for truth_channel in ("had", "semilep_e", "semilep_mu", "semilep_tau"):
            block = multiplicity["semileptonic_logic"].get(f"HBB|{truth_channel}", {"n": 0, "cnt": {}})
            denominator, counts = block["n"], block["cnt"]
            lower_labels.append(truth_channel)
            lower_cells.append([percentage(counts.get(key, 0), denominator) for key in ("ISOElectrons==0", "ISOMuons==0", "mu0_el0", "Isolep==0", "ISOElectrons==1", "ISOMuons==1", "Isolep==1")])
    else:
        lower_labels, lower_cells = [], []
        lower_columns = ["0 ISOE+Mu", "0 Isolep", "1 ISOE+Mu", "1 Isolep", "2 ISOE+Mu", "2 Isolep"]
        for group in ("NO_TAU", "HAS_TAU"):
            block = multiplicity["dileptonic_logic"].get(group, {"n": 0, "pass": {}})
            denominator, counts = block["n"], block["pass"]
            lower_labels.append(group)
            lower_cells.append([percentage(counts.get(key, 0), denominator) for key in ("MU0_EL0", "ISOLEP0", "MUEL_SUM1", "ISOLEP1", "MUEL_SUM2", "ISOLEP2")])
    figure, axes = plt.subplots(2, 1, figsize=(12, 6.8), gridspec_kw={"height_ratios": [1.0, 1.35]})
    for axis in axes:
        axis.axis("off")
    axes[0].table(cellText=purity_cells, rowLabels=purity_labels, colLabels=["Top→W", "Tau", "Hadron"], loc="center")
    axes[1].table(cellText=lower_cells, rowLabels=lower_labels, colLabels=lower_columns, loc="center")
    figure.suptitle("H→bb, semileptonic" if channel == "SEMI" else "H→bb, dileptonic")
    figure.tight_layout()
    figure.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(figure)


def multiplicity_rows(payload):
    rows = []
    for key, block in payload["semileptonic_logic"].items():
        for selection, count in block.get("cnt", {}).items():
            rows.append({"logic": "semileptonic", "category": key, "denominator": block["n"], "selection": selection, "count": count})
    for key, block in payload["dileptonic_logic"].items():
        for selection, count in block.get("pass", {}).items():
            rows.append({"logic": "dileptonic", "category": key, "denominator": block["n"], "selection": selection, "count": count})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--complete", type=Path, action="append", required=True)
    parser.add_argument("--finder", type=Path, action="append", required=True)
    parser.add_argument("--source-file-id", action="append", required=True)
    parser.add_argument("--legacy-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-events", type=int, default=-1)
    args = parser.parse_args()
    if not (len(args.complete) == len(args.finder) == len(args.source_file_id)):
        raise ValueError("complete, finder, and source-file-id lists must have equal length")
    output = args.output_dir.resolve(strict=False)
    output.mkdir(parents=True, exist_ok=True)
    targets = [output / name for name in ("tagger_stdout.txt", "finder_stdout.txt", "lepton_counts.json", "lepton_purity.csv", "lepton_multiplicity.csv", "semileptonic_lepton_table.png", "dileptonic_lepton_table.png")]
    if any(path.exists() or path.is_symlink() for path in targets):
        raise RuntimeError("refusing to overwrite existing lepton analysis outputs")
    legacy = args.legacy_dir.resolve(strict=True)
    maximum = str(args.max_events)
    tagger_text = run_frozen(legacy / "isolepton_eff_purity_v2077.py", args.complete, ["--max-events", maximum], targets[0])
    finder_text = run_frozen(legacy / "isolepton_finder_eff_purity_v2077.py", args.finder, ["--max-events", maximum, "--rcal-ele-min", "0.90", "--calE-mu-max", "5.0", "--pid-mu-first"], targets[1])
    counts = joined_multiplicity(args.complete, args.finder, args.source_file_id, legacy, args.max_events)
    rows = purity_rows(parse_tagger_origins(tagger_text), parse_finder_origins(finder_text))
    targets[2].write_text(json.dumps({"purity": rows, "multiplicity": counts}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with targets[3].open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    count_rows = multiplicity_rows(counts)
    with targets[4].open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["logic", "category", "denominator", "selection", "count"])
        writer.writeheader()
        writer.writerows(count_rows)
    write_channel_table("SEMI", rows, counts, targets[5])
    write_channel_table("DI", rows, counts, targets[6])


if __name__ == "__main__":
    main()
