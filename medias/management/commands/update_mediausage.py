from time import perf_counter
from more_itertools import chunked
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from glams.models import Glam
from medias.models import MediaFile
from medias.utils import get_usage, create_mediausage_instances


class Command(BaseCommand):
    help = "Update MediaUsage for one or all GLAMs (processes all files)."

    def add_arguments(self, parser):
        parser.add_argument("pk", type=str, nargs="?", default=None, help="Wikidata ID of a single GLAM (optional)")
        parser.add_argument("--batch-size", type=int, default=50, help="Files per API call (default: 50)")

    def handle(self, *args, **options):
        pk = options["pk"]
        batch_size = options["batch_size"]

        if pk:
            try:
                glams = [Glam.objects.get(pk=pk)]
            except Glam.DoesNotExist:
                raise CommandError(f"GLAM '{pk}' does not exist.")
        else:
            glams = list(Glam.objects.order_by("name_pt"))

        total_glams = len(glams)
        t_total = perf_counter()
        errors = []

        self.stdout.write(f"\nUpdating mediausage for {total_glams} GLAM(s)")
        self.stdout.write("=" * 60)

        for i, glam in enumerate(glams, 1):
            connection.close()
            try:
                medias = list(MediaFile.objects.filter(glam=glam))
                total_files = len(medias)
                processed = 0

                for batch in chunked(medias, batch_size):
                    filenames = [media.filename for media in batch]
                    media_usage = get_usage("|File:".join(filenames))
                    create_mediausage_instances(media_usage)
                    processed += len(batch)

                self.stdout.write(f"[{i}/{total_glams}] {glam.name_pt}: {processed}/{total_files} files processed")
            except Exception as e:
                msg = f"[{i}/{total_glams}] [ERROR] {glam.name_pt} ({glam.pk}): {e}"
                self.stdout.write(self.style.ERROR(msg))
                errors.append(msg)

        elapsed = perf_counter() - t_total
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS(f"Done in {elapsed:.1f}s ({elapsed / 60:.1f} min)"))
        if errors:
            self.stdout.write(self.style.ERROR(f"\n{len(errors)} error(s):"))
            for err in errors:
                self.stdout.write(self.style.ERROR(f"  {err}"))