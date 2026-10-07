from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

ProgressCallback = Optional[Callable[[int, str], None]]


@dataclass(frozen=True)
class ProviderMetadata:
    provider_id: str
    display_name: str
    model: str
    api_base: str
    credential_status: str
    supports_text: bool = True
    supports_images: bool = False
    supports_files: bool = False
    endpoint_family: str = ""
    auth_mode: str = ""
    project_header_enabled: bool = False
    response_parsing_mode: str = ""


class AIProvider:
    provider_id = "base"
    display_name = "AI Provider"

    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    def test_connection(self, progress_callback: ProgressCallback = None) -> str:
        raise NotImplementedError

    def generate(
        self,
        user_prompt: str,
        *,
        system_message: str = "",
        timeout_seconds: int | None = None,
        progress_callback: ProgressCallback = None,
    ) -> str:
        raise NotImplementedError

    def generate_with_images(
        self,
        user_prompt: str,
        image_paths,
        *,
        system_message: str = "",
        timeout_seconds: int | None = None,
    ) -> str:
        raise RuntimeError(f"{self.display_name} Provider는 이미지 입력을 지원하지 않습니다.")
