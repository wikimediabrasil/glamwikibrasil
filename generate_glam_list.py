#!/usr/bin/env python
import sys
import os
import json

sys.path.insert(0, '/data/project/glamwikibrasil/www/python/src')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "glamwikibrasil.settings")

import django
django.setup()

from glams.models import Glam
from django.db.models import Count

OUTPUT_FILE = '/data/project/glamwikibrasil/logs/glam_list.txt'

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

with open(OUTPUT_FILE, 'w') as f:
    for g in Glam.objects.annotate(n=Count('mediafile')).order_by('-n'):
        f.write(f"{g.pk} {g.n}\n")

print(f"Written {OUTPUT_FILE}")