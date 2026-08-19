from django.test import TestCase


class PageAndHealthTests(TestCase):
    def test_dashboard_contains_operational_controls(self):
        response = self.client.get("/")
        self.assertContains(response, "经营罗盘")
        self.assertContains(response, "今日经营雷达")
        self.assertContains(response, "问问经营助手")
        self.assertContains(response, 'name="start"')

    def test_health_checks_database(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], "ok")
