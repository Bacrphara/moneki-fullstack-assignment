from django.conf import settings
from django.test import Client, TestCase, override_settings


class PageAndHealthTests(TestCase):
    def test_dashboard_contains_operational_controls(self):
        response = self.client.get("/")
        self.assertContains(response, "经营罗盘")
        self.assertContains(response, "今日经营雷达")
        self.assertContains(response, "问问经营助手")
        self.assertContains(response, 'name="start"')

    def test_assistant_is_visible_before_metrics_and_exposes_loading_feedback(self):
        content = self.client.get("/").content.decode()
        self.assertLess(content.index('id="assistant"'), content.index('id="kpis"'))
        self.assertIn('id="assistant-status"', content)
        self.assertIn('aria-live="polite"', content)
        self.assertIn("正在查询真实数据", content)

    def test_dashboard_provides_csrf_token_for_assistant_requests(self):
        browser = Client(enforce_csrf_checks=True)
        response = browser.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", browser.cookies)
        self.assertContains(response, 'id="assistant-question"')

    def test_health_checks_database(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], "ok")

    @override_settings(DEBUG=True)
    def test_admin_uses_configured_non_default_path(self):
        self.assertRegex(settings.ADMIN_PATH, r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d]{8}$")
        default_response = self.client.get("/admin/")
        self.assertEqual(default_response.status_code, 404)
        self.assertNotContains(default_response, settings.ADMIN_PATH, status_code=404)
        response = self.client.get(f"/{settings.ADMIN_PATH}/")
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/{settings.ADMIN_PATH}/login/", response.url)
