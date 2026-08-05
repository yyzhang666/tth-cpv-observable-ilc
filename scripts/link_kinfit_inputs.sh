#!/usr/bin/env bash
# =============================================================================
# link_kinfit_inputs.sh — create repo-local symlinks to the shared kinfit
# ROOT trees so that every clone sees them at the same repo-relative paths:
#
#   data/kinfit/physsim -> <events_physsim>/kinfit/mva_inputs_20260731
#   data/kinfit/whizard -> <events_whizard>/kinfit/mva_inputs_20260731
#
# Configs and scripts should reference data/kinfit/... (repo-relative) only;
# the link targets are machine-specific and gitignored (data/ is ignored).
#
# Usage:
#   bash scripts/link_kinfit_inputs.sh                # use the NAF defaults
#   TTH_KINFIT_PHYSSIM=/other/path \
#   TTH_KINFIT_WHIZARD=/other/path \
#   bash scripts/link_kinfit_inputs.sh                # override per machine
# =============================================================================
set -euo pipefail

PHYSSIM_SRC="${TTH_KINFIT_PHYSSIM:-/data/dust/user/zhangyuy/analysis/tth/events_physsim/kinfit/mva_inputs_20260731}"
WHIZARD_SRC="${TTH_KINFIT_WHIZARD:-/data/dust/user/zhangyuy/analysis/tth/events_whizard/kinfit/mva_inputs_20260731}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LINK_DIR="$REPO_ROOT/data/kinfit"
mkdir -p "$LINK_DIR"

link_one() {
    local src="$1" name="$2"
    if [[ ! -d "$src" ]]; then
        echo "[link_kinfit_inputs] ERROR: source dir not found/readable: $src" >&2
        echo "  On NAF this usually means missing read permission; ask the owner" >&2
        echo "  to run: chmod -R a+rX $src" >&2
        exit 1
    fi
    # -n: replace an existing link instead of descending into it (idempotent)
    ln -sfn "$src" "$LINK_DIR/$name"
    echo "[link_kinfit_inputs] $LINK_DIR/$name -> $src"
}

link_one "$PHYSSIM_SRC" physsim
link_one "$WHIZARD_SRC" whizard

echo "[link_kinfit_inputs] done. Reference these in configs as data/kinfit/physsim and data/kinfit/whizard (repo-relative)."
