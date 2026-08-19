from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from analytics import llm


class DeepSeekAdapterTests(SimpleTestCase):
    @override_settings(DEEPSEEK_API_KEY="test-only", DEEPSEEK_BASE_URL="https://api.deepseek.com")
    @patch("analytics.llm.time.sleep")
    @patch("analytics.llm.httpx.post")
    def test_retries_and_returns_none_on_network_failure(self, post, sleep):
        import httpx
        post.side_effect = httpx.ConnectError("offline")
        self.assertIsNone(llm.request_plan("问题"))
        self.assertEqual(post.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @override_settings(DEEPSEEK_API_KEY="test-only")
    @patch("analytics.llm.time.sleep")
    @patch("analytics.llm.httpx.post")
    def test_rejects_unknown_tool(self, post, sleep):
        response = post.return_value
        response.raise_for_status.return_value = None
        response.json.return_value = {"choices": [{"message": {"content": '{"tool":"run_sql","args":{}}'}}]}
        self.assertIsNone(llm.request_plan("删除数据库"))
