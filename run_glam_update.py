#!/usr/bin/env python
import sys
import json
import os
import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "glamwikibrasil.settings")  # adjust if needed

import django
django.setup()

from django.core.management import call_command

CHECKPOINT_FILE = os.path.expanduser("~/logs/checkpoint.json")


def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {}


def save_checkpoint(data):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def mark_done(checkpoint, pk, step):
    current = datetime.datetime.now().strftime("%Y-%m")
    if checkpoint.get("run_id") != current:
        checkpoint.clear()
        checkpoint["run_id"] = current
    checkpoint.setdefault(pk, {})[step] = True
    save_checkpoint(checkpoint)


def run(pk, log_path):
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    checkpoint = load_checkpoint()
    glam_data = checkpoint.get(pk, {})

    with open(log_path, "a", buffering=1) as log:
        def out(msg):
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            line = f"[{ts}] {msg}\n"
            log.write(line)
            log.flush()

        out(f"=== Starting update for {pk} ===")

        # Step 1: mediafiles
        if not glam_data.get("files_done"):
            out("Step 1: mediafiles")
            try:
                call_command("update_mediafiles", pk, stdout=log, stderr=log)
                mark_done(checkpoint, pk, "files_done")
                out("Step 1: done")
            except Exception as e:
                out(f"Step 1 FAILED: {e}")
                sys.exit(1)
        else:
            out("Step 1: mediafiles already done, skipping")

        # Step 2: mediausage
        if not glam_data.get("usage_done"):
            out("Step 2: mediausage")
            try:
                call_command("update_mediausage", pk, stdout=log, stderr=log)
                mark_done(checkpoint, pk, "usage_done")
                out("Step 2: done")
            except Exception as e:
                out(f"Step 2 FAILED: {e}")
                sys.exit(1)
        else:
            out("Step 2: mediausage already done, skipping")

        # Step 3: mediarequests
        if not glam_data.get("requests_done"):
            out("Step 3: mediarequests")
            try:
                call_command("update_mediarequests", pk, stdout=log, stderr=log)
                mark_done(checkpoint, pk, "requests_done")
                out("Step 3: done")
            except Exception as e:
                out(f"Step 3 FAILED: {e}")
                sys.exit(1)
        else:
            out("Step 3: mediarequests already done, skipping")

        out(f"=== Finished {pk} ===")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python run_glam_update.py <pk> <log_path>")
        sys.exit(1)

    pk = sys.argv[1]
    log_path = sys.argv[2]
    run(pk, log_path)