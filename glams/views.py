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
    total_requests = MediaRequests.objects.aggregate(total=Sum("requests"))["total"] or 0
    total_files = MediaFile.objects.count() or 0
    total_glams = Glam.objects.count() or 0

    context = {"total_requests": total_requests, "total_files": total_files, "total_glams": total_glams}
    return render(request, "glams/index.html", context=context)

"""
12,users,user
"""

# ======================================================================================================================
# CREATE
# ======================================================================================================================
@permission_required('glams.add_institution')
def institution_create(request):
    if request.method == 'POST':
        form = InstitutionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(reverse('glams:institution_list'))
    else:
        form = InstitutionForm()
    return render(request, 'glams/institution_create.html', {'form': form})

@permission_required('glams.add_glam')
def glam_create(request):
    if request.method == 'POST':
        form = GlamForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(reverse('glams:glam_list'))
    else:
        form = GlamForm()
    return render(request, 'glams/glam_create.html', {'form': form})

# ======================================================================================================================
# RETRIEVE
# ======================================================================================================================
@permission_required('glams.view_institution')
def institution_list(request):
    items = Institution.objects.all()
    return render(request, 'glams/institution_list.html', {'items': items})


@permission_required('glams.view_institution')
def institution_detail(request, pk):
    institution = get_object_or_404(Institution, pk=pk)
    return render(request, 'glams/institution_detail.html', {'item': institution})


@permission_required('glams.view_glam')
def glam_list(request):
    items = Glam.objects.all()
    return render(request, 'glams/glam_list.html', {'items': items})


@permission_required('glams.view_glam')
def glam_detail(request, pk):
    glam = get_object_or_404(Glam, pk=pk)
    media_requests = MediaRequests.objects.filter(file__glam=glam).order_by("timestamp").values("timestamp").annotate(total=Sum("requests"))
    media_files = MediaFile.objects.filter(glam=glam).count()
    total_views = sum(item["total"] for item in media_requests)
    total_projects = MediaUsage.objects.filter(file__glam=glam).values("wiki").distinct().count()
    timestamp_options = list(media_requests.values_list("timestamp", flat=True).order_by("-timestamp"))

    context = {
        "item": glam,
        "chart_data": list(media_requests),
        "timestamp_options": timestamp_options,
        "media_files": media_files,
        "total_views": total_views,
        "total_projects": total_projects
    }

    return render(request, 'glams/glam_detail.html', context)


# ======================================================================================================================
# UPDATE
# ======================================================================================================================
@permission_required('glams.change_institution')
def institution_update(request, pk):
    institution = get_object_or_404(Institution, pk=pk)
    if request.method == 'POST':
        form = InstitutionForm(request.POST, instance=institution)
        if form.is_valid():
            form.save()
            return redirect(reverse('glams:institution_list'))
    else:
        form = InstitutionForm(instance=institution)
    return render(request, 'glams/institution_update.html', {'form': form})


@permission_required('glams.change_glam')
def glam_update(request, pk):
    glam = get_object_or_404(Glam, pk=pk)
    if request.method == 'POST':
        form = GlamForm(request.POST, instance=glam)
        if form.is_valid():
            form.save()
            return redirect(reverse('glams:glam_list'))
    else:
        form = GlamForm(instance=glam)
    return render(request, 'glams/glam_update.html', {'form': form})


# ======================================================================================================================
# DELETE
# ======================================================================================================================
@permission_required('glams.delete_institution')
def institution_delete(request, pk):
    institution = get_object_or_404(Institution, pk=pk)
    if request.method == 'POST':
        institution.delete()
        return redirect(reverse('glams:institution_list'))
    return render(request, 'glams/institution_delete.html', {'item': institution})


@permission_required('glams.delete_glam')
def glam_delete(request, pk):
    glam = get_object_or_404(Glam, pk=pk)
    if request.method == 'POST':
        glam.delete()
        return redirect(reverse('glams:glam_list'))
    return render(request, 'glams/glam_delete.html', {'item': glam})
