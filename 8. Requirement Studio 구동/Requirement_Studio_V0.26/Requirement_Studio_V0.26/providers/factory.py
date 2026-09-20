from __future__ import annotations

from pathlib import Path

from providers.alira_provider import AliraProvider
from providers.hchat_provider import HChatProvider


def create_provider(project_root: Path, provider_id: str, config: dict):
    provider_id = (provider_id or "alira").lower()
    if provider_id == "alira":
        return AliraProvider(project_root, config.get("alira", {}))
    if provider_id == "hchat_gpt":
        return HChatProvider(project_root, config.get("hchat", {}), backend="gpt")
    if provider_id == "hchat_gemini":
        return HChatProvider(project_root, config.get("hchat", {}), backend="gemini")
    raise ValueError(f"지원하지 않는 Provider: {provider_id}")
