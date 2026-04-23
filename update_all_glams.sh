#!/bin/bash

# =============================================================================
# update_all_glams.sh
# Monthly update: mediafiles, mediausage, mediarequests for all GLAMs.
# Large GLAMs (>=THRESHOLD files) get dedicated Toolforge jobs.
# Small GLAMs are batched into a single sequential job.
# Checkpointing is handled by run_glam_update.py.
# =============================================================================

THRESHOLD=1000
SRC=/data/project/glamwikibrasil/www/python/src
VENV=/data/project/glamwikibrasil/www/python/venv/bin/activate
LOG_DIR=/data/project/glamwikibrasil/logs
MASTER_LOG=$LOG_DIR/master.log
TMP_LIST=/tmp/glam_list.txt
TOOLFORGE=$(which toolforge)

mkdir -p "$LOG_DIR"
rm -f "$TMP_LIST"

# =============================================================================
# Activate venv
# =============================================================================
source "$VENV" || { echo "Failed to activate venv"; exit 1; }
cd "$SRC" || { echo "Failed to cd to $SRC"; exit 1; }

echo "=================================================" | tee -a "$MASTER_LOG"
echo "GLAM Wiki Brasil — Monthly Update" | tee -a "$MASTER_LOG"
echo "Started: $(date)" | tee -a "$MASTER_LOG"
echo "=================================================" | tee -a "$MASTER_LOG"

# =============================================================================
# Get all GLAMs with file counts
# =============================================================================
echo "Fetching GLAM list..." | tee -a "$MASTER_LOG"

python manage.py shell -c "
from glams.models import Glam
from django.db.models import Count
for g in Glam.objects.annotate(n=Count('mediafile')).order_by('-n'):
    print(g.pk, g.n)
" 2>/dev/null > "$TMP_LIST"

if [ ! -s "$TMP_LIST" ]; then
    echo "ERROR: GLAM list is empty. Aborting." | tee -a "$MASTER_LOG"
    exit 1
fi

echo "GLAM list ready." | tee -a "$MASTER_LOG"
echo "=================================================" | tee -a "$MASTER_LOG"

SMALL_CHAIN=""

# =============================================================================
# Process each GLAM
# =============================================================================
while read pk count; do
    # Skip any non-Wikidata lines (garbage output)
    if [[ ! "$pk" =~ ^Q[0-9]+$ ]] || [[ ! "$count" =~ ^[0-9]+$ ]]; then
        echo "Skipping invalid line: '$pk $count'" | tee -a "$MASTER_LOG"
        continue
    fi

    JOB_NAME="update-$(echo $pk | tr '[:upper:]' '[:lower:]')"
    LOG="$LOG_DIR/update_${pk}.log"
    CMD="source $VENV && cd $SRC && python run_glam_update.py $pk $LOG 2>&1 | tee -a $MASTER_LOG"

    if [ "$count" -ge "$THRESHOLD" ]; then
        # -------------------------------------------------------------------
        # LARGE GLAM — dedicated Toolforge job
        # -------------------------------------------------------------------
        echo "Scheduling solo job for $pk ($count files)..." | tee -a "$MASTER_LOG"

        "$TOOLFORGE" jobs run "$JOB_NAME" \
            --command "bash -c '$CMD'" \
            --image python3.11 \
            --mount all \
            --mem 1Gi \
            --cpu 1

        if [ $? -ne 0 ]; then
            echo "WARNING: Failed to schedule job for $pk" | tee -a "$MASTER_LOG"
        fi

        sleep 2

    else
        # -------------------------------------------------------------------
        # SMALL GLAM — add to batch chain
        # -------------------------------------------------------------------
        echo "Queued small GLAM: $pk ($count files)" | tee -a "$MASTER_LOG"
        SMALL_CHAIN+="python run_glam_update.py $pk $LOG 2>&1 | tee -a $MASTER_LOG && "
    fi

done < "$TMP_LIST"

# ======================================