#!/usr/bin/env python3
"""Write one LCIO per source containing exactly the frozen selected-common events."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


KEY_FIELDS = ("source_file_id", "local_index", "run_number", "event_number")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_keys(path):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(set(KEY_FIELDS) - set(reader.fieldnames or ()))
        if missing:
            raise RuntimeError(f"selected-common CSV missing fields: {missing}")
        rows = [
            {
                "source_file_id": row["source_file_id"],
                "local_index": int(row["local_index"]),
                "run_number": int(row["run_number"]),
                "event_number": int(row["event_number"]),
            }
            for row in reader
        ]
    keys = [tuple(row[field] for field in KEY_FIELDS) for row in rows]
    if len(keys) != 4730 or len(keys) != len(set(keys)):
        raise RuntimeError(f"expected 4730 unique source-aware keys, found {len(set(keys))}")
    return rows


def event_fingerprint(event):
    collections = []
    for name in sorted(str(value) for value in event.getCollectionNames()):
        collection = event.getCollection(name)
        collections.append(
            [name, str(collection.getTypeName()), int(collection.getNumberOfElements())]
        )
    payload = {
        "run_number": int(event.getRunNumber()),
        "event_number": int(event.getEventNumber()),
        "collections": collections,
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest(), payload


def write_mapping(path, rows):
    fields = [
        "source_file_id",
        "filtered_local_index",
        "original_local_index",
        "run_number",
        "event_number",
        "semantic_fingerprint_sha256",
    ]
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def process_source(source, wanted_rows, output_dir, IOIMPL):
    source_id = source["source_file_id"]
    input_path = Path(source["lcio"]).resolve(strict=True)
    expected_events = int(source["expected_events"])
    wanted = {row["local_index"]: row for row in wanted_rows}
    if len(wanted) != len(wanted_rows):
        raise RuntimeError(f"{source_id}: duplicate original local index")
    output_path = output_dir / f"{source_id}_common.slcio"
    mapping_path = output_dir / f"{source_id}_mapping.csv"
    reader = IOIMPL.LCFactory.getInstance().createLCReader()
    writer = IOIMPL.LCFactory.getInstance().createLCWriter()
    reader.open(str(input_path))
    writer.open(str(output_path))
    mapping = []
    local_index = 0
    try:
        while local_index < expected_events:
            event = reader.readNextEvent()
            if not bool(event):
                break
            if local_index in wanted:
                frozen = wanted[local_index]
                observed_key = (
                    source_id,
                    local_index,
                    int(event.getRunNumber()),
                    int(event.getEventNumber()),
                )
                expected_key = tuple(frozen[field] for field in KEY_FIELDS)
                if observed_key != expected_key:
                    raise RuntimeError(
                        f"{source_id}: event-key mismatch at {local_index}: "
                        f"{observed_key} != {expected_key}"
                    )
                fingerprint, _ = event_fingerprint(event)
                writer.writeEvent(event)
                mapping.append(
                    {
                        "source_file_id": source_id,
                        "filtered_local_index": len(mapping),
                        "original_local_index": local_index,
                        "run_number": observed_key[2],
                        "event_number": observed_key[3],
                        "semantic_fingerprint_sha256": fingerprint,
                    }
                )
            local_index += 1
    finally:
        reader.close()
        writer.close()
    if local_index != expected_events:
        raise RuntimeError(
            f"{source_id}: readable input event count {local_index} != {expected_events}"
        )
    if len(mapping) != len(wanted):
        raise RuntimeError(f"{source_id}: wrote {len(mapping)} events, expected {len(wanted)}")
    write_mapping(mapping_path, mapping)

    check = IOIMPL.LCFactory.getInstance().createLCReader()
    check.open(str(output_path))
    validated = 0
    try:
        while True:
            event = check.readNextEvent()
            if not bool(event):
                break
            if validated >= len(mapping):
                raise RuntimeError(f"{source_id}: filtered LCIO has extra events")
            row = mapping[validated]
            fingerprint, _ = event_fingerprint(event)
            observed = (int(event.getRunNumber()), int(event.getEventNumber()), fingerprint)
            expected = (
                row["run_number"],
                row["event_number"],
                row["semantic_fingerprint_sha256"],
            )
            if observed != expected:
                raise RuntimeError(
                    f"{source_id}: filtered semantic mismatch at {validated}: "
                    f"{observed} != {expected}"
                )
            validated += 1
    finally:
        check.close()
    if validated != len(mapping):
        raise RuntimeError(f"{source_id}: validated {validated}, expected {len(mapping)}")
    return {
        "source_file_id": source_id,
        "input_lcio": str(input_path),
        "input_expected_events": expected_events,
        "input_sha256": sha256(input_path),
        "filtered_lcio": str(output_path),
        "filtered_events": len(mapping),
        "filtered_sha256": sha256(output_path),
        "mapping_csv": str(mapping_path),
        "mapping_sha256": sha256(mapping_path),
        "ordered_event_keys_match": True,
        "semantic_fingerprints_match": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selected-common-csv", type=Path, required=True)
    parser.add_argument("--expected-selected-common-sha256", required=True)
    parser.add_argument("--sources-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() or args.output_dir.is_symlink():
        raise RuntimeError(f"refusing to reuse output directory: {args.output_dir}")
    selected_path = args.selected_common_csv.resolve(strict=True)
    observed_hash = sha256(selected_path)
    if observed_hash != args.expected_selected_common_sha256:
        raise RuntimeError(
            f"selected-common hash mismatch: {observed_hash} != "
            f"{args.expected_selected_common_sha256}"
        )
    rows = read_keys(selected_path)
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["source_file_id"]].append(row)
    sources = json.loads(args.sources_json.read_text(encoding="utf-8"))["sources"]
    expected_counts = [1168, 1168, 1168, 1226]
    counts = [len(grouped[source["source_file_id"]]) for source in sources]
    if counts != expected_counts:
        raise RuntimeError(f"per-source selected counts {counts} != {expected_counts}")

    from pyLCIO import IOIMPL

    args.output_dir.mkdir(parents=True)
    source_results = [
        process_source(source, grouped[source["source_file_id"]], args.output_dir, IOIMPL)
        for source in sources
    ]
    manifest = {
        "status": "validated exact-key filtered LCIO inputs for full180 replay",
        "selected_common_csv": {
            "path": str(selected_path),
            "sha256": observed_hash,
            "keys": len(rows),
            "per_source": dict(Counter(row["source_file_id"] for row in rows)),
        },
        "sources_json": {
            "path": str(args.sources_json.resolve(strict=True)),
            "sha256": sha256(args.sources_json),
        },
        "event_key": list(KEY_FIELDS),
        "semantic_fingerprint": "sha256(run,event,sorted collection name/type/size)",
        "sources": source_results,
        "command": [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
        "script_sha256": sha256(Path(__file__).resolve()),
    }
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"counts": counts, "output_dir": str(args.output_dir)}, sort_keys=True))


if __name__ == "__main__":
    main()
