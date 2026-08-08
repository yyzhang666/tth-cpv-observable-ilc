#!/usr/bin/env bash
# =============================================================================
# link_kinfit_inputs.sh
#
# Create repo-local, canonically named symlinks to the shared kinfit ROOT
# files:
#
#   data/kinfit/physsim/kinfit_<sample_key>_chunk<N>.root
#   data/kinfit/whizard/kinfit_<sample_key>_chunk<N>.root
#
# The source ROOT files are never renamed or modified. Only the local symlink
# names are canonicalized.
#
# Re-running this script:
#   - replaces existing symlinks;
#   - removes duplicate symlinks pointing to the same source file;
#   - never overwrites a regular file.
#
# Usage:
#   bash scripts/link_kinfit_inputs.sh
#
# Optional source overrides:
#   TTH_KINFIT_PHYSSIM=/other/path \
#   TTH_KINFIT_WHIZARD=/other/path \
#   bash scripts/link_kinfit_inputs.sh
# =============================================================================

set -euo pipefail

PHYSSIM_SRC="${TTH_KINFIT_PHYSSIM:-/data/dust/user/zhangyuy/analysis/tth/events_physsim/kinfit/mva_inputs_20260731}"
WHIZARD_SRC="${TTH_KINFIT_WHIZARD:-/data/dust/user/zhangyuy/analysis/tth/events_whizard/kinfit/mva_inputs_20260731}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LINK_ROOT="$REPO_ROOT/data/kinfit"

mkdir -p "$LINK_ROOT"


canonical_root_name() {
    local source_path="$1"
    local basename

    basename="$(basename "$source_path")"

    # Already canonical:
    #   kinfit_tthcpv_reco_elpr_chunk0.root
    if [[ "$basename" =~ ^kinfit_(.+)_chunk([0-9]+)\.root$ ]]; then
        printf '%s\n' "$basename"
        return 0
    fi

    # Accept files missing only the leading "kinfit_":
    #   tthcpv_reco_elpr_chunk0.root
    # becomes:
    #   kinfit_tthcpv_reco_elpr_chunk0.root
    if [[ "$basename" =~ ^(.+)_chunk([0-9]+)\.root$ ]]; then
        printf 'kinfit_%s\n' "$basename"
        return 0
    fi

    # Handle raw batch job filenames:
    #   kinfit_physsim__tth-cpv__eL.pR__I01234_0_1.root
    #   physsim__ttbb__eR.pL__I01234_0_56.root
    if [[ "$basename" =~ ^(kinfit_)?[a-zA-Z0-9]+__([^_]+)__([^_]+)__.*_([0-9]+)\.root$ ]]; then
        local raw_sample="${BASH_REMATCH[2]}"
        local raw_pol="${BASH_REMATCH[3]}"
        local chunk="${BASH_REMATCH[4]}"

        local sample_clean
        sample_clean="$(echo "$raw_sample" | tr -d '-')"

        local pol_clean
        pol_clean="$(echo "$raw_pol" | tr -d '.' | tr '[:upper:]' '[:lower:]')"

        printf 'kinfit_%s_reco_%s_chunk%s.root\n' "$sample_clean" "$pol_clean" "$chunk"
        return 0
    fi

    echo "[link_kinfit_inputs] ERROR: cannot infer canonical name from:" >&2
    echo "  $source_path" >&2
    echo "Expected one of:" >&2
    echo "  kinfit_<sample_key>_chunk<N>.root" >&2
    echo "  <sample_key>_chunk<N>.root" >&2
    return 1
}


prepare_destination_directory() {
    local destination="$1"

    # The old script created destination as one directory symlink.
    # Remove that symlink before replacing it with a real local directory.
    if [[ -L "$destination" ]]; then
        echo "[link_kinfit_inputs] removing old directory link: $destination"
        rm -f "$destination"
    elif [[ -e "$destination" && ! -d "$destination" ]]; then
        echo "[link_kinfit_inputs] ERROR: destination exists but is not a directory:" >&2
        echo "  $destination" >&2
        exit 1
    fi

    mkdir -p "$destination"
}


remove_duplicate_links() {
    local destination_dir="$1"
    local canonical_path="$2"
    local source_real="$3"

    local existing_link
    local existing_real

    while IFS= read -r -d '' existing_link; do
        [[ "$existing_link" == "$canonical_path" ]] && continue

        existing_real="$(readlink -f "$existing_link" 2>/dev/null || true)"

        if [[ -n "$existing_real" && "$existing_real" == "$source_real" ]]; then
            echo "[link_kinfit_inputs] removing duplicate link:"
            echo "  $existing_link"
            rm -f "$existing_link"
        fi
    done < <(
        find "$destination_dir" \
            -maxdepth 1 \
            -type l \
            -name '*.root' \
            -print0
    )
}


link_root_directory() {
    local source_dir="$1"
    local family="$2"
    local destination_dir="$LINK_ROOT/$family"

    if [[ ! -d "$source_dir" ]]; then
        echo "[link_kinfit_inputs] ERROR: source directory not found/readable:" >&2
        echo "  $source_dir" >&2
        echo "On NAF, check directory permissions with:" >&2
        echo "  ls -ld \"$source_dir\"" >&2
        exit 1
    fi

    prepare_destination_directory "$destination_dir"

    local source_file
    local source_real
    local canonical_name
    local canonical_path
    local count=0

    # Detect accidental collisions within one source tree.
    declare -A claimed_names=()

    while IFS= read -r -d '' source_file; do
        # SKIP failed job artifacts and temporary work folders:
        if [[ "$source_file" =~ /(failed|runner_output|work_)/ ]]; then
            continue
        fi

        source_real="$(readlink -f "$source_file")"
        canonical_name="$(canonical_root_name "$source_file")"
        canonical_path="$destination_dir/$canonical_name"

        if [[ -n "${claimed_names[$canonical_name]:-}" &&
              "${claimed_names[$canonical_name]}" != "$source_real" ]]; then
            echo "[link_kinfit_inputs] ERROR: two source files map to the same name:" >&2
            echo "  name   : $canonical_name" >&2
            echo "  source1: ${claimed_names[$canonical_name]}" >&2
            echo "  source2: $source_real" >&2
            exit 1
        fi
        claimed_names["$canonical_name"]="$source_real"

        # Never replace a real file owned by the student.
        if [[ -e "$canonical_path" && ! -L "$canonical_path" ]]; then
            echo "[link_kinfit_inputs] ERROR: refusing to overwrite regular file:" >&2
            echo "  $canonical_path" >&2
            exit 1
        fi

        remove_duplicate_links \
            "$destination_dir" \
            "$canonical_path" \
            "$source_real"

        # -s: symbolic link
        # -f: replace existing destination
        # -n: do not dereference an existing directory symlink
        ln -sfn "$source_real" "$canonical_path"

        echo "[link_kinfit_inputs] $canonical_path"
        echo "                     -> $source_real"

        count=$((count + 1))
    done < <(
        find -L "$source_dir" \
            -type f \
            -name '*.root' \
            -print0 |
        sort -z
    )

    if [[ "$count" -eq 0 ]]; then
        echo "[link_kinfit_inputs] ERROR: no ROOT files found under:" >&2
        echo "  $source_dir" >&2
        exit 1
    fi

    echo "[link_kinfit_inputs] linked $count $family ROOT files"
}


link_root_directory "$PHYSSIM_SRC" physsim
link_root_directory "$WHIZARD_SRC" whizard

echo
echo "[link_kinfit_inputs] done"
echo "[link_kinfit_inputs] canonical ROOT directory:"
echo "  $LINK_ROOT"
