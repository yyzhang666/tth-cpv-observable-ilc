#!/usr/bin/env python3
"""Validate Finder-branch collections and bounded upstream PFO equality."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SGV_REQUIRED = (
    "PandoraPFOs",
    "MarlinTrkTracks",
    "TrackMCTruthLink",
    "MCTruthTrackLink",
    "MCParticlesSkimmed",
    "RecoMCTruthLink",
    "MCTruthRecoLink",
)
COMPLETE_REQUIRED = ("MCParticlesSkimmed", "PFOsWithoutOverlayCheated", "ISOElectrons", "ISOMuons")
FINDER_REQUIRED = ("MCParticlesSkimmed", "PFOsWithoutOverlayCheated", "Isolep", "PFOsAfterIso")


def open_reader(path):
    from pyLCIO import IOIMPL

    reader = IOIMPL.LCFactory.getInstance().createLCReader()
    reader.open(str(path))
    return reader


def names(event):
    return set(str(value) for value in event.getCollectionNames())


def vector(value):
    try:
        return [float(value[index]) for index in range(value.size())]
    except Exception:
        try:
            return [float(item) for item in value]
        except Exception:
            return []


def pfo_payload(pfo):
    payload = {
        "type": int(pfo.getType()),
        "energy": float(pfo.getEnergy()),
        "momentum": vector(pfo.getMomentum()),
        "mass": float(pfo.getMass()),
        "charge": float(pfo.getCharge()),
        "covariance": vector(pfo.getCovMatrix()),
        "n_particles": len(pfo.getParticles()),
        "n_tracks": len(pfo.getTracks()),
        "n_clusters": len(pfo.getClusters()),
        "particle_ids": [],
    }
    for pid in pfo.getParticleIDs():
        payload["particle_ids"].append(
            {
                "algorithm_type": int(pid.getAlgorithmType()),
                "pdg": int(pid.getPDG()),
                "likelihood": float(pid.getLikelihood()),
                "parameters": vector(pid.getParameters()),
            }
        )
    return payload


def collection_fingerprint(collection):
    payload = [pfo_payload(collection.getElementAt(index)) for index in range(collection.getNumberOfElements())]
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def require(event, required, label, index):
    missing = sorted(set(required) - names(event))
    if missing:
        raise RuntimeError(f"{label} event {index} missing collections: {', '.join(missing)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-file-id", required=True)
    parser.add_argument("--sgv-input", type=Path, required=True)
    parser.add_argument("--complete-reco", type=Path, required=True)
    parser.add_argument("--finder-output", type=Path, required=True)
    parser.add_argument("--max-events", type=int, default=20)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    if args.max_events <= 0 or args.max_events > 20:
        raise ValueError("bounded validation requires max-events in [1,20]")
    readers = [open_reader(path.resolve(strict=True)) for path in (args.sgv_input, args.complete_reco, args.finder_output)]
    checked = 0
    try:
        while checked < args.max_events:
            events = [reader.readNextEvent() for reader in readers]
            if any(event is None for event in events):
                if not all(event is None for event in events):
                    raise RuntimeError("input branches ended at different bounded event positions")
                break
            sgv_event, complete_event, finder_event = events
            require(sgv_event, SGV_REQUIRED, "sgv", checked)
            require(complete_event, COMPLETE_REQUIRED, "complete-reco", checked)
            require(finder_event, FINDER_REQUIRED, "finder", checked)
            complete_key = (args.source_file_id, int(complete_event.getRunNumber()), int(complete_event.getEventNumber()))
            finder_key = (args.source_file_id, int(finder_event.getRunNumber()), int(finder_event.getEventNumber()))
            if complete_key != finder_key:
                raise RuntimeError(f"event-key mismatch: {complete_key} != {finder_key}")
            complete_hash = collection_fingerprint(complete_event.getCollection("PFOsWithoutOverlayCheated"))
            finder_hash = collection_fingerprint(finder_event.getCollection("PFOsWithoutOverlayCheated"))
            if complete_hash != finder_hash:
                raise RuntimeError(f"PFOsWithoutOverlayCheated payload mismatch at {complete_key}")
            checked += 1
    finally:
        for reader in readers:
            reader.close()
    output = args.output_json.resolve(strict=False)
    if output.exists() or output.is_symlink():
        raise RuntimeError(f"refusing to overwrite validation record: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "ok": True,
                "events_checked": checked,
                "source_file_id": args.source_file_id,
                "join_key": ["source_file_id", "run", "event"],
                "pfo_payload": "PFOsWithoutOverlayCheated exact serialized numeric/object-count fingerprint",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
