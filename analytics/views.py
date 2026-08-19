import uuid

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from analytics import services


def dashboard(request):
    return render(request, "dashboard.html")


def envelope(data, trace_id):
    return JsonResponse({"data": data, "meta": {"trace_id": trace_id, "timezone": "Asia/Shanghai",
                         "metric_policy": "营业额=有效明细金额之和；订单数=去重订单号；客单价=营业额/订单数"}})


def api_view(handler):
    def wrapped(request):
        trace_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        try:
            filters = services.parse_filters(request.GET)
            return envelope(handler(filters), trace_id)
        except ValueError as exc:
            return JsonResponse({"error": {"code": "invalid_filters", "message": str(exc)},
                                 "meta": {"trace_id": trace_id}}, status=400)
    return wrapped


summary_api = api_view(services.summary)
trend_api = api_view(services.trend)
top_products_api = api_view(services.top_products)
store_comparison_api = api_view(services.store_comparison)


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return JsonResponse({"status": "ok", "service": "经营罗盘", "database": "ok"})
    except Exception:
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)
