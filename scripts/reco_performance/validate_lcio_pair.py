#!/usr/bin/env python3
"""Validate that two LCIO files contain the same ordered unique event keys."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


VALIDATION_JSON_PREFIX = "LCIO_PAIR_VALIDATION_JSON="


def event_key(event):
    return int(event.getRunNumber()), int(event.getEventNumber())


def validate_lcio_pair(left_path, right_path, expected_events, reader_factory=None):
    if int(expected_events) <= 0:
        raise ValueError("expected_events must be positive")
    if reader_factory is None:
        from pyLCIO import IOIMPL

        reader_factory = lambda: IOIMPL.LCFactory.getInstance().createLCReader()

    left_reader = reader_factory()
    right_reader = reader_factory()
    left_reader.open(str(left_path))
    right_reader.open(str(right_path))
    left_keys = set()
    right_keys = set()
    count = 0
    try:
        while True:
            left_event = left_reader.readNextEvent()
            right_event = right_reader.readNextEvent()
            left_eof = not bool(left_event)
            right_eof = not bool(right_event)
            if left_eof or right_eof:
                if left_eof != right_eof:
                    raise RuntimeError(
                        f"LCIO pair reached EOF at different indices: {count}"
                    )
                break

            left_key = event_key(left_event)
            right_key = event_key(right_event)
            if left_key in left_keys:
                raise RuntimeError(f"duplicate left event key: {left_key}")
            if right_key in right_keys:
                raise RuntimeError(f"duplicate right event key: {right_key}")
            left_keys.add(left_key)
            right_keys.add(right_key)
            if left_key != right_key:
                raise RuntimeError(
                    f"ordered event-key mismatch at index {count}: "
                    f"{left_key} != {right_key}"
                )
            count += 1
    finally:
        left_reader.close()
        right_reader.close()

    if count != int(expected_events):
        raise RuntimeError(f"LCIO pair event count {count} != expected {expected_events}")
    return {
        "events": count,
        "ordered_event_keys_match": True,
        "simultaneous_eof": True,
        "unique_left_event_keys": True,
        "unique_right_event_keys": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--expected-events", type=int, required=True)
    args = parser.parse_args()
    result = validate_lcio_pair(
        args.left.resolve(strict=True),
        args.right.resolve(strict=True),
        args.expected_events,
    )
    print(VALIDATION_JSON_PREFIX + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
