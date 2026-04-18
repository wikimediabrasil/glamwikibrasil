from time import perf_counter
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from glams.models import Glam
from medias.models import MediaFile
from medias.utils import get_category_members, url_to_category_name, create_mediafile_instances


class Command(BaseCommand):
    help = "Update MediaFiles for one or all GLAMs."

    def add_arguments(self, parser):
        parser.add_argument("pk", type=str, nargs="?", default=None, help="Wikidata ID of a single GLAM (optional)")

    def handle(self, *args, **options):
        pk = options["pk"]
        glams = [Glam.objects.get(pk=pk)] if pk else list(Glam.objects.order_by("name_pt"))

        if pk:
            try:
                glams = [Glam.objects.get(pk=pk)]
            except Glam.DoesNotExist:
                raise CommandError(f"GLAM '{pk}' does not exist.")
        else:
            glams = list(Glam.objects.order_by("name_pt"))

        total_glams = len(glams)
        t_total = perf_counter()
        total_new = 0
        errors = []

        self.stdout.write(f"\nUpdating mediafiles for {total_glams} GLAM(s)")
        self.stdout.write("=" * 60)

        for i, glam in enumerate(glams, 1):
            connection.close()
            try:
                before = MediaFile.objects.filter(glam=glam).count()
                category_members = get_category_members(url_to_category_name(glam.category_url))
                create_mediafile_instances(glam.pk, category_members)
                after = MediaFile.objects.filter(glam=glam).count()
                new_files = after - before
                total_new += new_files
                self.stdout.write(f"[{i}/{total_glams}] {glam.name_pt}: {after} total, +{new_files} new")
            except Exception as e:
                msg = f"[{i}/{total_glams}] [ERROR] {glam.name_pt} ({glam.pk}): {e}"
                self.stdout.write(self.style.ERROR(msg))
                errors.append(msg)

        elapsed = perf_counter() - t_total
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS(f"Done in {elapsed:.1f}s | +{total_new} new files"))
        if errors:
            self.stdout.write(self.style.ERROR(f"\n{len(errors)} error(s):"))
            for err in errors:
                self.stdout.write(self.style.ERROR(f"  {err}"))
