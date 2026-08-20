import calendar
import re
from datetime import date
from decimal import Decimal

from django.db.models import Count, Sum

from analytics import llm
from analytics.models import Product, Sale

MONTHS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
          "十": 10, "十一": 11, "十二": 12}


def month_range(year, month):
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def extract_month(question):
    match = re.search(r"(20\d{2})?年?([一二三四五六七八九十]{1,3}|1[0-2]|0?[1-9])月", question)
    if not match:
        return None
    year = int(match.group(1) or (Sale.objects.order_by("-date").values_list("date", flat=True).first() or date.today()).year)
    raw = match.group(2)
    return year, int(raw) if raw.isdigit() else MONTHS[raw]


def previous_context(session):
    last = session.messages.order_by("-created_at").first()
    return last.evidence if last else {}


def plan(question, session):
    context = previous_context(session)
    month = extract_month(question)
    if ("客单价" in question and ("最近" in question or "涨" in question or "跌" in question)):
        return {"tool": "query_aov_trend", "args": {}}
    if "哪个品类" in question and "营业额" in question:
        return {"tool": "query_revenue_by_store_category", "args": {}}
    products = list(Product.objects.values_list("name", flat=True))
    product = next((name for name in products if name.lower() in question.lower()), None)
    if not product and ("那" in question or "呢" in question):
        product = context.get("filters", {}).get("product")
    if product and month:
        return {"tool": "query_product_revenue", "args": {"product": product, "year": month[0], "month": month[1]}}
    return {"tool": "unsupported", "args": {}}


def execute(plan):
    tool, args = plan["tool"], plan["args"]
    if tool == "query_product_revenue":
        start, end = month_range(args["year"], args["month"])
        rows = Sale.objects.filter(product__name=args["product"], date__range=(start, end))
        values = rows.aggregate(revenue=Sum("amount"), orders=Count("order_id", distinct=True), qty=Sum("qty"))
        return {"filters": {"product": args["product"], "month": f'{args["year"]}-{args["month"]:02d}',
                            "start": start.isoformat(), "end": end.isoformat()},
                "result": {"revenue": float(values["revenue"]) if values["revenue"] is not None else None,
                           "orders": values["orders"], "qty": values["qty"]}}
    if tool == "query_revenue_by_store_category":
        row = Sale.objects.values("store__category").annotate(revenue=Sum("amount"), orders=Count("order_id", distinct=True)).order_by("-revenue").first()
        return {"filters": {}, "result": {"category": row["store__category"], "revenue": float(row["revenue"]), "orders": row["orders"]}}
    if tool == "query_aov_trend":
        months = list(Sale.objects.dates("date", "month", order="DESC")[:2])
        if len(months) < 2:
            return {"filters": {}, "result": None}
        periods = []
        for month in reversed(months):
            start, end = month_range(month.year, month.month)
            values = Sale.objects.filter(date__range=(start, end)).aggregate(revenue=Sum("amount"), orders=Count("order_id", distinct=True))
            periods.append({"month": month.strftime("%Y-%m"), "aov": float(values["revenue"] / values["orders"])})
        change = periods[1]["aov"] - periods[0]["aov"]
        range_start, _ = month_range(months[-1].year, months[-1].month)
        _, range_end = month_range(months[0].year, months[0].month)
        return {"filters": {"start": range_start.isoformat(), "end": range_end.isoformat()},
                "result": {"periods": periods, "change": change}}
    return {"filters": {}, "result": None}


def render(tool, evidence):
    result = evidence["result"]
    if tool == "unsupported":
        return "这份数据不包含该问题所需的信息。你可以询问商品营业额、门店品类或客单价趋势。", "unsupported"
    if result is None or result.get("revenue", 1) is None:
        return "当前数据中没有匹配记录，不能将缺失数据当作 0。", "no_data"
    if tool == "query_product_revenue":
        return f'{evidence["filters"]["product"]}在{evidence["filters"]["month"]}的营业额为 ¥{result["revenue"]:,.2f}，共 {result["orders"]} 笔订单。', "answered"
    if tool == "query_revenue_by_store_category":
        return f'{result["category"]}品类门店营业额最高，为 ¥{result["revenue"]:,.2f}。', "answered"
    if tool == "query_aov_trend":
        direction = "上涨" if result["change"] > 0 else "下跌" if result["change"] < 0 else "持平"
        a, b = result["periods"]
        return f'客单价从 {a["month"]} 的 ¥{a["aov"]:,.2f} 到 {b["month"]} 的 ¥{b["aov"]:,.2f}，{direction} ¥{abs(result["change"]):,.2f}。', "answered"
    return "这份数据不包含该问题所需的信息。你可以询问商品营业额、门店品类或客单价趋势。", "unsupported"


def answer(question, session):
    context = previous_context(session)
    remote_plan = llm.request_plan(question, context)
    planned = remote_plan or plan(question, session)
    mode = "deepseek" if remote_plan else "local"
    if planned["tool"] == "unsupported":
        text, status = render("unsupported", {"result": None})
        return text, {"tool": "unsupported", "filters": {}, "result": None}, status, "local"
    try:
        payload = execute(planned)
    except (KeyError, TypeError, ValueError):
        planned = plan(question, session)
        payload = execute(planned) if planned["tool"] != "unsupported" else {"filters": {}, "result": None}
        mode = "local"
    evidence = {"tool": planned["tool"], **payload}
    text, status = render(planned["tool"], evidence)
    return text, evidence, status, mode
