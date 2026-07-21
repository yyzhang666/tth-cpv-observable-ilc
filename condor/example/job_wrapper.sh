#!/usr/bin/env bash
# HTCondor job wrapper: run the kinfit + jet assignment stage on ONE chunk.
#
# Arguments: $1 = analysis config, $2 = chunk id, $3 = component.
#
# The wrapper is self-contained: it locates the repo, sources the environment,
# and delegates to the standard runner (which enforces job-local work dirs
# and overwrite protection).

set -euo pipefail

CONFIG="$1"
CHUNK="$2"
COMPONENT="${3:-interference}"

# repo root: condor/example/ -> repo
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

echo "[job] host=$(hostname) date=$(date -Is)"
echo "[job] repo=$REPO_ROOT config=$CONFIG chunk=$CHUNK component=$COMPONENT"

# environment (ILCSoft/ZHH stack + PYTHONPATH)
set +u
source env/setup.sh
set -u

bash scripts/run_kinfit_assignment.sh \
  --config "$CONFIG" --chunk "$CHUNK" --component "$COMPONENT"

echo "[job] Done."
