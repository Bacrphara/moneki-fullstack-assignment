from django.http import JsonResponse
from django.shortcuts import render


def dashboard(request):
    return render(request, "dashboard.html")


def health(request):
    return JsonResponse({"status": "ok", "service": "经营罗盘"})
