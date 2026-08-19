from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from analytics.models import ImportBatch, Product, Sale, Store


class DashboardApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        batch = ImportBatch.objects.create(source_hash="a" * 64)
        store = Store.objects.create(external_id="S1", name="徐汇店", category="拉面", district="徐汇")
        p1 = Product.objects.create(external_id="P1", name="牛肉poke", category="主食", unit_price=40)
        p2 = Product.objects.create(external_id="P2", name="可乐", category="饮料", unit_price=10)
        for fingerprint, order, day, product, amount in [
            ("1" * 64, "O1", date(2026, 6, 1), p1, 80),
            ("2" * 64, "O1", date(2026, 6, 1), p2, 10),
            ("3" * 64, "O2", date(2026, 6, 2), p1, 40),
        ]:
            Sale.objects.create(fingerprint=fingerprint, order_id=order, date=day, store=store,
                                product=product, qty=1, amount=Decimal(amount), payment="微信", batch=batch)

    def test_summary_uses_distinct_orders_for_aov(self):
        response = self.client.get("/api/dashboard/summary", {"start": "2026-06-01", "end": "2026-06-02"})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["revenue"], 130.0)
        self.assertEqual(data["orders"], 2)
        self.assertEqual(data["aov"], 65.0)

    def test_trend_and_top_products_return_joined_names(self):
        trend = self.client.get("/api/dashboard/trend", {"start": "2026-06-01", "end": "2026-06-02"}).json()["data"]
        top = self.client.get("/api/dashboard/top-products", {"start": "2026-06-01", "end": "2026-06-02"}).json()["data"]
        self.assertEqual(trend[0], {"date": "2026-06-01", "revenue": 90.0, "orders": 1, "aov": 90.0})
        self.assertEqual(top[0]["product_name"], "牛肉poke")
        self.assertEqual(top[0]["revenue"], 120.0)

    def test_invalid_date_range_returns_structured_error(self):
        response = self.client.get("/api/dashboard/summary", {"start": "bad"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_filters")
