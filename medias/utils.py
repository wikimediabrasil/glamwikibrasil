import re
import requests
from io import BytesIO
from urllib.parse import unquote
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from xhtml2pdf import pisa
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import get_template

from medias.models import MediaFile, MediaUsage, MediaRequests
from .models import Glam



# ======================================================================================================================
# EXPLANATION
# ======================================================================================================================
# 1. Get category name
# 2. Get category members with information
# 3. Create MediaFile instance
# 4. Get MediaUsage
# 5. Get MediaRequests
# ======================================================================================================================

def url_to_category_name(url):
    return unquote(url.split("/wiki/")[-1]).replace("_", " ")


def clean_filename(filename):
    return filename.replace("File:", "")


def clean_url(url):
    return unquote(url.replace("https://upload.wikimedia.org", ""))


def clean_thumb(url, mime):
    if mime in ["video/webm", "video/ogg", "video/mpeg"]:
        decoded_url = unquote(url.replace("https://upload.wikimedia.org", ""))
        return re.sub(r'(/wikipedia/commons/)([^/]+/[^/]+/)([^/]+\.webm)',
                      r'\1thumb/\2\3/1920px--\3.jpg',
                      decoded_url)
    else:
        return clean_url(url)


def clean_date(date):
    return datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")


def clean_license(content):
    match = re.search(r"==\{\{int:license-header\}\}==\n(.*?)}}", content, re.DOTALL)
    if match:
        return match.group(1).strip() + "}}"
    else:
        return ""


COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"


def get_category_members(category):
    params = {
        "action": "query",
        "format": "json",
        "generator": "categorymembers",
        "gcmtype": "file",
        "gcmlimit": "max",
        "gcmtitle": category,
        "prop": "info|imageinfo|revisions",
        "iiprop": "timestamp|user|userid|url|mime",
        # "rvprop": "content",
        # "rvslots": "*"
    }

    all_results = {}

    while True:
        response = requests.get(COMMONS_API_URL, params=params)
        data = response.json()

        if "query" in data and "pages" in data["query"]:
            all_results.update(data["query"]["pages"])

        if "continue" in data and "gcmcontinue" in data["continue"]:
            params["gcmcontinue"] = data["continue"]["gcmcontinue"]
        else:
            break

    return all_results


def get_usage(filenames):
    params = {
        "action": "query",
        "format": "json",
        "prop": "globalusage",
        "guprop": "url|pageid|namespace",
        "gulimit": "max",
        "titles": f"File:{filenames}",
    }

    all_results = {}

    while True:
        response = requests.get(COMMONS_API_URL, params=params)
        data = response.json()

        if "query" in data and "pages" in data["query"]:
            all_results.update(data["query"]["pages"])

        if "continue" in data:
            params["gucontinue"] = data["continue"]["gucontinue"]
        else:
            break

    return all_results


def get_requests(file, start, end, referer="all-referers", agent="user", granularity="monthly"):
    if not start:
        start = "2015010100"
    if not end:
        last_month = datetime.now().replace(day=1)-timedelta(days=1)
        end = last_month.strftime("%Y%m%d") + "00"

    url = f"https://wikimedia.org/api/rest_v1/metrics/mediarequests/per-file/{referer}/{agent}/{file.file_path.replace('/','%2F')}/{granularity}/{start}/{end}"

    response = requests.get(url)
    data = response.json()

    if "items" in data:
        return data["items"]
    else:
        return []


def create_mediafile_instances(glam_id, dataset):
    glam = Glam.objects.get(pk=glam_id)

    for idx, data in dataset.items():
        # PROP
        page_id = data["pageid"]
        filename = clean_filename(data["title"])

        # IMAGEINFO
        iidata = data["imageinfo"][0]
        mime = iidata["mime"]
        file_path = clean_url(iidata["url"])
        thumb_path = clean_thumb(iidata["url"], mime)
        upload_date = clean_date(iidata["timestamp"])
        uploader = iidata["user"]
        extension = mime

        # REVISION
        # file_license = clean_license(data["revisions"][0]["slots"]["main"]["*"])

        exists = MediaFile.objects.filter(page_id=page_id).exists()
        if not exists:
            MediaFile.objects.create(
                page_id=page_id,
                filename=filename,
                file_path=file_path,
                thumb_path=thumb_path,
                upload_date=upload_date,
                uploader=uploader,
                extension=extension,
                glam=glam,
            )


def create_mediausage_instances(data):
    for page_id, global_usage in data.items():
        file = get_object_or_404(MediaFile, page_id=page_id)
        for gu_object in global_usage["globalusage"]:
            title = gu_object["title"]
            wiki = gu_object["wiki"]
            url = gu_object["url"]
            page_id = gu_object["pageid"]
            namespace = gu_object["ns"]

            exists = MediaUsage.objects.filter(file=file, page_id=page_id).exists()
            if not exists:
                MediaUsage.objects.create(file=file, title=title, wiki=wiki, url=url, page_id=page_id, namespace=namespace)


def create_mediarequest(file_id, data):
    file = get_object_or_404(MediaFile, pk=file_id)
    for item in data:
        exists = MediaRequests.objects.filter(file=file,
                                              referer=item["referer"],
                                              granularity=item["granularity"],
                                              timestamp=item["timestamp"],
                                              agent=item["agent"]).exists()
        if not exists:
            MediaRequests.objects.create(
                file=file,
                referer=item["referer"],
                granularity=item["granularity"],
                timestamp=item["timestamp"],
                agent=item["agent"],
                requests=item["requests"],
            )


def render_to_pdf(template_src, context_dict=None):
    if context_dict is None:
        context_dict = {}
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("utf-8")), result)
    if pdf.err:
        return HttpResponse("Invalid PDF", status_code=400, content_type='text/plain')
    return HttpResponse(result.getvalue(), content_type='application/pdf')
