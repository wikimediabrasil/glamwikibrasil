#!/bin/bash

# =============================================================================
# update_all_glams.sh
# Monthly update: mediafiles, mediausage, mediarequests for all GLAMs.
# Large GLAMs (>=THRESHOLD files) get dedicated jobs.
# Small GLAMs are batched into a single sequential job.
# Checkpointing ensures no GLAM step is repeated on re-run.
# =============================================================================

THRESHOLD=1000
SRC=~/www/python/src
VENV=~/www/python/venv/bin/activate
LOG_DIR=~/logs
CHECKPOINT_FILE=~/logs/checkpoint.json
TMP_LIST=/tmp/glam_list.txt
TMP_SMALL=/tmp/small_glams.txt

mkdir -p "$LOG_DIR"
rm -f "$TMP_LIST" "$TMP_SMALL"

# =============================================================================
# Helper: check if a GLAM step is already done in checkpoint
# Usage: is_done Q12345 files_done
# =============================================================================
is_done() {
    local pk=$1
    local step=$2
    if [ ! -f "$CHECKPOINT_FILE" ]; then return 1; fi
    result=$(python3 -c "
import json, sys
data = json.load(open('$CHECKPOINT_FILE'))
run_id = data.get('run_id', '')
import datetime
current = datetime.datetime.now().strftime('%Y-%m')
if run_id != current:
    sys.exit(1)
glam = data.get('$pk', {})
sys.exit(0 if glam.get('$step') else 1)
" 2>/dev/null)
    return $?
}

# =============================================================================
# Helper: mark a GLAM step as done in checkpoint
# Usage: mark_done Q12345 files_done
# =============================================================================
mark_done() {
    local pk=$1
    local step=$2
    python3 -c "
import json, os, datetime
f = '$CHECKPOINT_FILE'
data = json.load(open(f)) if os.path.exists(f) else {}
current = datetime.datetime.now().strftime('%Y-%m')
if data.get('run_id') != current:
    data = {'run_id': current}
if '$pk' not in data:
    data['$pk'] = {}
data['$pk']['$step'] = True
json.dump(data, open(f, 'w'), indent=2)
"
}

# =============================================================================
# Activate venv
# =============================================================================
source "$VENV"
cd "$SRC" || exit 1

# =============================================================================
# Get all GLAMs with file counts
# =============================================================================
echo "Fetching GLAM list..."
python manage.py shell -c "
from glams.models import Glam
from django.db.models import Count
for g in Glam.objects.annotate(n=Count('mediafile')).order_by('-n'):
    print(g.pk, g.n)
" > "$TMP_LIST"

echo "GLAM list ready. Scheduling jobs..."
echo "=================================================="

SMALL_CHAIN=""

# =============================================================================
# Process each GLAM
# =============================================================================
while read pk count; do
    JOB_NAME="update-$(echo $pk | tr '[:upper:]' '[:lower:]')"
    LOG="$LOG_DIR/update_${pk}.log"

    if [ "$count" -ge "$THRESHOLD" ]; then
        # -----------------------------------------------------------------------
        # LARGE GLAM — dedicated Toolforge job with all 3 steps + checkpointing
        # -----------------------------------------------------------------------
        echo "Scheduling solo job for $pk ($count files)..."

        CMD="bash -c '"
        CMD+="source $VENV && cd $SRC && "

        # Step 1: mediafiles
        CMD+="python -c \"import subprocess,sys; "
        CMD+="r=subprocess.run(['python','manage.py','update_mediafiles','$pk'],capture_output=True,text=True); "
        CMD+="open('$LOG','a').write(r.stdout+r.stderr)\" && "
        CMD+="python3 -c \""
        CMD+="import json,os,datetime; f='$CHECKPOINT_FILE'; "
        CMD+="d=json.load(open(f)) if os.path.exists(f) else {}; "
        CMD+="d.setdefault('$pk',{})['files_done']=True; "
        CMD+="json.dump(d,open(f,'w'),indent=2)\" && "

        # Step 2: mediausage
        CMD+="python manage.py update_mediausage $pk >> $LOG 2>&1 && "
        CMD+="python3 -c \""
        CMD+="import json,os; f='$CHECKPOINT_FILE'; "
        CMD+="d=json.load(open(f)); d.setdefault('$pk',{})['usage_done']=True; "
        CMD+="json.dump(d,open(f,'w'),indent=2)\" && "

        # Step 3: mediarequests
        CMD+="python manage.py update_mediarequests $pk >> $LOG 2>&1 && "
        CMD+="python3 -c \""
        CMD+="import json,os; f='$CHECKPOINT_FILE'; "
        CMD+="d=json.load(open(f)); d.setdefault('$pk',{})['requests_done']=True; "
        CMD+="json.dump(d,open(f,'w'),indent=2)\""

        CMD+="'"

        toolforge jobs run "$JOB_NAME" \
            --command "$CMD" \
            --image python3.11 \
            --mount all \
            --mem 1Gi \
            --cpu 1
        sleep 2

    else
        # -----------------------------------------------------------------------
        # SMALL GLAM — add all 3 steps to the batch chain
        # -----------------------------------------------------------------------
        LOG="$LOG_DIR/update_${pk}.log"

        SMALL_CHAIN+="echo '--- $pk ---' >> $LOG 2>&1 && "

        # Step 1
        SMALL_CHAIN+="python manage.py update_mediafiles $pk >> $LOG 2>&1 && "
        SMALL_CHAIN+="python3 -c \""
        SMALL_CHAIN+="import json,os; f='$CHECKPOINT_FILE'; "
        SMALL_CHAIN+="d=json.load(open(f)) if os.path.exists(f) else {}; "
        SMALL_CHAIN+="d.setdefault('$pk',{})['files_done']=True; "
        SMALL_CHAIN+="json.dump(d,open(f,'w'),indent=2)\" && "

        # Step 2
        SMALL_CHAIN+="python manage.py update_mediausage $pk >> $LOG 2>&1 && "
        SMALL_CHAIN+="python3 -c \""
        SMALL_CHAIN+="import json,os; f='$CHECKPOINT_FILE'; "
        SMALL_CHAIN+="d=json.load(open(f)); "
        SMALL_CHAIN+="d.setdefault('$pk',{})['usage_done']=True; "
        SMALL_CHAIN+="json.dump(d,open(f,'w'),indent=2)\" && "

        # Step 3
        SMALL_CHAIN+="python manage.py update_mediarequests $pk >> $LOG 2>&1 && "
        SMALL_CHAIN+="python3 -c \""
        SMALL_CHAIN+="import json,os; f='$CHECKPOINT_FILE'; "
        SMALL_CHAIN+="d=json.load(open(f)); "
        SMALL_CHAIN+="d.setdefault('$pk',{})['requests_done']=True; "
        SMALL_CHAIN+="json.dump(d,open(f,'w'),indent=2)\" && "

        echo "Queued small GLAM: $pk ($count files)"
    fi

done < "$TMP_LIST"

# =============================================================================
# Submit batch job for all small GLAMs
# =============================================================================
if [ -n "$SMALL_CHAIN" ]; then
    # Remove trailing &&
    SMALL_CHAIN="${SMALL_CHAIN% && }"

    echo ""
    echo "Scheduling batch job for small GLAMs..."

    toolforge jobs run "update-small-glams" \
        --command "bash -c 'source $VENV && cd $SRC && $SMALL_CHAIN'" \
        --image python3.11 \
        --mount all \
        --mem 1Gi \
        --cpu 1
fi

# =============================================================================
# Cleanup
# =============================================================================
rm -f "$TMP_LIST" "$TMP_SMALL"

echo ""
echo "=================================================="
echo "All jobs scheduled."
echo "Monitor with:  toolforge jobs list"
echo "Live logs:     tail -f ~/logs/update_<pk>.log"
echo "Checkpoint:    cat $CHECKPOINT_FILE"