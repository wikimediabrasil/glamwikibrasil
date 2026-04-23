import json
import os
from time import perf_counter
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.core.management import call_command

from glams.models import Glam

CHECKPOINT_FILE = "/data/project/glamwikibrasil/checkpoint.json"


def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {}


def save_checkpoint(data):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(data, f, indent=2)


class Command(BaseCommand):
    help = "Monthly update: mediafiles, mediausage, and mediarequests for all GLAMs."

    def add_arguments(self, parser):
        parser.add_argument("--start", type=str, default=None)
        parser.add_argument("--end", type=str, default=None)
        parser.add_argument("--concurrency", type=int, default=5)
        parser.add_argument("--skip-files", action="store_true")
        parser.add_argument("--skip-usage", action="store_true")
        parser.add_argument("--skip-requests", action="store_true")
        parser.add_argument("--reset-checkpoint", action="store_true", help="Ignore checkpoint and start fresh")

    def handle(self, *args, **options):
        start = options["start"] or "2015010100"
        concurrency = options["concurrency"]

        end = options["end"]
        if not end:
            last_month = datetime.now().replace(day=1) - timedelta(days=1)
            end = last_month.strftime("%Y%m%d") + "00"

        checkpoint = {} if options["reset_checkpoint"] else load_checkpoint()

        # If the run_id (year-month) changed, reset checkpoint automatically
        run_id = datetime.now().strftime("%Y-%m")
        if checkpoint.get("run_id") != run_id:
            self.stdout.write(f"New month detected ({run_id}), resetting checkpoint.")
            checkpoint = {"run_id": run_id}

        glams = list(Glam.objects.order_by("name_pt"))
        total_glams = len(glams)
        t_total = perf_counter()

        self.stdout.write(f"\n{'=' * 60}")
        self.stdout.write(f"GLAM Wiki Brasil — Monthly Update [{run_id}]")
        self.stdout.write(f"Range: {start} → {end}")
        self.stdout.write(f"GLAMs: {total_glams}")
        self.stdout.write(f"{'=' * 60}")

        for i, glam in enumerate(glams, 1):
            pk = glam.pk
            glam_checkpoint = checkpoint.get(pk, {})
            self.stdout.write(f"\n[{i}/{total_glams}] {glam.name_pt} ({pk})")

            # --- STEP 1: Mediafiles ---
            if not options["skip_files"]:
                if glam_checkpoint.get("files_done"):
                    self.stdout.write("  Step 1 (files): already done, skipping.")
                else:
                    try:
                        call_command("update_mediafiles", pk, stdout=self.stdout, stderr=self.stderr)
                        glam_checkpoint["files_done"] = True
                        checkpoint[pk] = glam_checkpoint
                        save_checkpoint(checkpoint)
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"  Step 1 (files) FAILED: {e}"))

            # --- STEP 2: Mediausage ---
            if not options["skip_usage"]:
                if glam_checkpoint.get("usage_done"):
                    self.stdout.write("  Step 2 (usage): already done, skipping.")
                else:
                    try:
                        call_command("update_mediausage", pk, stdout=self.stdout, stderr=self.stderr)
                        glam_checkpoint["usage_done"] = True
                        checkpoint[pk] = glam_checkpoint
                        save_checkpoint(checkpoint)
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"  Step 2 (usage) FAILED: {e}"))

            # --- STEP 3: Mediarequests ---
            if not options["skip_requests"]:
                if glam_checkpoint.get("requests_done"):
                    self.stdout.write("  Step 3 (requests): already done, skipping.")
                else:
                    try:
                        call_command(
                            "update_mediarequests",
                            pk,
                            start=start,
                            end=end,
                            stdout=self.stdout,
                            stderr=self.stderr,
                        )
                        glam_checkpoint["requests_done"] = True
                        checkpoint[pk] = glam_checkpoint
                        save_checkpoint(checkpoint)
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"  Step 3 (requests) FAILED: {e}"))

        elapsed = perf_counter() - t_total
        self.stdout.write(f"\n{'=' * 60}")
        self.stdout.write(self.style.SUCCESS(
            f"Full update complete in {elapsed:.1f}s ({elapsed / 60:.1f} min)"
        ))