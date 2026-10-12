from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Any

import requests

from providers.base import AIProvider, ProviderMetadata, ProgressCallback


class CustomApiProvider(AIProvider):
    """Configurable REST provider for common external/corporate API shapes.

    V0.36 protocol profiles:
    - openai_compatible: OpenAI-compatible /chat/completions payload
    - openai_responses: OpenAI Responses-compatible /responses payload
    - anthropic_messages: Anthropic Messages payload
    - gemini_generate_content: Gemini generateContent payload

    The secret API key is runtime-only (manual_api_key or
    REQUIREMENT_STUDIO_CUSTOM_API_KEY) and is never persisted by this class.
    """

    provider_id = "custom_api"
    display_name = "기타 API"

    PROFILE_LABELS = {
        "openai_compatible": "OpenAI 호환 Chat Completions",
        "openai_responses": "OpenAI Responses",
        "anthropic_messages": "Anthropic Messages",
        "gemini_generate_content": "Gemini generateContent",
    }

    def __init__(self, project_root: Path, config: dict):
        self.project_root = Path(project_root).resolve()
        self.config = dict(config or {})
        self.profile = str(self.config.get("profile") or "openai_compatible")
        self.base_url = str(self.config.get("base_url") or "").strip()
        self.model = str(self.config.get("model") or "").strip()
        self.timeout_seconds = int(self.config.get("timeout_seconds") or 120)
        self.max_tokens = int(self.config.get("max_tokens") or 4096)
        self.api_key_required = bool(self.config.get("api_key_required", True))
        self.auth_mode = str(self.config.get("auth_mode") or "auto").strip().lower()
        self.api_key_name = str(self.config.get("api_key_name") or "").strip()
        self.version_header_name = str(self.config.get("version_header_name") or "").strip()
        self.version_header_value = str(self.config.get("version_header_value") or "").strip()
        self.supports_image_input = bool(self.config.get("supports_images", False))
        self.manual_api_key = str(self.config.get("manual_api_key") or "").strip()

    def _resolve_key(self) -> str:
        return self.manual_api_key or os.environ.get("REQUIREMENT_STUDIO_CUSTOM_API_KEY", "").strip()

    def metadata(self) -> ProviderMetadata:
        key = self._resolve_key()
        if self.api_key_required:
            credential = "수동 API Key" if key else "API Key 미입력"
        else:
            credential = "API Key 미사용"
        label = self.PROFILE_LABELS.get(self.profile, self.profile)
        return ProviderMetadata(
            provider_id=self.provider_id,
            display_name=f"기타 API / {label}",
            model=self.model,
            api_base=self.base_url,
            credential_status=credential,
            supports_text=True,
            supports_images=self.supports_image_input,
            supports_files=False,
        )

    def _require_ready(self) -> str:
        if not self.base_url:
            raise RuntimeError("기타 API Base/Endpoint가 비어 있습니다. [기타 API 설정]에서 입력해주세요.")
        if not self.model:
            raise RuntimeError("기타 API Model이 비어 있습니다. [기타 API 설정]에서 입력해주세요.")
        key = self._resolve_key()
        if self.api_key_required and not key:
            raise RuntimeError("기타 API Key가 입력되지 않았습니다. [API Key 수동 입력]을 사용해주세요.")
        return key

    @staticmethod
    def _data_url(path: Path) -> tuple[str, str]:
        data = path.read_bytes()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if not mime.startswith("image/"):
            raise RuntimeError(f"지원하지 않는 이미지 MIME Type: {mime} ({path.name})")
        encoded = base64.b64encode(data).decode("ascii")
        return mime, f"data:{mime};base64,{encoded}"

    def _effective_auth_mode(self) -> str:
        if self.auth_mode and self.auth_mode != "auto":
            return self.auth_mode
        if self.profile == "anthropic_messages":
            return "x-api-key"
        if self.profile == "gemini_generate_content":
            return "query_key"
        return "bearer"

    def _request_auth(self, key: str) -> tuple[dict[str, str], dict[str, str] | None]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        params: dict[str, str] = {}
        mode = self._effective_auth_mode()
        name = self.api_key_name
        if key and mode == "bearer":
            headers[name or "Authorization"] = f"Bearer {key}"
        elif key and mode == "x-api-key":
            headers[name or "x-api-key"] = key
        elif key and mode == "query_key":
            params[name or "key"] = key
        elif mode not in ("none", "auto"):
            raise RuntimeError(f"지원하지 않는 인증 방식: {mode}")
        if self.version_header_name and self.version_header_value:
            headers[self.version_header_name] = self.version_header_value
        return headers, (params or None)

    def _openai_endpoint(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return base + "/chat/completions"

    def _responses_endpoint(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/responses"):
            return base
        return base + "/responses"

    def _anthropic_endpoint(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/v1/messages") or base.endswith("/messages"):
            return base
        if base.endswith("/v1"):
            return base + "/messages"
        return base + "/v1/messages"

    def _gemini_endpoint(self) -> str:
        base = self.base_url.rstrip("/")
        if ":generateContent" in base:
            return base
        if "/models/" in base:
            return base + ("" if base.endswith(":generateContent") else ":generateContent")
        return f"{base}/models/{self.model}:generateContent"

    @staticmethod
    def _extract_openai_text(payload: dict) -> str:
        try:
            content = payload["choices"][0]["message"]["content"]
        except Exception as exc:
            raise RuntimeError("OpenAI 호환 응답에서 choices[0].message.content를 찾지 못했습니다.") from exc
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            pieces = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if text:
                        pieces.append(str(text))
            return "\n".join(pieces)
        return str(content or "")

    @staticmethod
    def _extract_responses_text(payload: dict) -> str:
        if isinstance(payload.get("output_text"), str) and payload.get("output_text"):
            return str(payload["output_text"])
        pieces: list[str] = []
        for item in payload.get("output") or []:
            if not isinstance(item, dict):
                continue
            for part in item.get("content") or []:
                if isinstance(part, dict) and part.get("type") in ("output_text", "text") and part.get("text"):
                    pieces.append(str(part["text"]))
        if not pieces:
            raise RuntimeError("OpenAI Responses 호환 응답에서 output_text를 찾지 못했습니다.")
        return "\n".join(pieces)

    @staticmethod
    def _extract_anthropic_text(payload: dict) -> str:
        parts = payload.get("content") or []
        texts = []
        for item in parts:
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                texts.append(str(item["text"]))
        if not texts:
            raise RuntimeError("Anthropic 응답에서 text content를 찾지 못했습니다.")
        return "\n".join(texts)

    @staticmethod
    def _extract_gemini_text(payload: dict) -> str:
        texts = []
        for candidate in payload.get("candidates") or []:
            content = candidate.get("content") or {}
            for part in content.get("parts") or []:
                if isinstance(part, dict) and part.get("text"):
                    texts.append(str(part["text"]))
        if not texts:
            raise RuntimeError("Gemini 응답에서 candidates[].content.parts[].text를 찾지 못했습니다.")
        return "\n".join(texts)

    def _post(self, url: str, key: str, payload: dict[str, Any], timeout: int):
        headers, params = self._request_auth(key)
        response = requests.post(url, headers=headers, params=params, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()

    def generate(
        self,
        user_prompt: str,
        *,
        system_message: str = "",
        timeout_seconds: int | None = None,
        progress_callback: ProgressCallback = None,
    ) -> str:
        key = self._require_ready()
        timeout = int(timeout_seconds or self.timeout_seconds)

        if self.profile == "openai_compatible":
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": user_prompt})
            payload = self._post(self._openai_endpoint(), key, {"model": self.model, "messages": messages}, timeout)
            text = self._extract_openai_text(payload)

        elif self.profile == "openai_responses":
            request: dict[str, Any] = {"model": self.model, "input": user_prompt}
            if system_message:
                request["instructions"] = system_message
            payload = self._post(self._responses_endpoint(), key, request, timeout)
            text = self._extract_responses_text(payload)

        elif self.profile == "anthropic_messages":
            request = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": [{"role": "user", "content": user_prompt}],
            }
            if system_message:
                request["system"] = system_message
            payload = self._post(self._anthropic_endpoint(), key, request, timeout)
            text = self._extract_anthropic_text(payload)

        elif self.profile == "gemini_generate_content":
            request = {"contents": [{"role": "user", "parts": [{"text": user_prompt}]}]}
            if system_message:
                request["systemInstruction"] = {"parts": [{"text": system_message}]}
            payload = self._post(self._gemini_endpoint(), key, request, timeout)
            text = self._extract_gemini_text(payload)
        else:
            raise RuntimeError(f"지원하지 않는 기타 API 형식: {self.profile}")

        if not (text or "").strip():
            raise RuntimeError("기타 API가 빈 응답을 반환했습니다.")
        return text.strip()

    def generate_with_images(
        self,
        user_prompt: str,
        image_paths,
        *,
        system_message: str = "",
        timeout_seconds: int | None = None,
    ) -> str:
        if not self.supports_image_input:
            return super().generate_with_images(
                user_prompt,
                image_paths,
                system_message=system_message,
                timeout_seconds=timeout_seconds,
            )

        key = self._require_ready()
        timeout = int(timeout_seconds or self.timeout_seconds)
        paths = [Path(p) for p in (image_paths or [])]
        if not paths:
            raise RuntimeError("Vision 요청에 사용할 이미지가 없습니다.")

        if self.profile == "openai_compatible":
            content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
            for path in paths:
                _mime, data_url = self._data_url(path)
                content.append({"type": "image_url", "image_url": {"url": data_url}})
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": content})
            payload = self._post(self._openai_endpoint(), key, {"model": self.model, "messages": messages}, timeout)
            text = self._extract_openai_text(payload)

        elif self.profile == "openai_responses":
            content: list[dict[str, Any]] = [{"type": "input_text", "text": user_prompt}]
            for path in paths:
                _mime, data_url = self._data_url(path)
                content.append({"type": "input_image", "image_url": data_url})
            request: dict[str, Any] = {
                "model": self.model,
                "input": [{"role": "user", "content": content}],
            }
            if system_message:
                request["instructions"] = system_message
            payload = self._post(self._responses_endpoint(), key, request, timeout)
            text = self._extract_responses_text(payload)

        elif self.profile == "anthropic_messages":
            content: list[dict[str, Any]] = []
            for path in paths:
                mime, data_url = self._data_url(path)
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime,
                        "data": data_url.split(",", 1)[1],
                    },
                })
            content.append({"type": "text", "text": user_prompt})
            request = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": [{"role": "user", "content": content}],
            }
            if system_message:
                request["system"] = system_message
            payload = self._post(self._anthropic_endpoint(), key, request, timeout)
            text = self._extract_anthropic_text(payload)

        elif self.profile == "gemini_generate_content":
            parts: list[dict[str, Any]] = [{"text": user_prompt}]
            for path in paths:
                mime, data_url = self._data_url(path)
                parts.append({"inlineData": {"mimeType": mime, "data": data_url.split(",", 1)[1]}})
            request = {"contents": [{"role": "user", "parts": parts}]}
            if system_message:
                request["systemInstruction"] = {"parts": [{"text": system_message}]}
            payload = self._post(self._gemini_endpoint(), key, request, timeout)
            text = self._extract_gemini_text(payload)
        else:
            raise RuntimeError(f"지원하지 않는 기타 API 형식: {self.profile}")

        if not (text or "").strip():
            raise RuntimeError("기타 API Vision이 빈 응답을 반환했습니다.")
        return text.strip()

    def test_connection(self, progress_callback: ProgressCallback = None) -> str:
        def emit(percent: int, message: str):
            if progress_callback:
                progress_callback(percent, message)

        emit(10, "기타 API 설정 확인")
        self._require_ready()
        emit(35, f"API 형식 확인: {self.PROFILE_LABELS.get(self.profile, self.profile)}")
        emit(55, "연결 요청 전송")
        response = self.generate(
            "연결 상태 확인입니다. 정상 수신했다면 CUSTOM_API_OK 라고 한 줄로만 답변하세요.",
            system_message="불필요한 설명 없이 요청한 결과만 출력하세요.",
            timeout_seconds=min(self.timeout_seconds, 60),
        )
        emit(95, "응답 수신 완료")
        return response
