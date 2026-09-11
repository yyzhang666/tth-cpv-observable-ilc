#!/usr/bin/env python3
"""Validate the frozen reco-performance study manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED_CHUNKS = list(range(1, 11))
EXPECTED_COUNTS = [12498, 12499, 12498, 12499, 12498, 12498, 12499, 12499, 12499, 12495]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def expanded_paths(payload: dict) -> list[str]:
    generator = payload["generator_mtt"]
    leptons = payload["physsim_leptons"]
    paths = list(generator["whizard"]["files"])
    paths.extend(generator["physsim"]["path_template"].format(chunk=chunk) for chunk in EXPECTED_CHUNKS)
    paths.extend(leptons["complete_reco_path_template"].format(chunk=chunk) for chunk in EXPECTED_CHUNKS)
    paths.extend(leptons["finder_branch_source_path_template"].format(chunk=chunk) for chunk in EXPECTED_CHUNKS)
    return paths


def validate(payload: dict) -> list[str]:
    problems = []
    required = {"generator_mtt", "physsim_leptons", "whizard_jet_flavor", "whizard_jet_assignment", "runtime", "frozen_sources"}
    missing = sorted(required - payload.keys())
    if missing:
        return [f"missing top-level keys: {', '.join(missing)}"]
    generator = payload["generator_mtt"]
    leptons = payload["physsim_leptons"]
    if generator["physsim"]["chunks"] != EXPECTED_CHUNKS:
        problems.append("Physsim generator chunks are not exactly 1-10")
    if leptons["chunks"] != EXPECTED_CHUNKS:
        problems.append("Physsim lepton chunks are not exactly 1-10")
    if leptons["complete_reco_event_counts"] != EXPECTED_COUNTS:
        problems.append("complete-reco event counts differ from the frozen inventory")
    if sum(leptons["complete_reco_event_counts"]) != leptons["expected_total_events"]:
        problems.append("complete-reco expected_total_events is inconsistent")
    whizard_files = generator["whizard"]["files"]
    if len(whizard_files) != generator["whizard"]["independent_physical_samples"]:
        problems.append("Whizard physical-sample count does not match its file list")
    paths = expanded_paths(payload)
    if len(paths) != len(set(paths)):
        problems.append("expanded input path list contains duplicates")
    if generator["physsim"]["cross_section_fb"] != 2.96055314955:
        problems.append("Physsim cross section changed")
    if generator["whizard"]["cross_section_fb"] != 2.206536:
        problems.append("Whizard cross section changed")
    if leptons["join_key"] != ["source_file_id", "run", "event"]:
        problems.append("cross-branch event join key changed")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--check-files", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    problems = validate(payload)
    if args.check_files:
        for path_string in expanded_paths(payload):
            if not Path(path_string).is_file():
                problems.append(f"missing input file: {path_string}")
        for record in payload["runtime"].values():
            if not isinstance(record, dict) or "path" not in record or "sha256" not in record:
                continue
            path = Path(record["path"])
            if not path.is_file():
                problems.append(f"missing runtime file: {path}")
            elif sha256(path) != record["sha256"]:
                problems.append(f"runtime hash mismatch: {path}")
        for record in payload["frozen_sources"].values():
            path = Path(record["path"])
            if not path.is_file():
                problems.append(f"missing frozen source: {path}")
            elif sha256(path) != record["sha256"]:
                problems.append(f"frozen-source hash mismatch: {path}")
    report = {"ok": not problems, "problems": problems, "expanded_input_files": len(expanded_paths(payload))}
    print(json.dumps(report, indent=2, sort_keys=True))
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
