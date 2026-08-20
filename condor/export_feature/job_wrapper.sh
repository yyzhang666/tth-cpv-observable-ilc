#!/usr/bin/env bash
# HTCondor wrapper: export features for one chunk.
#
# Arguments:
#   $1 = analysis config
#   $2 = chunk id
#   $3 = component (interference|sm)
#   $4 = level (reco|gen)

set -euo pipefail

CONFIG="$1"
CHUNK="$2"
COMPONENT="${3:-interference}"
LEVEL="${4:-reco}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

echo "[feature-export] host=$(hostname)"
echo "[feature-export] date=$(date -Is)"
echo "[feature-export] repo=$REPO_ROOT"
echo "[feature-export] config=$CONFIG chunk=$CHUNK component=$COMPONENT level=$LEVEL"

set +u
source env/setup.sh
set -u

python3 scripts/export_features.py \
  --config "$CONFIG" \
  --level "$LEVEL" \
  --chunk "$CHUNK" \
  --component "$COMPONENT"

echo "[feature-export] done"
