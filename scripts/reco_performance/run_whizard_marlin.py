#!/usr/bin/env python3
"""Render and run immutable Whizard complete-reco or canonical kinfit replay."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


SETUP = Path("/data/dust/user/zhangyuy/analysis/tth/ZHH/setup.sh")
KINFit_VALIDATION_PYTHON = Path(
    "/data/dust/user/zhangyuy/.venvs/zhh-catboost-py311/bin/python3"
)
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
KINFIT_VALIDATION_JSON_PREFIX = "KINFIT_VALIDATION_JSON="
BEST_TREE_REQUIRED_BRANCHES = {
    "accepted",
    "best_combo_id",
    "event_index",
    "event_number",
    "fit_success",
    "mH_postfit",
    "mW_had_postfit",
    "mt_had_postfit",
    "run_number",
    "top_combo_ids",
    "top_n",
}
CANDIDATE_TREE_REQUIRED_BRANCHES = {
    "candidate_rank",
    "combo_id",
    "event_index",
    "event_number",
    "fit_success",
    "fitchi2",
    "mH_postfit",
    "mH_prefit",
    "mW_had_postfit",
    "mW_had_prefit",
    "mt_had_postfit",
    "mt_had_prefit",
    "run_number",
}


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


def render_kinfit(authority, input_path, output_path, maximum, expected_top_n=10):
    root = copy.deepcopy(ET.parse(authority).getroot())
    validate_kinfit_authority(root, expected_top_n)
    one(root, "./global/parameter[@name='LCIOInputFiles']").text = str(input_path)
    one(root, "./global/parameter[@name='MaxRecordNumber']").set("value", str(maximum))
    one(root, "./global/parameter[@name='SkipNEvents']").set("value", "0")
    one(root, "./processor[@name='MyTTHSemiLepKinFit']/parameter[@name='outputFilename']").text = str(output_path)
    return root, 0, maximum


def validate_kinfit_authority(root, expected_top_n=10):
    processor = one(root, "./processor[@name='MyTTHSemiLepKinFit']")
    values = {
        node.get("name"): (node.text or "").strip()
        for node in processor.findall("./parameter")
    }
    required = {
        "TopN": str(expected_top_n),
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


def runtime_validate_kinfit(
    repo,
    runtime,
    output_path,
    expected_input_events,
    expected_top_n=10,
    reference_top10_root=None,
    event_mapping_csv=None,
):
    """Validate ROOT in a clean sourced child pinned to the compatible py311."""
    shell = (
        'source "$1" >/dev/null 2>&1; '
        'export PYTHONPATH="$2:${PYTHONPATH:-}"; '
        'validation_python="$3"; shift 3; exec "$validation_python" "$@"'
    )
    validation_args = [
        str(Path(__file__).resolve()),
        "_validate-kinfit",
        "--output", str(output_path),
        "--expected-input-events", str(expected_input_events),
        "--expected-top-n", str(expected_top_n),
    ]
    if reference_top10_root is not None or event_mapping_csv is not None:
        if reference_top10_root is None or event_mapping_csv is None:
            raise RuntimeError("TopN overlap validation requires both reference ROOT and mapping CSV")
        validation_args.extend(
            [
                "--reference-top10-root", str(reference_top10_root),
                "--event-mapping-csv", str(event_mapping_csv),
            ]
        )
    result = subprocess.run(
        [
            "bash",
            "-lc",
            shell,
            "bash",
            str(SETUP),
            runtime["pythonpath_prefix"],
            str(KINFit_VALIDATION_PYTHON),
            *validation_args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env={"HOME": os.environ.get("HOME", ""), "PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    )
    payloads = [
        line[len(KINFIT_VALIDATION_JSON_PREFIX) :]
        for line in result.stdout.splitlines()
        if line.startswith(KINFIT_VALIDATION_JSON_PREFIX)
    ]
    if len(payloads) != 1:
        raise RuntimeError(
            f"expected one kinfit validation JSON sentinel, found {len(payloads)}"
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


def tree_branch_names(tree):
    return {str(branch.GetName()) for branch in tree.GetListOfBranches()}


def validate_first10_overlap(
    path, reference_top10_root, event_mapping_csv, expected_input_events
):
    """Require full180's first ten base-combo ids to equal frozen Top10 per event."""
    import ROOT

    mapping = {}
    with Path(event_mapping_csv).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            filtered_index = int(row["filtered_local_index"])
            if filtered_index < int(expected_input_events):
                mapping[filtered_index] = int(row["original_local_index"])
    full_file = ROOT.TFile.Open(str(path))
    top10_file = ROOT.TFile.Open(str(reference_top10_root))
    if not full_file or full_file.IsZombie() or not top10_file or top10_file.IsZombie():
        raise RuntimeError("cannot open full180 or Top10 ROOT for overlap validation")
    try:
        full_tree = full_file.Get("TTHSemiLepKinFit")
        top10_tree = top10_file.Get("TTHSemiLepKinFit")
        if full_tree is None or top10_tree is None:
            raise RuntimeError("missing best tree for Top10 overlap validation")
        reference = {
            int(row.event_index): [int(value) for value in row.top_combo_ids]
            for row in top10_tree
        }
        compared = 0
        for row in full_tree:
            filtered_index = int(row.event_index)
            if filtered_index not in mapping:
                raise RuntimeError(f"full180 event_index absent from mapping: {filtered_index}")
            original_index = mapping[filtered_index]
            full_ids = [int(value) for value in row.top_combo_ids]
            if original_index not in reference or full_ids[:10] != reference[original_index]:
                raise RuntimeError(f"Top10 overlap mismatch at filtered event {filtered_index}")
            compared += 1
        if compared != len(mapping):
            raise RuntimeError(f"Top10 overlap compared {compared} events, expected {len(mapping)}")
        return {
            "first10_overlap_events": compared,
            "reference_top10_root": str(Path(reference_top10_root).resolve(strict=True)),
            "reference_top10_sha256": sha256(reference_top10_root),
            "event_mapping_csv": str(Path(event_mapping_csv).resolve(strict=True)),
            "event_mapping_sha256": sha256(event_mapping_csv),
        }
    finally:
        full_file.Close()
        top10_file.Close()


