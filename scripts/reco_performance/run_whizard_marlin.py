#!/usr/bin/env python3
"""Render and run immutable Whizard complete-reco or kinfit replay shards."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


SETUP = Path("/data/dust/user/zhangyuy/analysis/tth/ZHH/setup.sh")
PROCESSOR_LIBRARY = Path("/data/dust/user/zhangyuy/analysis/tth/ZHH/source/lib/libZHHProcessors.so")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def one(root, xpath):
    matches = root.findall(xpath)
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one XML node for {xpath}, found {len(matches)}")
    return matches[0]


def shard_bounds(event_count, shard_index):
    if event_count <= 0:
        raise ValueError("event_count must be positive")
    if shard_index == 0:
        return 0, min(6000, event_count)
    if shard_index == 1 and event_count > 6000:
        return 6000, event_count - 6000
    raise ValueError(f"invalid shard {shard_index} for {event_count} events")


def render_reco(authority, input_path, output_path, event_count, shard_index):
    root = copy.deepcopy(ET.parse(authority).getroot())
    skip, maximum = shard_bounds(event_count, shard_index)
    one(root, "./global/parameter[@name='LCIOInputFiles']").text = str(input_path)
    one(root, "./global/parameter[@name='MaxRecordNumber']").set("value", str(maximum))
    one(root, "./global/parameter[@name='SkipNEvents']").set("value", str(skip))
    one(root, "./constants/constant[@name='OutputDirectory']").set("value", str(output_path.parent))
    one(root, "./constants/constant[@name='OutputBaseName']").set("value", output_path.stem)
    return root, skip, maximum


def render_kinfit(authority, input_path, output_path, maximum):
    root = copy.deepcopy(ET.parse(authority).getroot())
    one(root, "./global/parameter[@name='LCIOInputFiles']").text = str(input_path)
    one(root, "./global/parameter[@name='MaxRecordNumber']").set("value", str(maximum))
    one(root, "./global/parameter[@name='SkipNEvents']").set("value", "0")
    one(root, "./processor[@name='MyTTHSemiLepKinFit']/parameter[@name='outputFilename']").text = str(output_path)
    return root, 0, maximum


def sourced_runtime(repo):
    shell = 'source "$1" >/dev/null 2>&1; printf "%s\\n" "$(root-config --libdir)" "${MARLIN_DLL:-}"'
    result = subprocess.run(["bash", "-lc", shell, "bash", str(SETUP)], check=True, capture_output=True, text=True)
    lines = result.stdout.splitlines()
    root_python = lines[0]
    marlin_dll = lines[1] if len(lines) > 1 else ""
    libraries = []
    for item in marlin_dll.split(":"):
        path = Path(item)
        if path.is_file():
            libraries.append({"path": str(path), "sha256": sha256(path)})
    return {
        "root_python_dir": root_python,
        "pythonpath_prefix": f"{root_python}:{repo / 'src'}",
        "marlin_dll": marlin_dll,
        "loaded_library_hashes": libraries,
        "processor_library": {"path": str(PROCESSOR_LIBRARY), "sha256": sha256(PROCESSOR_LIBRARY)},
    }


def validate_kinfit_root(path, root_python_dir):
    sys.path.insert(0, root_python_dir)
    import ROOT

    root_file = ROOT.TFile.Open(str(path))
    if not root_file or root_file.IsZombie():
        raise RuntimeError(f"invalid ROOT output: {path}")
    try:
        counters = {}
        for name in ("TTHSemiLepKinFit", "TTHSemiLepKinFit_candidates"):
            tree = root_file.Get(name)
            if tree is None:
                raise RuntimeError(f"missing required tree {name}")
            counters[name] = int(tree.GetEntries())
        if min(counters.values()) <= 0:
            raise RuntimeError(f"required kinfit trees are empty: {counters}")
        candidates = root_file.Get("TTHSemiLepKinFit_candidates")
        if candidates.GetBranch("fit_success") is None:
            raise RuntimeError("candidate tree lacks fit_success counter branch")
        counters["candidate_fit_success_rows"] = sum(int(row.fit_success) == 1 for row in candidates)
        if counters["candidate_fit_success_rows"] <= 0:
            raise RuntimeError(f"candidate tree has no successful fit rows: {counters}")
        return counters
    finally:
        root_file.Close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("reco", "kinfit"))
    parser.add_argument("--authority", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--event-count", type=int, required=True, help="full SGV count for reco; shard count for kinfit")
    parser.add_argument("--shard-index", type=int, choices=(0, 1))
    parser.add_argument("--allow-long-run", action="store_true")
    parser.add_argument("--accept-validated-exit-134", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.event_count <= 0:
        raise ValueError("event-count must be positive")
    if args.mode == "reco" and args.shard_index is None:
        raise ValueError("reco requires shard-index")
    if args.mode == "kinfit" and args.shard_index is not None:
        raise ValueError("kinfit input is already one shard; do not set shard-index")
    authority = args.authority.resolve(strict=True)
    input_path = args.input.resolve(strict=True)
    output_path = args.output.resolve(strict=False)
    run_dir = args.run_dir.resolve(strict=False)
    if output_path.exists() or output_path.is_symlink():
        raise RuntimeError(f"refusing to overwrite output: {output_path}")
    if run_dir.exists() or run_dir.is_symlink():
        raise RuntimeError(f"refusing to reuse run directory: {run_dir}")
    if args.mode == "reco":
        root, skip, maximum = render_reco(authority, input_path, output_path, args.event_count, args.shard_index)
    else:
        root, skip, maximum = render_kinfit(authority, input_path, output_path, args.event_count)
    if maximum > 20 and not args.allow_long_run:
        raise RuntimeError("Marlin above 20 events requires the recorded long-run gate")
    run_dir.mkdir(parents=True)
    as_run_xml = run_dir / f"{args.mode}_as_run.xml"
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(as_run_xml, encoding="utf-8", xml_declaration=True)
    repo = Path(__file__).resolve().parents[2]
    runtime = sourced_runtime(repo)
    manifest = {
        "mode": args.mode,
        "authority": {"path": str(authority), "sha256": sha256(authority)},
        "as_run_xml": {"path": str(as_run_xml), "sha256": sha256(as_run_xml)},
        "input": str(input_path),
        "output": str(output_path),
        "skip_events": skip,
        "max_records": maximum,
        "command": ["Marlin", str(as_run_xml)],
        "cwd": str(run_dir),
        **runtime,
    }
    runtime_path = run_dir / "runtime_manifest.json"
    runtime_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    if args.prepare_only:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shell = 'source "$1" >/dev/null 2>&1; export PYTHONPATH="$2:${PYTHONPATH:-}"; Marlin "$3"'
    with (run_dir / "marlin.log").open("xb") as log_stream:
        result = subprocess.run(
            ["bash", "-lc", shell, "bash", str(SETUP), runtime["pythonpath_prefix"], str(as_run_xml)],
            cwd=run_dir,
            stdout=log_stream,
            stderr=subprocess.STDOUT,
        )
    manifest["marlin_exit_code"] = result.returncode
    runtime_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    validated_exit_134 = result.returncode in (134, -6) and args.mode == "kinfit" and args.accept_validated_exit_134
    if result.returncode != 0 and not validated_exit_134:
        raise RuntimeError(f"Marlin failed with exit code {result.returncode}; artifacts retained")
    if not output_path.is_file() or output_path.stat().st_size <= 0:
        raise RuntimeError(f"missing or empty output after Marlin: {output_path}")
    if args.mode == "kinfit":
        counters = validate_kinfit_root(output_path, runtime["root_python_dir"])
        manifest["root_validation"] = counters
        manifest["accepted_exit_134"] = bool(validated_exit_134)
        runtime_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
