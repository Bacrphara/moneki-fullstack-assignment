import json
import logging
import time

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)
ALLOWED_TOOLS = {"query_product_revenue", "query_revenue_by_store_category", "query_aov_trend"}


def request_plan(question, context=None):
    if not settings.DEEPSEEK_API_KEY:
        return None
    prompt = "将问题映射为数据工具。只返回JSON: {tool,args}。允许工具:" + ",".join(sorted(ALLOWED_TOOLS))
    body = {"model": settings.DEEPSEEK_MODEL, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": prompt},
                         {"role": "user", "content": json.dumps({"question": question, "context": context or {}}, ensure_ascii=False)}]}
    for attempt in range(3):
        try:
            response = httpx.post(f"{settings.DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions",
                                  headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"}, json=body, timeout=15)
            response.raise_for_status()
            plan = json.loads(response.json()["choices"][0]["message"]["content"])
            if plan.get("tool") not in ALLOWED_TOOLS or not isinstance(plan.get("args"), dict):
                raise ValueError("模型返回了非白名单工具")
            return plan
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("DeepSeek 规划失败 attempt=%s type=%s", attempt + 1, type(exc).__name__)
            if attempt < 2:
                time.sleep(0.25 * (2 ** attempt))
    return None
