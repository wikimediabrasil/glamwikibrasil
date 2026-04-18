from time import perf_counter
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = "Monthly update: mediafiles, mediausage, and mediarequests for all GLAMs."

    def add_arguments(self, parser):
        parser.add_argument("--start", type=str, default=None, help="Start date YYYYMMDD00 (default: 2015010100)")
        parser.add_argument("--end", type=str, default=None, help="End date YYYYMMDD00 (default: last month)")
        parser.add_argument("--concurrency", type=int, default=5, help="Concurrent API requests (default: 5)")
        parser.add_argument("--skip-files", action="store_true", help="Skip mediafiles update")
        parser.add_argument("--skip-usage", action="store_true", help="Skip mediausage update")
        parser.add_argument("--skip-requests", action="store_true", help="Skip mediarequests update")

    def handle(self, *args, **options):
        start = options["start"] or "2015010100"
        concurrency = options["concurrency"]

        end = options["end"]
        if not end:
            last_month = datetime.now().replace(day=1) - timedelta(days=1)
            end = last_month.strftime("%Y%m%d") + "00"

        t_total = perf_counter()

        self.stdout.write(f"\n{'=' * 60}")
        self.stdout.write(f"GLAM Wiki Brasil — Monthly Update")
        self.stdout.write(f"Range: {start} → {end}")
        self.stdout.write(f"{'=' * 60}")

        # ==============================================================================================================
        # FILES
        # ==============================================================================================================
        if not options["skip_files"]:
            self.stdout.write("\n>>> STEP 1: Mediafiles")
            call_command("update_mediafiles", stdout=self.stdout, stderr=self.stderr)
        else:
            self.stdout.write("\n>>> STEP 1: Mediafiles [SKIPPED]")

        # ==============================================================================================================
        # USAGE
        # ==============================================================================================================
        if not options["skip_usage"]:
            self.stdout.write("\n>>> STEP 2: Mediausage")
            call_command("update_mediausage", stdout=self.stdout, stderr=self.stderr)
        else:
            self.stdout.write("\n>>> STEP 2: Mediausage [SKIPPED]")

        # ==============================================================================================================
        # REQUESTS
        # ==============================================================================================================
        if not options["skip_requests"]:
            self.stdout.write("\n>>> STEP 3: Mediarequests")
            call_command(
                "update_mediarequests",
                start=start,
                end=end,
                concurrency=concurrency,
                stdout=self.stdout,
                stderr=self.stderr,
            )
        else:
            self.stdout.write("\n>>> STEP 3: Mediarequests [SKIPPED]")

        elapsed = perf_counter() - t_total
        self.stdout.write(f"\n{'=' * 60}")
        self.stdout.write(self.style.SUCCESS(
            f"Full update complete in {elapsed:.1f}s ({elapsed / 60:.1f} min)"
        ))