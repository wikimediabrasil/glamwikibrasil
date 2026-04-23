#!/usr/bin/env python
import sys
import os
import json
import datetime

# Setup Django
sys.path.insert(0, '/data/project/glamwikibrasil/www/python/src')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "glamwikibrasil.settings")

import django
django.setup()

from django.core.management import call_command

CHECKPOINT_FILE = '/data/project/glamwikibrasil/logs/checkpoint.json'


def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {}


def save_checkpoint(data):
    os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def mark_done(checkpoint, pk, step):
    current = datetime.datetime.now().strftime("%Y-%m")
    if checkpoint.get("run_id") != current:
        checkpoint.clear()
        checkpoint["run_id"] = current
    checkpoint.setdefault(pk, {})[step] = True
    save_checkpoint(checkpoint)


def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run(pk):
    checkpoint = load_checkpoint()
    glam_data = checkpoint.get(pk, {})

    log(f"=== Starting update for {pk} ===")

    # Step 1: mediafiles
    if not glam_data.get("files_done"):
        log("Step 1: mediafiles")
        try:
            call_command("update_mediafiles", pk)
            mark_done(checkpoint, pk, "files_done")
            log("Step 1: done")
        except Exception as e:
            log(f"Step 1 FAILED: {e}")
            sys.exit(1)
    else:
        log("Step 1: mediafiles already done, skipping")

    # Step 2: mediausage
    if not glam_data.get("usage_done"):
        log("Step 2: mediausage")
        try:
            call_command("update_mediausage", pk)
            mark_done(checkpoint, pk, "usage_done")
            log("Step 2: done")
        except Exception as e:
            log(f"Step 2 FAILED: {e}")
            sys.exit(1)
    else:
        log("Step 2: mediausage already done, skipping")

    # Step 3: mediarequests
    if not glam_data.get("requests_done"):
        log("Step 3: mediarequests")
        try:
            call_command("update_mediarequests", pk)
            mark_done(checkpoint, pk, "requests_done")
            log("Step 3: done")
        except Exception as e:
            log(f"Step 3 FAILED: {e}")
            sys.exit(1)
    else:
        log("Step 3: mediarequests already done, skipping")

    log(f"=== Finished {pk} ===")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: run_glam_update.py <pk>")
        sys.exit(1)
    run(sys.argv[1])