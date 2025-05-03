import re
import os
import numpy as np
import requests
import unicodedata
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd

from matplotlib.ticker import MaxNLocator
from pathlib import Path
from PIL import Image
from urllib.parse import unquote, quote
from fpdf import FPDF
from datetime import datetime, timedelta
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils.formats import localize, date_format
from django.db.models import Q
from django.utils import formats

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


async def get_requests_async(session, file_path, start, end, referer="all-referers", agent="user", granularity="monthly"):
    url = f"https://wikimedia.org/api/rest_v1/metrics/mediarequests/per-file/{referer}/{agent}/{file_path.replace('/','%2F')}/{granularity}/{start}/{end}"
    async with session.get(url) as response:
        data = await response.json()
        return data.get("items", [])


def create_mediafile_instances(glam_id, dataset):
    glam = Glam.objects.get(pk=glam_id)

    existing_ids = set(MediaFile.objects.filter(page_id__in=[data["pageid"] for data in dataset.values()]).values_list("page_id",flat=True))

    filtered_dataset = { page_id: data for page_id, data in dataset.items() if page_id not in existing_ids }

    new_instances = []
    for page_id, data in filtered_dataset.items():
        # PROP
        filename = clean_filename(data["title"])

        # IMAGE INFO
        iidata = data["imageinfo"][0]
        mime = iidata["mime"]
        file_path = clean_url(iidata["url"])
        thumb_path = clean_thumb(iidata["url"], mime)
        upload_date = clean_date(iidata["timestamp"])
        uploader = iidata["user"]
        extension = mime

        new_instances.append(MediaFile(
            page_id=page_id,
            filename=filename,
            file_path=file_path,
            thumb_path=thumb_path,
            upload_date=upload_date,
            uploader=uploader,
            extension=extension,
            glam=glam,
        ))

    MediaFile.objects.bulk_create(new_instances, batch_size=1000)


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


def create_media_request(media_data_list):
    new_instances = []
    for file, data in media_data_list:
        incoming_items = { (item["referer"], item["granularity"], item["timestamp"], item["agent"]): item for item in data }

        existing_keys = set(MediaRequests.objects.filter(file=file).filter(
            Q(*[Q(referer=ref, granularity=gran, timestamp=ts, agent=ag) for (ref, gran, ts, ag) in incoming_items.keys()],
              _connector=Q.OR)).values_list("referer", "granularity", "timestamp", "agent"))

        new_instances.extend([MediaRequests(file=file, referer=ref, granularity=gran, timestamp=ts, agent=ag,
                                            requests=incoming_items[(ref, gran, ts, ag)]["requests"]) for
                              (ref, gran, ts, ag) in incoming_items.keys() if (ref, gran, ts, ag) not in existing_keys])

    if new_instances:
        MediaRequests.objects.bulk_create(new_instances, batch_size=1000)

