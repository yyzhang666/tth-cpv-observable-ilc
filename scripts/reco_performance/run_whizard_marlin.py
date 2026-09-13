#!/usr/bin/env python3
"""Render and run immutable Whizard complete-reco or canonical kinfit replay."""

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
REQUIRED_RECO_COLLECTIONS = (
    "MCParticlesSkimmed",
    "RefinedJets6",
    "OutputErrorFlowJets6",
    "TrueJets",
    "TrueJetPFOLink",
    "ISOElectrons",
    "ISOMuons",
    "JetSLDLink6",
    "SLDNuLink6",
)
VALIDATION_JSON_PREFIX = "RECO_VALIDATION_JSON="


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


def whole_file_bounds(event_count):
    if event_count <= 0:
        raise ValueError("event_count must be positive")
    return 0, event_count + 1


def render_reco(authority, input_path, output_path, event_count):
    root = copy.deepcopy(ET.parse(authority).getroot())
    skip, maximum = whole_file_bounds(event_count)
    one(root, "./global/parameter[@name='LCIOInputFiles']").text = str(input_path)
    one(root, "./global/parameter[@name='MaxRecordNumber']").set("value", str(maximum))
    one(root, "./global/parameter[@name='SkipNEvents']").set("value", str(skip))
    one(root, "./constants/constant[@name='OutputDirectory']").set("value", str(output_path.parent))
    one(root, "./constants/constant[@name='OutputBaseName']").set("value", output_path.stem)
    return root, skip, maximum


def render_kinfit(authority, input_path, output_path, maximum):
    root = copy.deepcopy(ET.parse(authority).getroot())
    validate_kinfit_authority(root)
    one(root, "./global/parameter[@name='LCIOInputFiles']").text = str(input_path)
    one(root, "./global/parameter[@name='MaxRecordNumber']").set("value", str(maximum))
    one(root, "./global/parameter[@name='SkipNEvents']").set("value", "0")
    one(root, "./processor[@name='MyTTHSemiLepKinFit']/parameter[@name='outputFilename']").text = str(output_path)
    return root, 0, maximum


def validate_kinfit_authority(root):
    processor = one(root, "./processor[@name='MyTTHSemiLepKinFit']")
    values = {
        node.get("name"): (node.text or "").strip()
        for node in processor.findall("./parameter")
    }
    required = {
        "TopN": "10",
        "FlavorJetCollectionName": "RefinedJets6",
        "JetCollectionName": "OutputErrorFlowJets6",
    }
    mismatches = {
        name: {"expected": expected, "observed": values.get(name)}
        for name, expected in required.items()
        if values.get(name) != expected
    }
    if mismatches:
        raise RuntimeError(f"non-canonical kinfit authority: {mismatches}")


def xml_library_hashes(root):
    libraries = []
    for node in root.findall(".//library"):
        value = (node.get("path") or node.text or "").strip()
        if not value:
            raise RuntimeError("XML library entry has no path")
        path = Path(value).resolve(strict=True)
        libraries.append({"path": str(path), "sha256": sha256(path)})
    return libraries


def event_key(event):
    return int(event.getRunNumber()), int(event.getEventNumber())


def validate_reco_output(input_path, output_path, expected_events, reader_factory=None):
    if reader_factory is None:
        from pyLCIO import IOIMPL

        reader_factory = lambda: IOIMPL.LCFactory.getInstance().createLCReader()
    input_reader = reader_factory()
    output_reader = reader_factory()
    input_reader.open(str(input_path))
    output_reader.open(str(output_path))
    count = 0
    input_keys = set()
    output_keys = set()
    try:
        while True:
            input_event = input_reader.readNextEvent()
            output_event = output_reader.readNextEvent()
            if not input_event or not output_event:
                if bool(input_event) != bool(output_event):
                    raise RuntimeError("SGV input and reco output have different event counts")
                break
            input_key = event_key(input_event)
            output_key = event_key(output_event)
            if input_key in input_keys:
                raise RuntimeError(f"duplicate SGV input event key: {input_key}")
            if output_key in output_keys:
                raise RuntimeError(f"duplicate reco output event key: {output_key}")
            input_keys.add(input_key)
            output_keys.add(output_key)
            if input_key != output_key:
                raise RuntimeError(
                    f"ordered event-key mismatch at index {count}: {input_key} != {output_key}"
                )
            names = {str(value) for value in output_event.getCollectionNames()}
            missing = sorted(set(REQUIRED_RECO_COLLECTIONS) - names)
            if missing:
                raise RuntimeError(
                    f"reco output event {count} missing collections: {', '.join(missing)}"
                )
            count += 1
    finally:
        input_reader.close()
        output_reader.close()
    if count != int(expected_events):
        raise RuntimeError(f"reco output event count {count} != expected {expected_events}")
    return {
        "events": count,
        "ordered_event_keys_match": True,
        "unique_event_keys": True,
        "required_collections": list(REQUIRED_RECO_COLLECTIONS),
    }


