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
    ) -> str:
        raise NotImplementedError
