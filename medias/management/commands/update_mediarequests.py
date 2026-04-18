import asyncio
from django.core.management.base import BaseCommand, CommandError
from glams.models import Glam
from medias.views import get_media_batch, get_existing_file_ids_for_month
from medias.utils import get_requests_async, create_media_request
from medias.models import MediaFile, MediaRequests
from datetime import datetime, timedelta
from asgiref.sync import sync_to_async
import aiohttp
from time import perf_counter


class Command(BaseCommand):
    help = "Update MediaRequests for a single GLAM. Usage: manage.py update_glam_requests <wikidata_id>"

    def add_arguments(self, parser):
        parser.add_argument("pk", type=str, help="Wikidata ID of the GLAM (e.g. Q12345)")
        parser.add_argument("--start", type=str, default=None, help="Start date in format YYYYMMDD00 (default: 2015010100)")
        parser.add_argument("--end", type=str, default=None, help="End date in format YYYYMMDD00 (default: last month)")

    def handle(self, *args, **options):
        pk = options["pk"]
        start = options["start"]
        end = options["end"]

        try:
            glam = Glam.objects.get(pk=pk)
        except Glam.DoesNotExist:
            raise CommandError(f"GLAM with pk '{pk}' does not exist.")

        total_files = MediaFile.objects.filter(glam=glam).count()
        self.stdout.write(f"GLAM: {glam.name_pt}")
        self.stdout.write(f"Total files in DB: {total_files}")

        t_start = perf_counter()
        asyncio.run(self.run_async(glam.pk, start, end))
        elapsed = perf_counter() - t_start

        total_requests = MediaRequests.objects.filter(file__glam=glam).count()
        self.stdout.write(
            self.style.SUCCESS(f"\nDone! Total MediaRequests records in DB for this GLAM: {total_requests}"))
        self.stdout.write(self.style.SUCCESS(f"Time elapsed: {elapsed:.2f}s ({elapsed / 60:.1f} min)"))

    async def run_async(self, pk, start, end):
        if not start:
            start = "2015010100"
        if not end:
            last_month = datetime.now().replace(day=1) - timedelta(days=1)
            end = last_month.strftime("%Y%m%d") + "00"

        self.stdout.write(f"Date range: {start} → {end}\n")

        glam = await sync_to_async(Glam.objects.get, thread_sensitive=True)(pk=pk)

        existing_page_ids = await sync_to_async(
            get_existing_file_ids_for_month, thread_sensitive=True
        )(glam, start, end)

        self.stdout.write(f"Files already with requests in this range: {len(existing_page_ids)}")

        total_files = await sync_to_async(
            lambda: MediaFile.objects.filter(glam=glam).exclude(page_id__in=existing_page_ids).count()
        )()
        self.stdout.write(f"Files still to process: {total_files}\n")

        if total_files == 0:
            self.stdout.write(self.style.SUCCESS("All files are up to date!"))
            return

        CONCURRENCY = 5
        semaphore = asyncio.Semaphore(CONCURRENCY)

        api_calls = 0
        lock = asyncio.Lock()

        async def fetch_with_semaphore(session, media):
            nonlocal api_calls
            async with semaphore:
                await asyncio.sleep(0.5)
                items = await get_requests_async(session, media.file_path, start, end)
                async with lock:
                    api_calls += 1
                    if api_calls % 50 == 0:
                        self.stdout.write(f"  API calls so far: {api_calls}/{total_files}")
                return (media, items)

        chunk_size = 500
        offset = 0
        total_inserted = 0

        headers = {
            "User-Agent": "GLAMWikiBrasil/1.0 (https://glamwikibrasil.toolforge.org; tecnologia@wmnobrasil.org)"
        }
        connector = aiohttp.TCPConnector(limit=CONCURRENCY)
        timeout = aiohttp.ClientTimeout(total=60)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=headers) as session:
            while True:
                media_batch = await sync_to_async(
                    get_media_batch, thread_sensitive=True
                )(glam.pk, existing_page_ids, offset, chunk_size)

                if not media_batch:
                    self.stdout.write(f"\nNo more files to process. Total API calls made: {api_calls}")
                    break

                self.stdout.write(f"Processing batch offset={offset}, size={len(media_batch)}...")

                tasks = [fetch_with_semaphore(session, media) for media in media_batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                errors = [r for r in results if isinstance(r, Exception)]
                valid_results = [r for r in results if not isinstance(r, Exception)]

                if errors:
                    self.stdout.write(self.style.WARNING(f"  {len(errors)} requests failed in this batch."))
                    self.stdout.write(self.style.ERROR(f"  First error: {errors[0]}"))

                if valid_results:
                    before = await sync_to_async(
                        lambda: MediaRequests.objects.filter(file__glam=glam).count()
                    )()
                    await sync_to_async(create_media_request, thread_sensitive=True)(valid_results)
                    after = await sync_to_async(
                        lambda: MediaRequests.objects.filter(file__glam=glam).count()
                    )()
                    inserted = after - before
                    total_inserted += inserted
                    self.stdout.write(
                        self.style.SUCCESS(f"  Inserted {inserted} new records (total so far: {total_inserted})"))

                offset += chunk_size