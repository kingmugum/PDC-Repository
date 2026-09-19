from __future__ import annotations

from pathlib import Path

from core.alira_client import AliraClient
from providers.base import AIProvider, ProviderMetadata, ProgressCallback


class AliraProvider(AIProvider):
    provider_id = "alira"
    display_name = "ALIRA / Qwen"

    def __init__(self, project_root: Path, config: dict):
        self.project_root = Path(project_root).resolve()
        self.config = config
        self.client = AliraClient(
            project_root=self.project_root,
            model=str(config.get("model") or "hosted_vllm/Qwen/Qwen3.6-27B"),
            api_base=str(config.get("api_base") or "http://10.10.10.200:19640/v1"),
            timeout_seconds=int(config.get("timeout_seconds") or 600),
        )

    def metadata(self) -> ProviderMetadata:
        exists = self.client.exe_exists()
        credential = "ALIRA 실행파일/라이선스 확인" if exists else "ALIRA 실행파일 없음"
        return ProviderMetadata(
            provider_id=self.provider_id,
            display_name=self.display_name,
            model=self.client.model,
            api_base=self.client.api_base,
            credential_status=credential,
            supports_text=True,
            supports_images=False,
            supports_files=False,
        )

    def test_connection(self, progress_callback: ProgressCallback = None) -> str:
        return self.client.test_connection(progress_callback=progress_callback)

    def generate(
        self,
        user_prompt: str,
        *,
        system_message: str = "",
        timeout_seconds: int | None = None,
    ) -> str:
        prompt = user_prompt
        if system_message:
            prompt = f"[SYSTEM INSTRUCTION]\n{system_message}\n\n[USER REQUEST]\n{user_prompt}"
        return self.client.run_prompt(
            prompt,
            agent_type="general_agent",
            timeout_seconds=timeout_seconds,
        )