def validate_kinfit_root(path, expected_input_events, expected_top_n=10):
    """Check the persisted schema and best/candidate event alignment."""
    import ROOT

    root_file = ROOT.TFile.Open(str(path))
    if not root_file or root_file.IsZombie():
        raise RuntimeError(f"invalid ROOT output: {path}")
    try:
        best_tree = root_file.Get("TTHSemiLepKinFit")
        candidates = root_file.Get("TTHSemiLepKinFit_candidates")
        if best_tree is None or candidates is None:
            raise RuntimeError("missing required best or candidate tree")
        best_branches = tree_branch_names(best_tree)
        candidate_branches = tree_branch_names(candidates)
        missing_best = sorted(BEST_TREE_REQUIRED_BRANCHES - best_branches)
        missing_candidates = sorted(CANDIDATE_TREE_REQUIRED_BRANCHES - candidate_branches)
        if missing_best or missing_candidates:
            raise RuntimeError(
                f"kinfit tree schema mismatch: best={missing_best}, candidates={missing_candidates}"
            )
        counters = {
            "TTHSemiLepKinFit": int(best_tree.GetEntries()),
            "TTHSemiLepKinFit_candidates": int(candidates.GetEntries()),
        }
        if min(counters.values()) <= 0:
            raise RuntimeError(f"required kinfit trees are empty: {counters}")
        best = {}
        for row in best_tree:
            event_index = int(row.event_index)
            if event_index in best:
                raise RuntimeError(f"duplicate best-tree event_index {event_index}")
            if event_index < 0 or event_index >= int(expected_input_events):
                raise RuntimeError(f"best-tree event_index outside input ceiling: {event_index}")
            combo_ids = [int(value) for value in row.top_combo_ids]
            if (
                int(row.top_n) != int(expected_top_n)
                or len(combo_ids) != int(expected_top_n)
                or len(set(combo_ids)) != int(expected_top_n)
            ):
                raise RuntimeError(
                    f"non-Top{expected_top_n} best-tree payload at event_index {event_index}"
                )
            best[event_index] = {
                "run_number": int(row.run_number),
                "event_number": int(row.event_number),
                "combo_ids": combo_ids,
            }
        ranks = {}
        counters["candidate_fit_success_rows"] = 0
        for row in candidates:
            event_index = int(row.event_index)
            if event_index not in best:
                raise RuntimeError(f"candidate event_index absent from best tree: {event_index}")
            payload = best[event_index]
            if (int(row.run_number), int(row.event_number)) != (
                payload["run_number"], payload["event_number"]
            ):
                raise RuntimeError(f"candidate/best event-key mismatch at {event_index}")
            rank = int(row.candidate_rank)
            if (
                rank < 0
                or rank >= int(expected_top_n)
                or int(row.combo_id) != payload["combo_ids"][rank]
            ):
                raise RuntimeError(
                    f"candidate Top{expected_top_n} alignment mismatch at event_index {event_index}"
                )
            ranks.setdefault(event_index, set()).add(rank)
            counters["candidate_fit_success_rows"] += int(row.fit_success) == 1
        if counters["candidate_fit_success_rows"] <= 0:
            raise RuntimeError(f"candidate tree has no successful fit rows: {counters}")
        incomplete = [
            index
            for index, values in ranks.items()
            if values != set(range(int(expected_top_n)))
        ]
        if incomplete or set(ranks) != set(best):
            raise RuntimeError(
                f"candidate ranks do not cover all {expected_top_n} base combos for all best events: {incomplete[:5]}"
            )
        counters.update(
            {
                "expected_input_events": int(expected_input_events),
                "best_event_index_min": min(best),
                "best_event_index_max": max(best),
                "best_event_indices_unique": True,
                "candidate_event_keys_align": True,
                f"candidate_top{expected_top_n}_rank_combo_alignment": True,
                "best_required_branches": sorted(BEST_TREE_REQUIRED_BRANCHES),
                "candidate_required_branches": sorted(CANDIDATE_TREE_REQUIRED_BRANCHES),
            }
        )
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
    if sys.argv[1:2] == ["_validate-kinfit"]:
        validator = argparse.ArgumentParser()
        validator.add_argument("_mode")
        validator.add_argument("--output", type=Path, required=True)
        validator.add_argument("--expected-input-events", type=int, required=True)
        validator.add_argument("--expected-top-n", type=int, choices=(10, 180), default=10)
        validator.add_argument("--reference-top10-root", type=Path)
        validator.add_argument("--event-mapping-csv", type=Path)
        validator.add_argument("--expected-sha256")
        validator.add_argument("--output-json", type=Path)
        validation_args = validator.parse_args()
        observed_hash = sha256(validation_args.output)
        if (
            validation_args.expected_sha256
            and observed_hash != validation_args.expected_sha256
        ):
            raise RuntimeError(
                f"ROOT hash mismatch: {observed_hash} != {validation_args.expected_sha256}"
            )
        validation = validate_kinfit_root(
            validation_args.output,
            validation_args.expected_input_events,
            validation_args.expected_top_n,
        )
        if validation_args.expected_top_n == 180:
            if not validation_args.reference_top10_root or not validation_args.event_mapping_csv:
                raise RuntimeError("full180 validation requires Top10 reference and event mapping")
            validation.update(
                validate_first10_overlap(
                    validation_args.output,
                    validation_args.reference_top10_root,
                    validation_args.event_mapping_csv,
                    validation_args.expected_input_events,
                )
            )
        payload = {
            "root": str(validation_args.output.resolve(strict=True)),
            "root_sha256": observed_hash,
            "command": [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
            "validation": validation,
        }
        if validation_args.output_json:
            if validation_args.output_json.exists() or validation_args.output_json.is_symlink():
                raise RuntimeError(
                    f"refusing to overwrite validation JSON: {validation_args.output_json}"
                )
            validation_args.output_json.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        print(KINFIT_VALIDATION_JSON_PREFIX + json.dumps(payload, sort_keys=True))
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("reco", "kinfit"))
    parser.add_argument("--authority", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--event-count", type=int, required=True, help="whole SGV/reco count; kinfit input count")
    parser.add_argument("--expected-top-n", type=int, choices=(10, 180), default=10)
    parser.add_argument("--reference-top10-root", type=Path)
    parser.add_argument("--event-mapping-csv", type=Path)
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
        root, skip, maximum = render_kinfit(
            authority, input_path, output_path, args.event_count, args.expected_top_n
        )
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
        counters = runtime_validate_kinfit(
            repo,
            runtime,
            output_path,
            args.event_count,
            args.expected_top_n,
            args.reference_top10_root,
            args.event_mapping_csv,
        )
        manifest["root_validation"] = counters
        manifest["accepted_exit_134"] = bool(validated_exit_134)
        runtime_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
