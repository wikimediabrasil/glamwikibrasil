import calendar
import aiohttp
import asyncio
from math import floor
from dateutil.relativedelta import relativedelta
from asgiref.sync import sync_to_async
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import permission_required
from django.shortcuts import render, redirect, reverse
from django.db.models import Count, Sum
from more_itertools import chunked
from .utils import *



# ======================================================================================================================
# UPDATE DATABASE
# ======================================================================================================================
def all_glams_report(request):
    user = request.user
    glams = Glam.objects.all()
    glam_requests = {}
    for glam in glams:
        total_requests = MediaRequests.objects.filter(file__glam=glam).aggregate(total=Sum("requests"))["total"] or 0
        total_files = MediaFile.objects.filter(glam=glam).count()
        usage = MediaUsage.objects.filter(file__glam=glam, namespace=0)
        total_usage_page = usage.values_list("page_id", flat=True).distinct().count()
        total_usage_wiki = usage.values_list("wiki", flat=True).distinct().count()
        glam_requests[glam.name_pt] = {"glam": glam, "total": total_requests, "files": total_files, "usage": total_usage_page, "wiki": total_usage_wiki}

    sorted_glam_requests = dict(sorted(glam_requests.items(), key=lambda item: item[1]["total"], reverse=True))
    context = {"chart_data": sorted_glam_requests, "user": user}

    return render(request, 'glams/all_glams.html', context)


def top_files_report(request):
    user = request.user
    most_viewed = MediaRequests.objects.all().values("file",
                                                     "file__filename",
                                                     "file__glam__name_pt",
                                                     "file__glam__wikidata").annotate(total_requests=Sum("requests")).order_by("-total_requests")[:100]

    context = {"dataset": most_viewed, "user": user}

    return render(request, 'glams/top_files.html', context)

# ======================================================================================================================
# UPDATE DATABASE
# ======================================================================================================================
@permission_required('medias.add_mediafile')
def update_glam_mediafiles(request, pk):
    glam = get_object_or_404(Glam, pk=pk)
    category_members = get_category_members(url_to_category_name(glam.category_url))
    create_mediafile_instances(pk, category_members)

    return redirect(reverse("glams:glam_detail", kwargs={"pk": pk}))


def update_all_glams_from_start(request, start, end):
    glams = Glam.objects.all()
    for glam in glams:
        asyncio.run(update_glam_async(glam.pk, start=start, end=end))
        print(f"{glam.name_pt} was updated at {datetime.now()}")
    return redirect(reverse("glams:glam_list"))


@permission_required('medias.add_mediarequests')
def update_glam_mediafiles_requests(request, pk, start=None, end=None):
    asyncio.run(update_glam_async(pk, start, end))
    return redirect(reverse("glams:glam_detail", kwargs={"pk": pk}))


async def update_glam_async(pk, start, end):
    glam = await sync_to_async(Glam.objects.get)(pk=pk)
    medias = await sync_to_async(list)(MediaFile.objects.filter(glam=glam))

    if not start:
        start = "2015010100"
    if not end:
        last_month = datetime.now().replace(day=1)-timedelta(days=1)
        end = last_month.strftime("%Y%m%d") + "00"

    async with aiohttp.ClientSession() as session:
        i=0
        for media_batch in chunked(medias, 1000):
            tasks = [get_requests_async(session, media.file_path, start, end) for media in media_batch]
            responses = await asyncio.gather(*tasks)
            all_data = list(zip(media_batch, responses))
            await sync_to_async(create_media_request)(all_data)
            print(i)
            i=i+1


async def process_media(session, media, start, end):
    data = await get_requests_async(session, media.file_path, start, end)
    await sync_to_async(create_media_request)(media.pk, data)


@permission_required('medias.add_mediausage')
def update_glam_mediafiles_usage(request, pk):
    glam = get_object_or_404(Glam, pk=pk)
    medias = MediaFile.objects.filter(glam=glam).iterator()

    for batch in chunked(medias, 50):
        filenames = [media.filename for media in batch]
        media_usage = get_usage("|File:".join(filenames))
        create_mediausage_instances(media_usage)

    return redirect(reverse("glams:glam_detail", kwargs={"pk": pk}))


