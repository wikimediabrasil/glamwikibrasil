import json

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.db.models import Sum

from medias.models import MediaRequests, MediaFile, MediaUsage
from .models import Institution, Glam
from .forms import InstitutionForm, GlamForm


# ======================================================================================================================
# INSTITUTIONAL PAGES
# ======================================================================================================================
def index(request):
    return render(request, "glams/index.html")


# ======================================================================================================================
# CREATE
# ======================================================================================================================
@permission_required("glams.add_institution")
def institution_create(request):
    if request.method == "POST":
        form = InstitutionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(reverse("glams:institution_list"))
    else:
        form = InstitutionForm()
    return render(request, "glams/institution_create.html", {"form": form})  # fixed "orm" → "form"


@permission_required("glams.add_glam")
def glam_create(request):
    if request.method == "POST":
        form = GlamForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(reverse("glams:glam_list"))
    else:
        form = GlamForm()
    return render(request, "glams/glam_create.html", {"form": form})


# ======================================================================================================================
# RETRIEVE
# ======================================================================================================================
def institution_list(request):
    items = Institution.objects.prefetch_related("institution_glams").order_by("name_pt")
    return render(request, "glams/institution_list.html", {"items": items})


def institution_detail(request, pk):
    institution = get_object_or_404(Institution.objects.prefetch_related("institution_glams"), pk=pk)
    return render(request, "glams/institution_detail.html", {"item": institution})


def glam_list(request):
    items = Glam.objects.prefetch_related("institutions").all()
    return render(request, "glams/glam_list.html", {"items": items})


def glam_detail(request, pk):
    glam = get_object_or_404(Glam.objects.prefetch_related("institutions"), pk=pk)

    # Evaluated once into a list — reused for chart_data, total_views, and timestamp_options
    media_requests = list(
        MediaRequests.objects
        .filter(file__glam=glam)
        .order_by("timestamp")
        .values("timestamp")
        .annotate(total=Sum("requests"))
    )

    chart_data = [
        {"timestamp": item["timestamp"].isoformat(), "total": item["total"]}
        for item in media_requests
    ]
    total_views = sum(item["total"] for item in media_requests)
    timestamp_options = sorted([item["timestamp"] for item in media_requests], reverse=True)

    media_files = MediaFile.objects.filter(glam=glam).count()
    total_projects = MediaUsage.objects.filter(file__glam=glam).values("wiki").distinct().count()

    context = {
        "item": glam,
        "chart_data": json.dumps(chart_data),
        "timestamp_options": timestamp_options,
        "media_files": media_files,
        "total_views": total_views,
        "total_projects": total_projects,
    }

    return render(request, "glams/glam_detail.html", context)


# ======================================================================================================================
# UPDATE
# ======================================================================================================================
@permission_required("glams.change_institution")
def institution_update(request, pk):
    institution = get_object_or_404(Institution, pk=pk)
    if request.method == "POST":
        form = InstitutionForm(request.POST, instance=institution)
        if form.is_valid():
            form.save()
            return redirect(reverse("glams:institution_list"))
    else:
        form = InstitutionForm(instance=institution)
    return render(request, "glams/institution_update.html", {"form": form})


@permission_required("glams.change_glam")
def glam_update(request, pk):
    glam = get_object_or_404(Glam, pk=pk)
    if request.method == "POST":
        form = GlamForm(request.POST, instance=glam)
        if form.is_valid():
            form.save()
            return redirect(reverse("glams:glam_list"))
    else:
        form = GlamForm(instance=glam)
    return render(request, "glams/glam_update.html", {"form": form})


# ======================================================================================================================
# DELETE
# ======================================================================================================================
@permission_required("glams.delete_institution")
def institution_delete(request, pk):
    institution = get_object_or_404(Institution, pk=pk)
    if request.method == "POST":
        institution.delete()
        return redirect(reverse("glams:institution_list"))
    return render(request, "glams/institution_delete.html", {"item": institution})


@permission_required("glams.delete_glam")
def glam_delete(request, pk):
    glam = get_object_or_404(Glam, pk=pk)
    if request.method == "POST":
        glam.delete()
        return redirect(reverse("glams:glam_list"))
    return render(request, "glams/glam_delete.html", {"item": glam})
