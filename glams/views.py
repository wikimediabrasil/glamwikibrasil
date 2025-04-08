from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.db.models import Sum

from medias.models import MediaRequests
from .models import Institution, Glam
from .forms import InstitutionForm, GlamForm


# ======================================================================================================================
# INSTITUTIONAL PAGES
# ======================================================================================================================
def index(request):
    context = {}
    return render(request, "glams/index.html", context=context)


# ======================================================================================================================
# CREATE
# ======================================================================================================================
def institution_create(request):
    if request.method == 'POST':
        form = InstitutionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(reverse('glams:institution_list'))
    else:
        form = InstitutionForm()
    return render(request, 'glams/institution_create.html', {'form': form})

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
def institution_list(request):
    items = Institution.objects.all()
    return render(request, 'glams/institution_list.html', {'items': items})


def institution_detail(request, pk):
    institution = get_object_or_404(Institution, pk=pk)
    return render(request, 'glams/institution_detail.html', {'item': institution})


def glam_list(request):
    items = Glam.objects.all()
    return render(request, 'glams/glam_list.html', {'items': items})


def glam_detail(request, pk):
    glam = get_object_or_404(Glam, pk=pk)
    media_requests = MediaRequests.objects.filter(file__glam=glam).order_by("timestamp").values("timestamp").annotate(total=Sum("requests"))
    timestamp_options = list(media_requests.values_list("timestamp", flat=True))

    return render(request, 'glams/glam_detail.html', {'item': glam, 'chart_data': list(media_requests), 'timestamp_options': timestamp_options})


# ======================================================================================================================
# UPDATE
# ======================================================================================================================
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
def institution_delete(request, pk):
    institution = get_object_or_404(Institution, pk=pk)
    if request.method == 'POST':
        institution.delete()
        return redirect(reverse('glams:institution_list'))
    return render(request, 'glams/institution_delete.html', {'item': institution})


def glam_delete(request, pk):
    glam = get_object_or_404(Glam, pk=pk)
    if request.method == 'POST':
        glam.delete()
        return redirect(reverse('glams:glam_list'))
    return render(request, 'glams/glam_delete.html', {'item': glam})
