#!/bin/bash

# =============================================================================
# update_all_glams.sh
# =============================================================================

THRESHOLD=1000
SRC=/data/project/glamwikibrasil/www/python/src
LOG_DIR=/data/project/glamwikibrasil/logs
GLAM_LIST=$LOG_DIR/glam_list.txt
DRY_RUN=false

# Parse --dry-run flag
for arg in "$@"; do
    if [ "$arg" = "--dry-run" ]; then
        DRY_RUN=true
    fi
done

mkdir -p "$LOG_DIR"

# =============================================================================
# Find toolforge binary
# =============================================================================
TOOLFORGE=""
if command -v toolforge &>/dev/null; then
    TOOLFORGE=$(command -v toolforge)
else
    for p in /usr/bin/toolforge "$HOME/.local/bin/toolforge" /usr/local/bin/toolforge; do
        if [ -x "$p" ]; then
            TOOLFORGE="$p"
            break
        fi
    done
fi

if [ -z "$TOOLFORGE" ]; then
    echo "ERROR: toolforge binary not found."
    exit 1
fi

# Wrap toolforge for dry run
run_toolforge() {
    if [ "$DRY_RUN" = true ]; then
        echo "WOULD SUBMIT: toolforge $*"
    else
        "$TOOLFORGE" "$@"
    fi
}

echo "Using toolforge at: $TOOLFORGE"
echo "Dry run: $DRY_RUN"
echo "================================================="
echo "GLAM Wiki Brasil — Monthly Update"
echo "Started: $(date)"
echo "================================================="

# ==================