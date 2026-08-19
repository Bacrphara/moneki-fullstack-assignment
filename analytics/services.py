from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Sum

from analytics.models import Sale


@dataclass(frozen=True)
class Filters:
    start: date
    end: date
    store_id: str = ""
    product_id: str = ""


def parse_filters(params) -> Filters:
    bounds = Sale.objects.aggregate(start=models_min("date"), end=models_max("date"))
    latest = bounds["end"] or date.today()
    try:
        start = date.fromisoformat(params.get("start")) if params.get("start") else latest - timedelta(days=29)
        end = date.fromisoformat(params.get("end")) if params.get("end") else latest
    except ValueError as exc:
        raise ValueError("日期必须使用 YYYY-MM-DD") from exc
    if start > end:
        raise ValueError("开始日期不能晚于结束日期")
    return Filters(start, end, params.get("store_id", ""), params.get("product_id", ""))


def models_min(field):
    from django.db.models import Min
    return Min(field)


def models_max(field):
    from django.db.models import Max
    return Max(field)


def sales_for(filters):
    query = Sale.objects.filter(date__range=(filters.start, filters.end))
    if filters.store_id:
        query = query.filter(store__external_id=filters.store_id)
    if filters.product_id:
        query = query.filter(product__external_id=filters.product_id)
    return query


def summary(filters):
    values = sales_for(filters).aggregate(revenue=Sum("amount"), orders=Count("order_id", distinct=True))
    revenue = values["revenue"] or Decimal("0")
    orders = values["orders"] or 0
    return {"revenue": float(revenue), "orders": orders, "aov": float(revenue / orders) if orders else None}


def trend(filters):
    rows = sales_for(filters).values("date").annotate(revenue=Sum("amount"), orders=Count("order_id", distinct=True)).order_by("date")
    return [{"date": row["date"].isoformat(), "revenue": float(row["revenue"]), "orders": row["orders"],
             "aov": float(row["revenue"] / row["orders"]) if row["orders"] else None} for row in rows]


def top_products(filters, limit=10):
    rows = sales_for(filters).values("product__external_id", "product__name", "product__category").annotate(
        revenue=Sum("amount"), qty=Sum("qty"), orders=Count("order_id", distinct=True)).order_by("-revenue")[:limit]
    return [{"product_id": row["product__external_id"], "product_name": row["product__name"],
             "category": row["product__category"], "revenue": float(row["revenue"]),
             "qty": row["qty"], "orders": row["orders"]} for row in rows]


def store_comparison(filters):
    rows = sales_for(filters).values("store__external_id", "store__name", "store__category").annotate(
        revenue=Sum("amount"), orders=Count("order_id", distinct=True)).order_by("-revenue")
    return [{"store_id": row["store__external_id"], "store_name": row["store__name"],
             "category": row["store__category"], "revenue": float(row["revenue"]), "orders": row["orders"],
             "aov": float(row["revenue"] / row["orders"]) if row["orders"] else None} for row in rows]
