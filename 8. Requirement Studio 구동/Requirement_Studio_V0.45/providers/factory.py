from __future__ import annotations

from pathlib import Path

from providers.alira_provider import AliraProvider
from providers.hchat_provider import HChatProvider
from providers.custom_api_provider import CustomApiProvider


def create_provider(project_root: Path, provider_id: str, config: dict):
    provider_id = (provider_id or "alira").lower()
    if provider_id == "alira":
        return AliraProvider(project_root, config.get("alira", {}))
    if provider_id == "hchat_gpt":
        return HChatProvider(project_root, config.get("hchat", {}), backend="gpt")
    if provider_id == "hchat_gemini":
        return HChatProvider(project_root, config.get("hchat", {}), backend="gemini")
    if provider_id == "hchat_claude":
        return HChatProvider(project_root, config.get("hchat", {}), backend="claude")
    if provider_id == "custom_api":
        return CustomApiProvider(project_root, config.get("custom", {}))
    raise ValueError(f"지원하지 않는 Provider: {provider_id}")
