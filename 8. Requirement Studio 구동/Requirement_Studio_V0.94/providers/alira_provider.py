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
            license_path=str(config.get("license_path") or ""),
        )

    def metadata(self) -> ProviderMetadata:
        exists = self.client.exe_exists()
        license_path = self.client.resolved_license_path()
        if not exists:
            credential = "ALIRA CLI 미설치"
        elif not license_path:
            credential = "ALIRA 라이선스 미감지"
        else:
            credential = f"ALIRA CLI/라이선스 확인 · {license_path.name}"
        return ProviderMetadata(
            provider_id=self.provider_id,
            display_name=self.display_name,
            model=self.client.model,
            api_base=self.client.api_base,
            credential_status=credential,
            supports_text=True,
            supports_images=bool(self.config.get("supports_images", False)),
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
        progress_callback: ProgressCallback = None,
    ) -> str:
        prompt = user_prompt
        if system_message:
            prompt = f"[SYSTEM INSTRUCTION]\n{system_message}\n\n[USER REQUEST]\n{user_prompt}"
        return self.client.run_prompt(
            prompt,
            agent_type="general_agent",
            timeout_seconds=timeout_seconds,
            progress_callback=progress_callback,
        )

    def generate_with_images(
        self,
        user_prompt: str,
        image_paths,
        *,
        system_message: str = "",
        timeout_seconds: int | None = None,
    ) -> str:
        """ALIRA Native Vision through the verified CLI Image Tool route.

        ALIRA Vision Verifier V0.3 confirmed that the local ALIRA CLI/general_agent
        can recover randomized image-only facts when its image tool is allowed in
        headless mode. V0.40 therefore uses that verified path instead of assuming
        a guessed direct OpenAI-compatible endpoint on the Qwen gateway.
        """
        if not bool(self.config.get("supports_images", False)):
            raise RuntimeError(
                "ALIRA Native Vision이 비활성화되어 있습니다. "
                "config/provider_config.json의 alira.supports_images를 확인해주세요."
            )
        transport = str(self.config.get("vision_transport") or "cli_image_tool").strip().lower()
        if transport != "cli_image_tool":
            raise RuntimeError(f"지원하지 않는 ALIRA Vision transport입니다: {transport}")
        return self.client.run_vision_prompt(
            user_prompt,
            image_paths,
            system_message=system_message,
            timeout_seconds=timeout_seconds,
        )

