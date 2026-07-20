from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from fundlab.ai.cache import FileAICache
from fundlab.ai.providers import DeepSeekProvider
from fundlab.config import Settings
from fundlab.domain.models import AIAnalysis


class DeepSeekProviderTests(unittest.TestCase):
    def test_structured_response_and_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(
                project_root=root,
                data_dir=root / "data",
                database_path=root / "test.sqlite3",
                ai_enabled=True,
                deepseek_api_key="test-key",
                deepseek_model="deepseek-v4-flash",
            )
            calls = []

            def fake_transport(url, headers, body, timeout):
                calls.append((url, headers, json.loads(body), timeout))
                content = {
                    "subject_id": "000001:A",
                    "as_of_date": "2026-01-02",
                    "summary": "测试",
                    "events": [],
                    "risk_flags": [],
                    "unknowns": [],
                }
                return {
                    "choices": [{"message": {"content": json.dumps(content)}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                }

            provider = DeepSeekProvider(
                settings, FileAICache(root / "cache"), transport=fake_transport
            )
            messages = [{"role": "user", "content": "请输出 JSON"}]
            first = provider.generate_structured(messages, AIAnalysis)
            second = provider.generate_structured(messages, AIAnalysis)
            self.assertEqual(first.data["as_of_date"], date(2026, 1, 2).isoformat())
            self.assertFalse(first.cached)
            self.assertTrue(second.cached)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][2]["response_format"], {"type": "json_object"})
            self.assertNotIn("test-key", json.dumps(calls[0][2]))


if __name__ == "__main__":
    unittest.main()
