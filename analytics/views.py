import json
import uuid

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from analytics import assistant, services
from analytics.models import AssistantMessage, AssistantSession


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


@require_http_methods(["POST"])
def create_session(request):
    session = AssistantSession.objects.create(id=uuid.uuid4())
    return envelope({"session_id": str(session.id)}, str(uuid.uuid4()))


@require_http_methods(["POST"])
def chat(request):
    trace_id = str(uuid.uuid4())
    try:
        payload = json.loads(request.body or "{}")
        session = AssistantSession.objects.get(id=payload.get("session_id"))
        question = str(payload.get("question", "")).strip()
        if not question:
            raise ValueError("问题不能为空")
        answer, evidence, status = assistant.answer(question, session)
        message = AssistantMessage.objects.create(session=session, question=question, answer=answer,
                                                  evidence=evidence, mode="local")
        return envelope({"answer": answer, "evidence": evidence, "status": status, "mode": message.mode,
                         "dashboard_filters": evidence.get("filters", {})}, trace_id)
    except (ValueError, AssistantSession.DoesNotExist, json.JSONDecodeError):
        return JsonResponse({"error": {"code": "invalid_request", "message": "会话或问题无效"},
                             "meta": {"trace_id": trace_id}}, status=400)


@require_http_methods(["DELETE"])
def delete_session(request, session_id):
    AssistantSession.objects.filter(id=session_id).delete()
    return JsonResponse({}, status=204)


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return JsonResponse({"status": "ok", "service": "经营罗盘", "database": "ok"})
    except Exception:
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)
