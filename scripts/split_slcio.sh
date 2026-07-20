#!/usr/bin/env bash
# Split an SLCIO file into chunks of N events (debug workflow only).
#
# Debug outputs are never physics results; final numbers must be reproduced
# on the full sample (README rule 4). Split files are gitignored.
#
# Usage:
#   bash scripts/split_slcio.sh input.slcio output_prefix 1000
#
# Requires the LCIO tools from the ZHH environment:
#   source env/setup.sh   (provides lcio_split_file)

set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 INPUT_SLCIO OUTPUT_PREFIX EVENTS_PER_CHUNK" >&2
  exit 1
fi

INPUT="$1"
PREFIX="$2"
CHUNK="$3"

[[ -e "$INPUT" ]] || { echo "Missing input: $INPUT" >&2; exit 1; }

if command -v lcio_split_file >/dev/null 2>&1; then
  # lcio_split_file splits by approximate output file size; convert via a
  # measured events/size ratio is overkill for debugging — prefer the python
  # fallback below for exact event counts when pyLCIO is available.
  echo "[info] using python pyLCIO splitter for exact event counts"
fi

python3 - "$INPUT" "$PREFIX" "$CHUNK" <<'PY'
import sys
from pathlib import Path

try:
    from pyLCIO import IOIMPL
except Exception as exc:
    raise SystemExit(
        f"pyLCIO unavailable ({exc}); source env/setup.sh first, or use "
        "--max-events early stopping instead of splitting (KNOWN_ISSUES #11)."
    )

src, prefix, chunk = sys.argv[1], sys.argv[2], int(sys.argv[3])
reader = IOIMPL.LCFactory.getInstance().createLCReader()
reader.open(src)

writer = None
count = total = part = 0
while True:
    evt = reader.readNextEvent()
    if evt is None:
        break
    if writer is None or count >= chunk:
        if writer is not None:
            writer.close()
        part += 1
        count = 0
        out = f"{prefix}_part{part:03d}.slcio"
        if Path(out).exists():
            raise SystemExit(f"Refusing to overwrite {out}")
        writer = IOIMPL.LCFactory.getInstance().createLCWriter()
        writer.open(out)
        print(f"[split] -> {out}")
    writer.writeEvent(evt)
    count += 1
    total += 1
if writer is not None:
    writer.close()
reader.close()
print(f"[done] {total} events into {part} chunks")
PY
