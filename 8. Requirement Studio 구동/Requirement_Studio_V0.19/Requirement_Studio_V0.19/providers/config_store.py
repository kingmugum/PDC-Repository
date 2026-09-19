from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "selected_provider": "alira",
    "alira": {
        "model": "hosted_vllm/Qwen/Qwen3.6-27B",
        "api_base": "http://10.10.10.200:19640/v1",
        "timeout_seconds": 600,
    },
    "hchat": {
        "backend": "gpt",
        "base_url": "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3",
        "project_id": "",
        "api_version": "2025-04-01-preview",
        "gpt_model": "gpt-5.6-terra",
        "gpt_model_options": ["gpt-5.6-terra", "gpt-5.4", "gpt-5.2"],
        "gemini_model": "gemini-3.1-pro-preview",
        "gemini_stream_option": "generateContent",
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

    def load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

        merged = json.loads(json.dumps(DEFAULT_CONFIG))
        for key, value in data.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key].update(value)
            else:
                merged[key] = value
        return merged

    def save(self, data: dict[str, Any]) -> None:
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def update_selection(
        self,
        provider_id: str,
        *,
        gpt_model: str | None = None,
    ) -> dict[str, Any]:
        data = self.load()
        data["selected_provider"] = provider_id
        if provider_id == "hchat_gpt":
            data["hchat"]["backend"] = "gpt"
            if gpt_model:
                data["hchat"]["gpt_model"] = gpt_model
        elif provider_id == "hchat_gemini":
            data["hchat"]["backend"] = "gemini"
        self.save(data)
        return data
