import asyncio
from datetime import datetime, timedelta
from time import perf_counter

import aiohttp
from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from glams.models import Glam
from medias.models import MediaFile
from medias.views import get_media_batch, get_existing_file_ids_for_month
from medias.utils import get_requests_async, create_media_request


class Command(BaseCommand):
    help = "Update MediaRequests for a single GLAM."

    def add_arguments(self, parser):
        parser.add_argument("pk", type=str)
        parser.add_argument("--start", type=str, default=None)
        parser.add_argument("--end", type=str, default=None)

    def handle(self, *args, **options):
        pk = options["pk"]
        start = options["start"]
        end = options["end"]

        try:
            glam = Glam.objects.get(pk=pk)
        except Glam.DoesNotExist:
            raise CommandError(f"GLAM with pk '{pk}' does not exist.")

        self.stdout.write(f"GLAM: {glam.name_pt}")

        t0 = perf_counter()
        asyncio.run(self.run_async(glam.pk, start, end))
        elapsed = perf_counter() - t0

        self.stdout.write(self.style.SUCCESS(
            f"\nDone in {elapsed:.1f}s ({elapsed/60:.1f} min)"
        ))

    async def run_async(self, pk, start, end):
        if not start:
            start = "2015010100"
        if not end:
            last_month = datetime.now().replace(day=1) - timedelta(days=1)
            end = last_month.strftime("%Y%m%d") + "00"

        self.stdout.write(f"Date range: {start} → {end}\n")

        glam = await sync_to_async(Glam.objects.get, thread_sensitive=True)(pk=pk)

        existing_ids = await sync_to_async(
            get_existing_file_ids_for_month, thread_sensitive=True
        )(glam, start, end)

        self.stdout.write(f"Already processed: {len(existing_ids)}")

        CONCURRENCY = 5
        CHUNK_SIZE = 100
        semaphore = asyncio.Semaphore(CONCURRENCY)

        headers = {
            "User-Agent": "GLAMWikiBrasil/1.0 (toolforge)"
        }

        timeout = aiohttp.ClientTimeout(total=60)
        connector = aiohttp.TCPConnector(limit=CONCURRENCY)

        async def fetch_with_retry(session, media, retries=3):
            for attempt in range(retries):
                try:
                    async with semaphore:
                        await asyncio.sleep(0.3)
                        return await get_requests_async(
                            session, media.file_path, start, end
                        )
                except Exception as e:
                    if attempt == retries - 1:
                        return e
                    await asyncio.sleep(2 ** attempt)

        offset = 0
        total_inserted = 0
        batch_counter = 0

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers
        ) as session:

            while True:
                # 🔑 refresh DB connection periodically
                if batch_counter % 5 == 0:
                    await sync_to_async(close_old_connections, thread_sensitive=True)()

                media_batch = await sync_to_async(
                    get_media_batch, thread_sensitive=True
                )(pk, existing_ids, offset, CHUNK_SIZE)

                if not media_batch:
                    break

                self.stdout.write(
                    f"Batch offset={offset} size={len(media_batch)}"
                )

                tasks = [
                    fetch_with_retry(session, media)
                    for media in media_batch
                ]

                results = await asyncio.gather(*tasks)

                valid = []
                errors = 0

                for media, result in zip(media_batch, results):
                    if isinstance(result, Exception):
                        errors += 1
                    else:
                        valid.append((media, result))

                if errors:
                    self.stdout.write(
                        self.style.WARNING(f"{errors} failed requests (will retry next run)")
                    )

                if valid:
                    await sync_to_async(
                        create_media_request,
                        thread_sensitive=True
                    )(valid)

                    total_inserted += len(valid)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Inserted {len(valid)} (total {total_inserted})"
                        )
                    )

                offset += CHUNK_SIZE
                batch_counter += 1

                # 🔑 small pause between batches (very important)
                await asyncio.sleep(1)

        self.stdout.write(
            self.style.SUCCESS(f"\nFinished. Total inserted: {total_inserted}")
        )