class PDF(FPDF):
    def __init__(self, glam, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.glam = glam

    def header(self):
        pass

    def footer(self):
        self.set_xy(30,-35)
        self.set_font("M-REGULAR", "", 9)
        self.set_text_color(0, 0, 0)
        self.multi_cell(w=160, h=3, txt=str(_("All data is based on the files of this GLAM-Wiki partnership available at Wikimedia Commons. The data shows a monthly up-to-date snapshot of the usage and views of the files during the selected month, through a variety of metrics.")), align='L')
        self.cell(w=0, h=3, ln=1, txt="", align="L")
        self.set_x(30)
        w = self.get_string_width(str(_("Sources: ")))
        self.cell(w=w, h=3, ln=0, txt=str(_("Sources: ")), align="L")
        w = self.get_string_width(str(_("MediaWiki API")))
        self.set_text_color(0, 84, 179)
        self.cell(w=w, h=3, ln=0, txt=str(_("MediaWiki API")), align="L", link="https://www.mediawiki.org/wiki/API:Main_page")
        self.set_text_color(0, 0, 0)
        self.cell(w=2.5, h=3, ln=0, txt=str(_(" | ")), align="L")
        self.set_text_color(0, 84, 179)
        w = self.get_string_width(str(_("Core REST API")))
        self.cell(w=w, h=3, ln=1, txt=str(_("Core REST API")), align="L", link="https://api.wikimedia.org/wiki/Core_REST_API")
        self.set_text_color(0, 0, 0)
        self.set_x(30)
        w = self.get_string_width(str(_("Contact: ")))
        self.cell(w=w, h=3, ln=0, txt=str(_("Contact: ")), align="L")
        self.set_text_color(0, 84, 179)
        self.cell(w=0, h=3, ln=1, txt=str(_("cultura@wmnobrasil.org")), align="L",link="mailto:cultura@wmnobrasil.org")
        self.set_text_color(0, 0, 0)
        self.set_x(30)
        w = self.get_string_width(str(_("See more at ")))
        self.cell(w=w, h=3, ln=0, txt=str(_("See more at ")), align="L")
        self.set_text_color(0, 84, 179)
        self.cell(w=0, h=3, ln=1, txt=str(_("https://glamwikibrasil.toolforge.org/glams/%(glam_id)s") % {"glam_id": self.glam.wikidata}), align="L", link=f"https://glamwikibrasil.toolforge.org/glams/{self.glam.wikidata}")


def add_text(pdf, color, w, h, ln, txt, align, font_family, size, x=None, y=None, multi_cel=False, link=None):
    x_ = x if x else pdf.get_x()
    y_ = y if y else pdf.get_y()
    pdf.set_xy(x_, y_)
    if color:
        r,g,b = color
        pdf.set_text_color(r,g,b)
    if font_family and size:
        pdf.set_font(font_family, "", size)
    if w and h and ln>=0 and txt and align:
        if multi_cel:
            pdf.multi_cell(w=w, h=h, txt=str(txt), align=align)
        else:
            if link:
                pdf.cell(w=w, h=h, ln=ln, txt=str(txt), align=align, link=link)
            else:
                pdf.cell(w=w, h=h, ln=ln, txt=str(txt), align=align)


def section_title(pdf, txt, w, x=None, y=None):
    add_text(pdf, (0, 0, 0), w, 5.5, 2, txt, "C", "M-BOLD", 12, x, y)


def section_value(pdf, txt, w, x=None, y=None):
    add_text(pdf, (0, 84, 179), w, 25, 2, localize(txt), "C", "M-BOLD", 36, x, y+6)


def section_tooltip(pdf, txt, w, x=None, y=None):
    add_text(pdf, (0, 0, 0), w, 3, 2, txt, "C", "M-REGULAR", 9, x, y + 29, True)


def section_title_2(pdf, txt, link, w, x=None, y=None):
    add_text(pdf, (0, 84, 179), w, 5.5, 2, txt, "L", "M-BOLD", 15, x, y, False, link)


def section_value_2(pdf, txt, w, x=None, y=None):
    add_text(pdf, (0, 84, 179), w, 5.5, 0, localize(txt), "L", "M-BOLD", 24, x, y)


def section_value_complement_2(pdf, txt, w, x=None, y=None):
    add_text(pdf, (0, 0, 0), w, 5.5, 2, txt, "L", "M-REGULAR", 12, x, y)


def insert_image(pdf, thumb, filename, y, files):
    try:
        local_file_path = os.path.join(settings.MEDIA_ROOT, "temp", simple_slugify(thumb))
        base_path, ext = os.path.splitext(local_file_path)
        lower_ext = ext.lower()

        specific_formats = [".tiff", ".tif"]
        allowed_formats = [".png", ".jpg", ".jpeg"]
        toggle_delete_images = True

        if lower_ext not in allowed_formats and lower_ext not in specific_formats:
            toggle_delete_images = False
            local_file_path = os.path.join(settings.BASE_DIR, "static", "images", "no_image.png")
        else:
            if lower_ext in specific_formats:
                url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename}?width=200"
                local_file_path = base_path + ".jpg"
            else:
                url = f"https://commons.wikimedia.org/w/thumb.php?f={filename}&w=200"

            response = requests.get(url)

            with open(local_file_path, "wb") as f:
                f.write(response.content)

        img = Image.open(local_file_path).convert("RGB")

        orig_w, orig_h = img.size
        target_ratio = 60 / 53
        image_ratio = orig_w / orig_h

        if image_ratio > target_ratio:
            new_width = int(orig_h * image_ratio)
            left = (orig_w - new_width) / 2
            right = left + new_width
            top = 0
            bottom = orig_h
        else:
            new_height = int(orig_w / target_ratio)
            left = 0
            right = orig_w
            top = (orig_h - new_height) / 2
            bottom = top + new_height

        cropped = img.crop((left, top, right, bottom))
        cropped.save(local_file_path)

        pdf.image(local_file_path, x=0, y=y, w=60, h=53)

        if toggle_delete_images:
            files.append(local_file_path)
    except:
        pass


def delete_images(files):
    for path_str in files:
        path = Path(path_str)
        try:
            path.unlink()
        except:
            pass


