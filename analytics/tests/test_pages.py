from django.conf import settings
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

    def test_admin_uses_configured_non_default_path(self):
        self.assertRegex(settings.ADMIN_PATH, r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d]{8}$")
        self.assertEqual(self.client.get("/admin/").status_code, 404)
        response = self.client.get(f"/{settings.ADMIN_PATH}/")
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/{settings.ADMIN_PATH}/login/", response.url)
