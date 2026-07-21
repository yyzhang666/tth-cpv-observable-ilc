#!/usr/bin/env bash
# Merge SLCIO files (debug workflow only; merged debug files are gitignored).
#
# Usage:
#   bash scripts/merge_slcio.sh merged.slcio split_*.slcio

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 OUTPUT_SLCIO INPUT1.slcio [INPUT2.slcio ...]" >&2
  exit 1
fi

OUTPUT="$1"
shift

[[ -e "$OUTPUT" ]] && { echo "Refusing to overwrite existing $OUTPUT" >&2; exit 1; }

python3 - "$OUTPUT" "$@" <<'PY'
import sys

try:
    from pyLCIO import IOIMPL
except Exception as exc:
    raise SystemExit(
        f"pyLCIO unavailable ({exc}); source env/setup.sh first (see KNOWN_ISSUES.md)."
    )

out, inputs = sys.argv[1], sys.argv[2:]
writer = IOIMPL.LCFactory.getInstance().createLCWriter()
writer.open(out)
total = 0
for src in inputs:
    reader = IOIMPL.LCFactory.getInstance().createLCReader()
    reader.open(src)
    n = 0
    while True:
        evt = reader.readNextEvent()
        if evt is None:
            break
        writer.writeEvent(evt)
        n += 1
    reader.close()
    total += n
    print(f"[merge] {src}: {n} events")
writer.close()
print(f"[done] {total} events -> {out}")
PY