def generate_usage_chart(data, filename, files):
    matplotlib.use("Agg")

    labels = [item["wiki"] for item in data]
    totals = [item["total"] for item in data]

    fig, ax = plt.subplots(figsize=(16*0.393701, 7.3*0.393701))

    bars = ax.barh(labels, totals, color="#0054b3")
    ax.bar_label(bars, fmt='%d', padding=3)
    ax.set_xlabel(str(_("Number of medias used")))
    ax.set_ylabel(str(_("Wiki")))
    ax.set_title(str(_("Number of medias used per wiki")))
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))

    ax.set_xlim(0, max(totals) * 1.1)
    ax.invert_yaxis()

    plt.tight_layout()
    plt.savefig(filename, format="png", dpi=150)
    plt.close(fig)
    files.append(filename)


def generate_views_timeline(data, filename, files):
    df = pd.DataFrame(data)

    df["timestamp"] = pd.to_datetime(df["timestamp"], format="%Y%m%d%H")
    df["year_month"] = df["timestamp"].dt.strftime("%Y-%m")
    df['cumulative'] = df['total'].cumsum()

    num_ticks = 12
    tick_indices = np.linspace(0, len(df) - 1, num=num_ticks, dtype=int)
    tick_labels = df['year_month'].iloc[tick_indices]

    fig, ax1 = plt.subplots(figsize=(16 * 0.393701, 12 * 0.393701))

    ax1.fill_between(df["year_month"], df["total"], color="#0054b3", alpha=0.5, label=_("Monthly views"))
    ax1.set_ylabel(str(_("Monthly views")))
    ax1.tick_params(axis='y')

    ax2 = ax1.twinx()
    ax2.plot(df['year_month'], df['cumulative'], color='#EA5B0C', label=_("Cumulative views"), linewidth=2)
    ax2.set_ylabel(str(_("Cumulative views")))
    ax2.tick_params(axis='y')

    ax1.set_xlabel(str(_("Date")))
    ax1.set_title(str(_("Number of views per month")))
    ax1.xaxis.set_major_locator(MaxNLocator(nbins=len(df["year_month"])))
    ax1.yaxis.set_major_formatter(ticker.FuncFormatter(localized_format))
    ax2.yaxis.set_major_formatter(ticker.FuncFormatter(localized_format))
    ax1.set_xticks(tick_indices)
    ax1.set_xticklabels(tick_labels, rotation=90)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()

    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper center', bbox_to_anchor=(0.5, -0.5), ncol=2, frameon=False)
    plt.xticks(rotation=90)
    ax1.grid(True, linewidth=0.5, zorder=0)
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.5)
    plt.savefig(filename, format="png", dpi=150)
    plt.close(fig)

    files.append(filename)


def localized_format(x, pos=None):
    return localize(int(x))


def simple_slugify(text):
    base, ext = os.path.splitext(text)
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^\w\s-]", "", base).strip().lower()
    base = re.sub(r"[-\s]+", "-", base)
    return base + ext.lower()