# ======================================================================================================================
# GENERATE REPORT
# ======================================================================================================================
def return_report(request, pk):
    timestamp = request.POST.get('timestamp')
    return redirect(reverse("medias:glam_report_for_month", kwargs={"pk": pk, "timestamp": timestamp}))


def return_report_for_month(request, pk, timestamp):
    glam, _files, _views, _avg_views, _avg_views_year, _most_viewed, _articles, _wikis, usage, _requests, _n_days = extract_numbers_from_db(pk, timestamp)

    context = {
        "files": _files,
        "views": _views,
        "avg_views": _avg_views,
        "avg_views_year": _avg_views_year,
        "most_viewed": _most_viewed,
        "articles": _articles,
        "wikis": _wikis,
        "glam": glam,
        "timestamp": datetime.strptime(timestamp, "%Y%m%d%H"),
        "usage": list(usage.values('wiki').annotate(total=Count('id')).order_by('-total'))[:10],
        "request_data": list(_requests.order_by("timestamp").values("timestamp").annotate(total=Sum("requests"))),
        "n_days": _n_days
    }
    pdf, file_paths = render_to_pdf(context)
    file = pdf.output(dest='S').encode('latin-1')
    delete_images(file_paths)
    response = HttpResponse(file, content_type='application/pdf')
    content_disposition = 'inline; filename=f"{glam.name_pt} - {timestamp}.pdf"'
    response['Content-Disposition'] = content_disposition
    return response


def get_views_for_year_until_month(glam, timestamp):
    months = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"]
    year = int(timestamp[:4])
    month = timestamp[4:6]
    timestamps = [f"{year}{month_x}0100" for month_x in months[:months.index(month)+1]]
    media_requests_objects = MediaRequests.objects.filter(file__glam=glam, timestamp__in=timestamps)
    media_requests = media_requests_objects.values_list('requests', flat=True)
    n_months = int(month)

    return sum(media_requests), n_months


def extract_numbers_from_db(pk, timestamp):
    year = int(timestamp[:4])
    month = int(timestamp[4:6])
    n_days = calendar.monthrange(year, month)[1]
    glam = get_object_or_404(Glam, pk=pk)

    media_requests_objects = MediaRequests.objects.filter(file__glam=glam, timestamp=timestamp)
    media_requests_objects_historical = MediaRequests.objects.filter(file__glam=glam, timestamp__lte=timestamp)
    media_requests = media_requests_objects.values_list('requests', flat=True)
    usage = MediaUsage.objects.filter(file__glam=glam, namespace="0")
    total_views_for_the_year_until_now, n_months = get_views_for_year_until_month(glam, timestamp)

    date_timestamp = datetime.strptime(timestamp, "%Y%m%d%H") + relativedelta(months=1)
    total_media_files = MediaFile.objects.filter(glam=glam, upload_date__lte=date_timestamp).count()
    total_views = sum(media_requests)
    average_views = floor(total_views / n_days)
    average_views_year = floor(total_views_for_the_year_until_now / n_months)
    most_viewed = media_requests_objects.order_by('-requests')[:3]
    usage_articles = usage.values("page_id", "wiki").values_list("page_id", flat=True).distinct().count()
    usage_wikis = usage.values("page_id", "wiki").values_list("wiki", flat=True).distinct().count()

    return glam, total_media_files, total_views, average_views, average_views_year, most_viewed, usage_articles, usage_wikis, usage, media_requests_objects_historical, n_days


def get_index_counter_data(request):
    return JsonResponse({
        "total_requests": MediaRequests.objects.aggregate(total=Sum("requests"))["total"] or 0,
        "total_files": MediaFile.objects.count() or 0,
        "total_glams": Glam.objects.count() or 0
    })
