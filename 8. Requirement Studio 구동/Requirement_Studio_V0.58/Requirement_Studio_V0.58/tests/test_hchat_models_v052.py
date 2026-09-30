from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from providers import hchat_provider
from providers.config_store import ProviderConfigStore
from providers.hchat_provider import HChatProvider


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload
        self.status_code = 200
        self.text = json.dumps(payload)

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeRequests:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _FakeResponse(self.payload)


class HChatV052Tests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "api_keys").mkdir(parents=True, exist_ok=True)

    def test_config_catalog_migrates_old_gemini_and_claude(self):
        config_dir = self.root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "provider_config.json").write_text(
            json.dumps({
                "hchat": {
                    "base_url": "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v2",
                    "gemini_model": "gemini-3.1-pro-preview",
                    "gemini_model_options": ["gemini-3.1-pro-preview"],
                    "claude_protocol": "tbd",
                    "claude_model": "TBD - 연결 정보 입력 필요",
                    "claude_model_options": ["TBD - 연결 정보 입력 필요"],
                    "claude_supports_images": False,
                }
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        cfg = ProviderConfigStore(self.root).load()["hchat"]
        self.assertEqual(cfg["base_url"], "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3")
        self.assertEqual(cfg["gemini_model"], "gemini-3.7-flash")
        self.assertEqual(cfg["gemini_model_options"], ["gemini-3.7-flash"])
        self.assertEqual(cfg["claude_model"], "claude-sonnet-5")
        self.assertEqual(cfg["claude_model_options"], ["claude-sonnet-5"])
        self.assertEqual(cfg["claude_protocol"], "hchat_messages_v3")
        self.assertEqual(cfg["claude_endpoint"], "claude/messages")
        self.assertTrue(cfg["claude_supports_images"])

    def test_gemini_v3_uses_bearer_header_and_ignores_thought_parts(self):
        cfg = {
            "base_url": "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3",
            "project_id": "P123",
            "gemini_model": "gemini-3.7-flash",
            "gemini_stream_option": "generateContent",
        }
        provider = HChatProvider(self.root, cfg, backend="gemini")
        fake = _FakeRequests({
            "candidates": [{
                "content": {
                    "parts": [
                        {"text": "internal reasoning", "thought": True},
                        {"text": "FINAL_OK"},
                    ]
                }
            }]
        })
        with patch.object(hchat_provider, "requests", fake):
            result = provider._ask_once("hello", "system", "secret", 30)
        self.assertEqual(result, "FINAL_OK")
        self.assertEqual(len(fake.calls), 1)
        url, kwargs = fake.calls[0]
        self.assertEqual(
            url,
            "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3/models/gemini-3.7-flash:generateContent",
        )
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(kwargs["headers"]["X-Project-Id"], "P123")
        self.assertNotIn("params", kwargs)
        self.assertEqual(kwargs["json"]["systemInstruction"]["parts"][0]["text"], "system")

    def test_claude_sonnet5_v3_messages_payload(self):
        cfg = {
            "base_url": "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3",
            "project_id": "P456",
            "claude_protocol": "hchat_messages_v3",
            "claude_endpoint": "claude/messages",
            "claude_model": "claude-sonnet-5",
            "claude_max_tokens": 4096,
            "claude_thinking_mode": "disabled",
        }
        provider = HChatProvider(self.root, cfg, backend="claude")
        fake = _FakeRequests({"content": [{"type": "text", "text": "CLAUDE_OK"}]})
        with patch.object(hchat_provider, "requests", fake):
            result = provider._ask_once("hello", "system", "secret", 30)
        self.assertEqual(result, "CLAUDE_OK")
        url, kwargs = fake.calls[0]
        self.assertEqual(
            url,
            "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3/claude/messages",
        )
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(kwargs["headers"]["X-Project-Id"], "P456")
        payload = kwargs["json"]
        self.assertEqual(payload["model"], "claude-sonnet-5")
        self.assertEqual(payload["max_tokens"], 4096)
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertEqual(payload["system"], "system")
        self.assertNotIn("temperature", payload)
        self.assertNotIn("top_p", payload)

    def test_claude_sonnet5_v3_vision_payload(self):
        image_path = self.root / "fixture.png"
        image_path.write_bytes(b"fakepng")
        cfg = {
            "base_url": "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3",
            "claude_protocol": "hchat_messages_v3",
            "claude_endpoint": "claude/messages",
            "claude_model": "claude-sonnet-5",
            "claude_supports_images": True,
            "claude_max_tokens": 4096,
            "claude_thinking_mode": "disabled",
            "manual_api_key": "secret",
            "max_retry": 1,
        }
        provider = HChatProvider(self.root, cfg, backend="claude")
        fake = _FakeRequests({"content": [{"type": "text", "text": "VISION_OK"}]})
        with patch.object(hchat_provider, "requests", fake):
            result = provider.generate_with_images("inspect", [image_path], system_message="system", timeout_seconds=30)
        self.assertEqual(result, "VISION_OK")
        url, kwargs = fake.calls[0]
        self.assertTrue(url.endswith("/api/v3/claude/messages"))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret")
        content = kwargs["json"]["messages"][0]["content"]
        self.assertEqual(content[0]["type"], "image")
        self.assertEqual(content[-1], {"type": "text", "text": "inspect"})

    def test_v053_run_metadata_exposes_endpoint_family(self):
        gemini = HChatProvider(self.root, {
            "base_url": "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3",
            "project_id": "P1",
            "gemini_model": "gemini-3.7-flash",
        }, backend="gemini").metadata()
        self.assertEqual(gemini.model, "gemini-3.7-flash")
        self.assertEqual(gemini.endpoint_family, "hchat_v3_generate_content")
        self.assertEqual(gemini.auth_mode, "Bearer")
        self.assertTrue(gemini.project_header_enabled)
        self.assertEqual(gemini.response_parsing_mode, "gemini_candidates_without_thought_parts")

        claude = HChatProvider(self.root, {
            "base_url": "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3",
            "claude_model": "claude-sonnet-5",
        }, backend="claude").metadata()
        self.assertEqual(claude.model, "claude-sonnet-5")
        self.assertEqual(claude.endpoint_family, "hchat_v3_claude_messages")



if __name__ == "__main__":
    unittest.main()