def has_sldcorrection_end_signature(log_path):
    tail = Path(log_path).read_bytes()[-131072:].decode("utf-8", errors="replace")
    return all(
        marker in tail
        for marker in (
            "*** Break *** segmentation violation",
            "in SLDCorrection::end",
            "SLDCorrection/src/SLDCorrection.cc:",
            "in marlin::ProcessorMgr::end()",
        )
    )


def accepted_reco_tail_segv(returncode, explicitly_allowed, log_path):
    return (
        int(returncode) in (139, -11)
        and bool(explicitly_allowed)
        and has_sldcorrection_end_signature(log_path)
    )


def runtime_validate_reco(repo, runtime, input_path, output_path, expected_events):
    shell = (
        'source "$1" >/dev/null 2>&1; '
        'export PYTHONPATH="$2:${PYTHONPATH:-}"; '
        'python3 "$3" _validate-reco --input "$4" --output "$5" --expected-events "$6"'
    )
    result = subprocess.run(
        [
            "bash",
            "-lc",
            shell,
            "bash",
            str(SETUP),
            runtime["pythonpath_prefix"],
            str(Path(__file__).resolve()),
            str(input_path),
            str(output_path),
            str(expected_events),
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    payloads = [
        line[len(VALIDATION_JSON_PREFIX) :]
        for line in result.stdout.splitlines()
        if line.startswith(VALIDATION_JSON_PREFIX)
    ]
    if len(payloads) != 1:
        raise RuntimeError(
            f"expected one reco validation JSON sentinel, found {len(payloads)}"
        )
    return json.loads(payloads[0])


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
    if sys.argv[1:2] == ["_validate-reco"]:
        validator = argparse.ArgumentParser()
        validator.add_argument("_mode")
        validator.add_argument("--input", type=Path, required=True)
        validator.add_argument("--output", type=Path, required=True)
        validator.add_argument("--expected-events", type=int, required=True)
        validation_args = validator.parse_args()
        print(
            VALIDATION_JSON_PREFIX
            + json.dumps(
                validate_reco_output(
                    validation_args.input,
                    validation_args.output,
                    validation_args.expected_events,
                ),
                sort_keys=True,
            )
        )
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("reco", "kinfit"))
    parser.add_argument("--authority", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--event-count", type=int, required=True, help="whole SGV/reco count; kinfit input count")
    parser.add_argument("--allow-long-run", action="store_true")
    parser.add_argument("--accept-validated-exit-134", action="store_true")
    parser.add_argument("--accept-validated-reco-tail-segv", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.event_count <= 0:
        raise ValueError("event-count must be positive")
    authority = args.authority.resolve(strict=True)
    input_path = args.input.resolve(strict=True)
    output_path = args.output.resolve(strict=False)
    run_dir = args.run_dir.resolve(strict=False)
    if output_path.exists() or output_path.is_symlink():
        raise RuntimeError(f"refusing to overwrite output: {output_path}")
    if run_dir.exists() or run_dir.is_symlink():
        raise RuntimeError(f"refusing to reuse run directory: {run_dir}")
    if args.mode == "reco":
        root, skip, maximum = render_reco(authority, input_path, output_path, args.event_count)
    else:
        root, skip, maximum = render_kinfit(authority, input_path, output_path, args.event_count)
    if args.event_count > 20 and not args.allow_long_run:
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
        "expected_output_events": args.event_count,
        "command": ["Marlin", str(as_run_xml)],
        "cwd": str(run_dir),
        **runtime,
        "xml_library_hashes": xml_library_hashes(root),
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
    reco_tail_segv = result.returncode in (139, -11) and args.mode == "reco"
    accepted_tail_segv = args.mode == "reco" and accepted_reco_tail_segv(
        result.returncode,
        args.accept_validated_reco_tail_segv,
        run_dir / "marlin.log",
    )
    if result.returncode != 0 and not validated_exit_134 and not (
        accepted_tail_segv
    ):
        raise RuntimeError(f"Marlin failed with exit code {result.returncode}; artifacts retained")
    if not output_path.is_file() or output_path.stat().st_size <= 0:
        raise RuntimeError(f"missing or empty output after Marlin: {output_path}")
    if args.mode == "reco":
        validation = runtime_validate_reco(repo, runtime, input_path, output_path, args.event_count)
        manifest["output_validation"] = validation
        manifest["accepted_reco_tail_segv"] = bool(reco_tail_segv)
        manifest["accept_reason"] = (
            "validated_SLDCorrection_end_tail_segv" if reco_tail_segv else "zero_exit_and_validated_output"
        )
        runtime_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    else:
        counters = validate_kinfit_root(output_path, runtime["root_python_dir"])
        manifest["root_validation"] = counters
        manifest["accepted_exit_134"] = bool(validated_exit_134)
        runtime_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