def render_to_pdf(context):
    pdf = PDF(orientation='P', unit="mm", format="A4", glam=context["glam"])
    pdf.add_font('M-BLACK', '', os.path.join(settings.BASE_DIR, 'static/fonts/Montserrat-Black.ttf'), uni=True)
    pdf.add_font('M-BOLD', '', os.path.join(settings.BASE_DIR, 'static/fonts/Montserrat-Bold.ttf'), uni=True)
    pdf.add_font('M-REGULAR', '', os.path.join(settings.BASE_DIR, 'static/fonts/Montserrat-Regular.ttf'), uni=True)

    ####################################################################################################################
    # FIRST PAGE
    ####################################################################################################################
    pdf.add_page()
    pdf.set_fill_color(0, 84, 179)
    pdf.rect(0, 0, 210, 64, "F")
    pdf.set_fill_color(241, 241, 241)
    pdf.rect(0, 74, 210, 53, "F")
    pdf.rect(0, 200, 210, 53, "F")

    pdf.image(str(os.path.join(settings.BASE_DIR, "static", "images", "white_logo.png")), x=87.5, y=10, w=45)

    title_phrase = context["glam"].name_pt
    date_phrase = formats.date_format(context["timestamp"], "F/Y", use_l10n=True)

    add_text(pdf, (255, 255, 255), 160, 10, 2, title_phrase, "C", "M-BLACK", 24, 30, 33, multi_cel=True)
    add_text(pdf, (255, 255, 255), 160, 8.5, 2, date_phrase, "C", "M-BLACK", 20, 30)

    xe, xd, y, w = 30, 115, 79, 75

    # Number of total files
    section_title(pdf, _("Total number of files"), w, xe, y)
    section_value(pdf, localize(context["files"]), w, xe, y)
    section_tooltip(pdf, _("This figure shows the total media files uploaded to the main category of this institution in Wikimedia Commons, by the end of the selected month."), w, xe, y)

    # Number of total views
    section_title(pdf, _("Total views for the month"), w, xd, y)
    section_value(pdf, localize(context["views"]), w, xd, y)
    section_tooltip(pdf, _("This figure shows the sum of all views throughout the chosen month, for this partnership's main category on Wikimedia Commons."), w, xd, y)

    y += 63

    # Average daily views
    section_title(pdf, _("Average daily views"), w, xe, y)
    section_value(pdf, localize(context["avg_views"]), w, xe, y)
    section_tooltip(pdf, _("This figure shows the average views per day for this month."), w, xe, y)

    # Year average monthly views
    section_title(pdf, _("Average monthly views"), w, xd, y)
    section_value(pdf, localize(context["avg_views_year"]), w, xd, y)
    section_tooltip(pdf, _("This figure shows the average views per month for this year, up until this month."), w, xd, y)

    y += 63

    # Number of articles
    section_title(pdf, _("Number of articles"), w, xe, y)
    section_value(pdf, localize(context["articles"]), w, xe, y)
    section_tooltip(pdf, _("This figure shows how many Wiki pages use files from this GLAM-Wiki partnership."), w, xe, y)

    # Number of projects
    section_title(pdf, _("Number of projects"), w, xd, y)
    section_value(pdf, localize(context["wikis"]), w, xd, y)
    section_tooltip(pdf, _("This figure shows how many distinct Wikimedia projects use files from this GLAM-Wiki partnership."), w, xd, y)

    ####################################################################################################################
    # SECOND PAGE
    ####################################################################################################################
    pdf.add_page()

    pdf.set_fill_color(241, 241, 241)
    pdf.rect(0, 74, 210, 53, "F")
    pdf.rect(0, 200, 210, 53, "F")

    add_text(pdf, (0, 84, 179), 160, 10, 2, _("Most viewed medias"), "C", "M-BLACK", 24, 30, 33)
    add_text(pdf, (0, 84, 179), 160, 8.5, 2, date_phrase, "C", "M-BLACK", 20, 30)

    xe, xd, y, w = 0, 70, 79, 120

    # Most viewed files
    files = []
    n_days = context["n_days"]

    for file_obj in context["most_viewed"]:
        file_requests = file_obj.requests
        filename = f"{file_obj.file.filename}"
        filename_string = filename[:32]+"..." if len(filename) > 35 else filename
        file_thumb = file_obj.file.thumb_path
        file_link = f"https://commons.wikimedia.org/wiki/File:{quote(filename.replace(' ', '_'))}"
        insert_image(pdf, file_thumb, filename, y - 5, files)

        pdf.set_font("M-BOLD", "", 24)
        most_viewed = f"{localize(file_requests)}"
        most_viewed_len = pdf.get_string_width(most_viewed)
        avg_viewership = f"{localize(int(file_requests / n_days))}"
        avg_viewership_len = pdf.get_string_width(avg_viewership)

        section_title_2(pdf, filename_string, file_link, w, xd, y)
        section_value_2(pdf, most_viewed, most_viewed_len, xd, y + 16)
        section_value_complement_2(pdf, _(" views this month"), w-most_viewed_len)
        section_value_2(pdf, avg_viewership, avg_viewership_len, xd, y + 27)
        section_value_complement_2(pdf, _(" views per day in average"), w - avg_viewership_len)
        section_value_complement_2(pdf, _("Uploaded at %(upload_date)s") % {"upload_date": date_format(file_obj.file.upload_date, format='DATETIME_FORMAT', use_l10n=True)}, w, xd, y + 38)

        y += 63

    ####################################################################################################################
    # THIRD PAGE
    ####################################################################################################################
    pdf.add_page()
    usage_data = context["usage"]
    usage_filename = os.path.join(settings.MEDIA_ROOT, "temp", simple_slugify("usage " + title_phrase + " " + str(context["timestamp"])) + ".png")
    requests_data = context["request_data"]
    requests_filename = os.path.join(settings.MEDIA_ROOT, "temp", simple_slugify("requests " + title_phrase + " " + str(context["timestamp"])) + ".png")

    add_text(pdf, (0, 84, 179), 160, 10, 2, _("Usage and views"), "C", "M-BLACK", 24, 30, 33)

    x, yt, yb, w = 30, 74, 157, 160

    generate_usage_chart(usage_data, usage_filename, files)
    generate_views_timeline(requests_data, requests_filename, files)
    pdf.image(str(usage_filename), x=x, y=yt, w=w, h=73)
    pdf.image(str(requests_filename), x=x, y=yb, w=w, h=120)

    return pdf, files