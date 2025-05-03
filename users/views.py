import os
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render, redirect, reverse
from django.contrib.auth import logout
from urllib.parse import urlencode

# ==================================================================================================================== #
# LOGIN
# ==================================================================================================================== #
def login_oauth(request):
    next_url = request.GET.get("next", "/")
    login_url = reverse("users:social:begin", kwargs={"backend": "mediawiki"})

    redirect_url = f"{login_url}?{urlencode({'next': next_url})}"
    return redirect(redirect_url)


def logout_oauth(request):
    logout(request)
    return redirect(request.GET.get("next", "/"))
