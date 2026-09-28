from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "selected_provider": "hchat_gpt",
    "alira": {
        "model": "hosted_vllm/Qwen/Qwen3.6-27B",
        "model_options": ["hosted_vllm/Qwen/Qwen3.6-27B"],
        "api_base": "http://10.10.10.200:19640/v1",
        "timeout_seconds": 600,
        "supports_images": True,
        "vision_transport": "cli_image_tool",
        "license_path": "alira_license/license.lic",
    },
    "custom": {
        "profile": "openai_compatible",
        "profile_flags": {
            "openai_compatible": True,
            "openai_responses": True,
            "anthropic_messages": True,
            "gemini_generate_content": True,
        },
        "base_url": "",
        "model": "",
        "model_options": [],
        "timeout_seconds": 120,
        "max_tokens": 4096,
        "api_key_required": True,
        "auth_mode": "auto",
        "api_key_name": "Authorization",
        "version_header_name": "",
        "version_header_value": "",
        "supports_images": False,
    },
    "hchat": {
        "backend": "gpt",
        "base_url": "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3",
        "project_id": "",
        "api_version": "2025-04-01-preview",
        "gpt_model": "gpt-5.6-terra",
        "gpt_model_options": ["gpt-5.6-terra", "gpt-5.4", "gpt-5.2"],
        "gpt_supports_images": True,
        "gemini_model": "gemini-3.1-pro-preview",
        "gemini_model_options": ["gemini-3.1-pro-preview"],
        "gemini_stream_option": "generateContent",
        "gemini_supports_images": True,
        # V0.36 Claude skeleton. Detailed H-Chat transport values are intentionally TBD
        # until the user's corporate connection specification is confirmed.
        "claude_protocol": "tbd",
        "claude_base_url": "",
        "claude_endpoint": "",
        "claude_model": "TBD - 연결 정보 입력 필요",
        "claude_model_options": ["TBD - 연결 정보 입력 필요"],
        "claude_api_version": "2023-06-01",
        "claude_supports_images": False,
        "timeout_seconds": 120,
        "max_retry": 3,
        "retry_wait_seconds": 2.0,
    },
}


class ProviderConfigStore:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.config_dir = self.project_root / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.config_dir / "provider_config.json"
        if not self.path.exists():
            self.save(DEFAULT_CONFIG)

    @staticmethod
    def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
        result = json.loads(json.dumps(base))
        for key, value in (overlay or {}).items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = ProviderConfigStore._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        return self._deep_merge(DEFAULT_CONFIG, data)

    def save(self, data: dict[str, Any]) -> None:
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def update_selection(
        self,
        provider_id: str,
        *,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Persist provider/model selection without hard-coding one backend.

        V0.36 goal: every provider can expose a model dropdown and the selected model
        can be swapped through config rather than code edits.
        """
        data = self.load()
        provider_id = str(provider_id or "hchat_gpt")
        data["selected_provider"] = provider_id

        if provider_id == "hchat_gpt":
            data["hchat"]["backend"] = "gpt"
            if model:
                data["hchat"]["gpt_model"] = model
        elif provider_id == "hchat_gemini":
            data["hchat"]["backend"] = "gemini"
            if model:
                data["hchat"]["gemini_model"] = model
        elif provider_id == "hchat_claude":
            data["hchat"]["backend"] = "claude"
            if model:
                data["hchat"]["claude_model"] = model
        elif provider_id == "alira":
            if model:
                data["alira"]["model"] = model
        elif provider_id == "custom_api":
            if model:
                data["custom"]["model"] = model
        self.save(data)
        return data

    def update_alira_connection(
        self,
        *,
        license_path: str | None = None,
        model: str | None = None,
        api_base: str | None = None,
    ) -> dict[str, Any]:
        data = self.load()
        alira = data.setdefault("alira", {})
        if license_path is not None:
            alira["license_path"] = str(license_path or "").strip()
        if model:
            alira["model"] = str(model).strip()
            options = [str(x).strip() for x in (alira.get("model_options") or []) if str(x).strip()]
            if alira["model"] not in options:
                options.insert(0, alira["model"])
            alira["model_options"] = options
        if api_base:
            alira["api_base"] = str(api_base).strip()
        data["selected_provider"] = "alira"
        self.save(data)
        return data

    def update_custom(
        self,
        *,
        profile: str,
        base_url: str,
        model: str,
        model_options: list[str] | None = None,
        api_key_required: bool,
        auth_mode: str = "bearer",
        api_key_name: str = "Authorization",
        version_header_name: str = "",
        version_header_value: str = "",
        supports_images: bool,
    ) -> dict[str, Any]:
        data = self.load()
        custom = data.setdefault("custom", {})
        options = [str(x).strip() for x in (model_options or []) if str(x).strip()]
        if model and model not in options:
            options.insert(0, model)
        custom.update({
            "profile": str(profile or "openai_compatible"),
            "base_url": str(base_url or "").strip(),
            "model": str(model or "").strip(),
            "model_options": options,
            "api_key_required": bool(api_key_required),
            "auth_mode": str(auth_mode or "bearer"),
            "api_key_name": str(api_key_name or "").strip(),
            "version_header_name": str(version_header_name or "").strip(),
            "version_header_value": str(version_header_value or "").strip(),
            "supports_images": bool(supports_images),
        })
        data["selected_provider"] = "custom_api"
        self.save(data)
        return data
