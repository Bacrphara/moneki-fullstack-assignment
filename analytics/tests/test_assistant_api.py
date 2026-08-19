import json
from datetime import date
from decimal import Decimal

from django.test import TestCase

from analytics.models import ImportBatch, Product, Sale, Store


class AssistantApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        batch = ImportBatch.objects.create(source_hash="b" * 64)
        ramen = Store.objects.create(external_id="S1", name="拉面店", category="拉面", district="徐汇")
        light = Store.objects.create(external_id="S2", name="轻食店", category="轻食", district="静安")
        beef = Product.objects.create(external_id="P1", name="牛肉poke", category="主食", unit_price=40)
        for index, (order, day, store, amount) in enumerate([
            ("M1", date(2026, 5, 2), light, 50), ("J1", date(2026, 6, 2), light, 80),
            ("J2", date(2026, 6, 3), ramen, 40), ("L1", date(2026, 7, 2), ramen, 100),
        ]):
            Sale.objects.create(fingerprint=str(index) * 64, order_id=order, date=day, store=store,
                                product=beef, qty=1, amount=Decimal(amount), payment="微信", batch=batch)

    def create_session(self):
        return self.client.post("/api/assistant/sessions").json()["data"]["session_id"]

    def ask(self, session_id, question):
        return self.client.post("/api/assistant/chat", data=json.dumps({"session_id": session_id, "question": question}),
                                content_type="application/json")

    def test_product_month_answer_contains_database_revenue_and_evidence(self):
        response = self.ask(self.create_session(), "牛肉poke六月卖了多少钱？")
        data = response.json()["data"]
        self.assertEqual(response.status_code, 200)
        self.assertIn("¥120.00", data["answer"])
        self.assertEqual(data["evidence"]["tool"], "query_product_revenue")
        self.assertEqual(data["evidence"]["result"]["revenue"], 120.0)

    def test_follow_up_reuses_product_and_changes_month(self):
        session = self.create_session()
        self.ask(session, "牛肉poke六月卖了多少钱？")
        data = self.ask(session, "那五月呢？").json()["data"]
        self.assertIn("¥50.00", data["answer"])
        self.assertEqual(data["evidence"]["filters"]["month"], "2026-05")

    def test_store_category_and_aov_questions_use_database(self):
        session = self.create_session()
        category = self.ask(session, "哪个品类的门店营业额最高？").json()["data"]
        self.assertIn("拉面", category["answer"])
        self.assertIn("¥140.00", category["answer"])
        aov = self.ask(session, "客单价最近是涨了还是跌了？").json()["data"]
        self.assertEqual(aov["evidence"]["tool"], "query_aov_trend")
        self.assertIn("上涨", aov["answer"])

    def test_unknown_question_refuses_instead_of_inventing(self):
        data = self.ask(self.create_session(), "明天会下雨吗？").json()["data"]
        self.assertEqual(data["status"], "unsupported")
        self.assertNotIn("0", data["answer"])
