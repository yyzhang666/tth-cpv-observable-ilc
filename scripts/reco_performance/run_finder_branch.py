#!/usr/bin/env python3
"""Render and run one guarded Physsim Finder branch job."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


SETUP = Path("/data/dust/user/zhangyuy/analysis/tth/ZHH/setup.sh")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def runtime_environment(repo: Path) -> tuple[dict[str, str], dict]:
    command = (
        'source "$1" >/dev/null 2>&1; '
        'printf "%s\\n" "$(root-config --libdir)" "${MARLIN_DLL:-}"'
    )
    result = subprocess.run(
        ["bash", "-lc", command, "bash", str(SETUP)],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = result.stdout.splitlines()
    root_python = lines[0]
    marlin_dll = lines[1] if len(lines) > 1 else ""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = ":".join(part for part in (root_python, str(repo / "src"), existing) if part)
    libraries = []
    for value in marlin_dll.split(":"):
        path = Path(value)
        if path.is_file():
            libraries.append({"path": str(path), "sha256": sha256(path)})
    return env, {"root_python_dir": root_python, "marlin_dll": marlin_dll, "loaded_library_hashes": libraries}


def validate_finder_output(path: Path, expected_events: int, reader_factory=None) -> dict:
    required = {"MCParticlesSkimmed", "PFOsWithoutOverlayCheated", "Isolep", "PFOsAfterIso"}
    if reader_factory is None:
        from pyLCIO import IOIMPL

        reader_factory = lambda: IOIMPL.LCFactory.getInstance().createLCReader()
    reader = reader_factory()
    reader.open(str(path))
    count = 0
    try:
        while True:
            event = reader.readNextEvent()
            if event is None:
                break
            names = {str(value) for value in event.getCollectionNames()}
            missing = sorted(required - names)
            if missing:
                raise RuntimeError(f"Finder output event {count} missing collections: {', '.join(missing)}")
            count += 1
    finally:
        reader.close()
    if count != int(expected_events):
        raise RuntimeError(f"Finder output event count {count} != requested {expected_events}")
    return {"events": count, "required_collections": sorted(required)}


def accepted_exit_134(returncode: int, explicitly_allowed: bool) -> bool:
    return int(returncode) in (134, -6) and bool(explicitly_allowed)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--max-records", type=int, required=True)
    parser.add_argument("--skip-events", type=int, required=True)
    parser.add_argument("--allow-long-run", action="store_true")
    parser.add_argument("--accept-validated-exit-134", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.max_records <= 0:
        raise ValueError("max-records must be explicit and positive")
    if args.max_records > 20 and not args.allow_long_run:
        raise RuntimeError("runs above 20 events require --allow-long-run after the recorded gate")
    if args.skip_events < 0:
        raise ValueError("skip-events must be non-negative")
    template = args.template.resolve(strict=True)
    input_path = args.input.resolve(strict=True)
    output = args.output.resolve(strict=False)
    run_dir = args.run_dir.resolve(strict=False)
    if output.exists() or output.is_symlink():
        raise RuntimeError(f"refusing to overwrite output: {output}")
    run_xml = run_dir / "finder_branch_as_run.xml"
    runtime_json = run_dir / "runtime_manifest.json"
    log_path = run_dir / "marlin.log"
    for path in (run_xml, runtime_json, log_path):
        if path.exists() or path.is_symlink():
            raise RuntimeError(f"refusing to overwrite run record: {path}")
    run_dir.mkdir(parents=True, exist_ok=True)
    rendered = template.read_text(encoding="utf-8")
    replacements = {
        "__INPUT_FILE__": str(input_path),
        "__OUTPUT_FILE__": str(output),
        "__MAX_RECORDS__": str(args.max_records),
        "__SKIP_EVENTS__": str(args.skip_events),
    }
    for token, value in replacements.items():
        if rendered.count(token) != 1:
            raise RuntimeError(f"template token must occur exactly once: {token}")
        rendered = rendered.replace(token, value)
    run_xml.write_text(rendered, encoding="utf-8")
    repo = Path(__file__).resolve().parents[2]
    env, runtime = runtime_environment(repo)
    payload = {
        "setup": {"path": str(SETUP), "sha256": sha256(SETUP)},
        "template": {"path": str(template), "sha256": sha256(template)},
        "as_run_xml": {"path": str(run_xml), "sha256": sha256(run_xml)},
        "input": str(input_path),
        "output": str(output),
        "max_records": args.max_records,
        "skip_events": args.skip_events,
        **runtime,
    }
    runtime_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.prepare_only:
        return
    shell = 'source "$1" >/dev/null 2>&1; export PYTHONPATH="$2:${PYTHONPATH:-}"; exec Marlin "$3"'
    with log_path.open("xb") as log_stream:
        result = subprocess.run(
            ["bash", "-lc", shell, "bash", str(SETUP), env["PYTHONPATH"], str(run_xml)],
            cwd=run_dir,
            env=env,
            stdout=log_stream,
            stderr=subprocess.STDOUT,
        )
    payload["marlin_exit_code"] = result.returncode
    runtime_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    exit_134_allowed = accepted_exit_134(result.returncode, args.accept_validated_exit_134)
    if result.returncode != 0 and not exit_134_allowed:
        raise RuntimeError(f"Marlin failed with exit code {result.returncode}; artifacts retained")
    if not output.is_file():
        raise RuntimeError(f"Marlin returned without creating output: {output}")
    validation = validate_finder_output(output, args.max_records)
    payload["output_validation"] = validation
    payload["accepted_exit_134"] = bool(exit_134_allowed)
    runtime_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
