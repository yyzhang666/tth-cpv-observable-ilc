#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIAG_REPO_ROOT="$(cd "${HERE}/../.." && pwd)"

source "${DIAG_REPO_ROOT}/env/setup.sh"

python3 "${HERE}/run_o_w_diagnostics.py" \
  --repo-root "${DIAG_REPO_ROOT}" \
  --output-dir "${HERE}/results" \
  "$@"
