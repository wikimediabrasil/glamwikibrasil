#!/bin/bash

# =============================================================================
# update_all_glams.sh
# Monthly update: mediafiles, mediausage, mediarequests for all GLAMs.
# Large GLAMs (>=THRESHOLD) get dedicated Toolforge jobs.
# Small GLAMs run sequentially in one job.
# =============================================================================

THRESHOLD=1000
SRC=/data/project/glamwikibrasil/www/python/src
VENV=/data/project/glamwikibrasil/www/python/venv/bin/activate
LOG_DIR=/data/project/glamwikibrasil/logs
TMP_LIST=/tmp/glam_list.txt

mkdir -p "$LOG_DIR"
rm -f "$TMP_LIST"

# =============================================================================
# Find toolforge binary
# =============================================================================
TOOLFORGE=$(command -v toolforge)
if [ -z "$TOOLFORGE" ]; then
    # common Toolforge locations
    for p in /usr/bin/toolforge ~/.local/bin/toolforge /usr/local/bin/toolforge; do
        if [ -x "$p" ]; then TOOLFORGE="$p"; break; fi
    done
fi
if [ -z "$TOOLFORGE" ]; then
    echo "ERROR: toolforge binary not found. Are you on the bastion?"
    exit 1
fi
echo "Using toolforge at: $TOOLFORGE"

# =============================================================================
# Activate venv
# =============================================================================
source "$VENV" || { echo "ERROR: Failed to activate venv"; exit 1; }
cd "$SRC" || { echo "ERROR: Failed to cd to $SRC"; exit 1; }

echo "================================================="
echo "GLAM Wiki Brasil — Monthly Update"
echo "Started: $(date)"
echo "================================================="

# =============================================================================
# Check quota before starting
# =============================================================================
echo "Current quota:"
"$TOOLFORGE" jobs quota
echo ""

# =============================================================================
# Get all GLAMs with file counts
# =============================================================================
echo "Fetching GLAM list..."
python manage.py shell -c "
from glams.models import Glam
from django.db.models import Count
for g in Glam.objects.annotate(n=Count('mediafile')).order_by('-n'):
    print(g.pk, g.n)
" 2>/dev/null | grep -E "^Q[0-9]+ [0-9]+$" > "$TMP_LIST"

if [ ! -s "$TMP_LIST" ]; then
    echo "ERROR: GLAM list is empty. Aborting."
    exit 1
fi

TOTAL=$(wc -l < "$TMP_LIST")
echo "Found $TOTAL GLAMs."
echo "================================================="

# =============================================================================
# Build small GLAMs script
# =============================================================================
SMALL_SCRIPT=/tmp/run_small_glams.sh
echo "#!/bin/bash" > "$SMALL_SCRIPT"
echo "source $VENV" >> "$SMALL_SCRIPT"
echo "cd $SRC" >> "$SMALL_SCRIPT"
echo "" >> "$SMALL_SCRIPT"

SMALL_COUNT=0
LARGE_COUNT=0

while read pk count; do
    JOB_NAME="update-$(echo $pk | tr '[:upper:]' '[:lower:]')"

    if [ "$count" -ge "$THRESHOLD" ]; then
        # -------------------------------------------------------------------
        # LARGE GLAM — dedicated job, logs handled by Toolforge natively
        # -------------------------------------------------------------------
        echo "Scheduling solo job for $pk ($count files)..."

        "$TOOLFORGE" jobs run "$JOB_NAME" \
            --command "./run_glam_update.py $pk" \
            --image python3.11 \
            --mount all \
            --mem 2Gi \
            --cpu 1 \
            --filelog-stdout "$LOG_DIR/update_${pk}.out" \
            --filelog-stderr "$LOG_DIR/update_${pk}.err" \
            --emails onfailure

        if [ $? -eq 0 ]; then
            echo "  → Scheduled OK"
            LARGE_COUNT=$((LARGE_COUNT + 1))
        else
            echo "  → WARNING: Failed to schedule $pk"
        fi

        sleep 2

    else
        # -------------------------------------------------------------------
        # SMALL GLAM — append to batch script
        # -------------------------------------------------------------------
        echo "echo '--- $pk ($count files) ---'" >> "$SMALL_SCRIPT"
        echo "python run_glam_update.py $pk" >> "$SMALL_SCRIPT"
        echo "" >> "$SMALL_SCRIPT"
        SMALL_COUNT=$((SMALL_COUNT + 1))
    fi

done < "$TMP_LIST"

# =============================================================================
# Submit batch job for all small GLAMs
# =============================================================================
if [ "$SMALL_COUNT" -gt 0 ]; then
    chmod +x "$SMALL_SCRIPT"
    cp "$SMALL_SCRIPT" "$SRC/run_small_glams.sh"

    echo ""
    echo "Scheduling batch job for $SMALL_COUNT small GLAMs..."

    "$TOOLFORGE" jobs run "update-small-glams" \
        --command "./run_small_glams.sh" \
        --image python3.11 \
        --mount all \
        --mem 1Gi \
        --cpu 1 \
        --filelog-stdout "$LOG_DIR/update_small_glams.out" \
        --filelog-stderr "$LOG_DIR/update_small_glams.err" \
        --emails onfailure

    if [ $? -eq 0 ]; then
        echo "  → Scheduled OK"
    else
        echo "  → WARNING: Failed to schedule small GLAMs batch"
    fi
fi

# =============================================================================
# Cleanup
# =============================================================================
rm -f "$TMP_LIST" "$SMALL_SCRIPT"

echo ""
echo "================================================="
echo "Done scheduling at: $(date)"
echo "Large GLAMs (solo jobs): $LARGE_COUNT"
echo "Small GLAMs (batch job): $SMALL_COUNT"
echo ""
echo "Monitor with:"
echo "  $TOOLFORGE jobs list"
echo "  $TOOLFORGE jobs logs update-small-glams -f"
echo "  $TOOLFORGE jobs logs update-q120985596 -f"
echo "  tail -f $LOG_DIR/update_Q120985596.out"
echo "================================================="