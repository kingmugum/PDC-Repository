from __future__ import annotations

import json
import time
from pathlib import Path

from providers.base import AIProvider, ProviderMetadata, ProgressCallback
from providers.hchat_credentials import resolve_external_api_key

try:
    import requests
except Exception:
    requests = None

try:
    from openai import AzureOpenAI
except Exception:
    AzureOpenAI = None


class HChatProvider(AIProvider):
    """
    H-Chat API Adapter.

    API 형식은 검증된 Signal Export V2 Step 5 구조를 그대로 참고한다.
    - GPT: AzureOpenAI(azure_endpoint=H-Chat base URL)
    - Gemini: POST /models/{model}:{generateContent}
    - API Key: 프로젝트 Root의 API_Key류 txt 최신 파일 자동 탐색
    """

    def __init__(self, project_root: Path, config: dict, backend: str = "gpt"):
        self.project_root = Path(project_root).resolve()
        self.config = config
        self.backend = (backend or config.get("backend") or "gpt").lower()
        self.base_url = str(config.get("base_url") or "").rstrip("/")
        self.project_id = str(config.get("project_id") or "").strip()
        self.api_version = str(config.get("api_version") or "2025-04-01-preview")
        self.gpt_model = str(config.get("gpt_model") or "gpt-5.6-terra")
        self.gemini_model = str(config.get("gemini_model") or "gemini-3.1-pro-preview")
        self.gemini_stream_option = str(config.get("gemini_stream_option") or "generateContent")
        self.timeout_seconds = int(config.get("timeout_seconds") or 120)
        self.max_retry = int(config.get("max_retry") or 3)
        self.retry_wait_seconds = float(config.get("retry_wait_seconds") or 2.0)
        # Runtime-only manual key. GUI가 메모리로만 주입하며 config 파일에는 저장하지 않는다.
        self.manual_api_key = str(config.get("manual_api_key") or "").strip()

    @property
    def provider_id(self) -> str:
        return "hchat_gemini" if self.backend == "gemini" else "hchat_gpt"

    @property
    def display_name(self) -> str:
        return "H-Chat / Gemini" if self.backend == "gemini" else "H-Chat / GPT"

    @property
    def model(self) -> str:
        return self.gemini_model if self.backend == "gemini" else self.gpt_model

    def _resolve_key(self) -> tuple[str, str]:
        if self.manual_api_key:
            return self.manual_api_key, "수동 입력됨"
        key, _path, display = resolve_external_api_key(self.project_root)
        return key, display

    def metadata(self) -> ProviderMetadata:
        _key, display = self._resolve_key()
        return ProviderMetadata(
            provider_id=self.provider_id,
            display_name=self.display_name,
            model=self.model,
            api_base=self.base_url,
            credential_status=display,
            supports_text=True,
            supports_images=False,
            supports_files=False,
        )

    def _create_gpt_client(self, api_key: str):
        if AzureOpenAI is None:
            raise ImportError("openai 패키지가 설치되지 않았습니다.")
        headers = {}
        if self.project_id:
            headers["X-Project-Id"] = self.project_id
        return AzureOpenAI(
            azure_endpoint=self.base_url,
            api_key=api_key,
            api_version=self.api_version,
            default_headers=headers if headers else None,
        )

    @staticmethod
    def _extract_gemini_text(resp_json: dict) -> str:
        candidates = resp_json.get("candidates") or []
        if candidates:
            content = (candidates[0] or {}).get("content") or {}
            parts = content.get("parts") or []
            texts = [p.get("text") for p in parts if isinstance(p, dict) and p.get("text")]
            if texts:
                return "".join(texts)
        for key in ("outputText", "text", "result"):
            if isinstance(resp_json.get(key), str):
                return resp_json[key]
        return json.dumps(resp_json, ensure_ascii=False)

    def _ask_once(self, user_prompt: str, system_message: str, api_key: str, timeout_seconds: int) -> str:
        if self.backend == "gpt":
            client = self._create_gpt_client(api_key)
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": user_prompt})
            completion = client.chat.completions.create(
                model=self.gpt_model,
                messages=messages,
                timeout=timeout_seconds,
            )
            content = completion.choices[0].message.content
            return content if content is not None else ""

        if self.backend == "gemini":
            if requests is None:
                raise ImportError("requests 패키지가 설치되지 않았습니다.")
            url = f"{self.base_url}/models/{self.gemini_model}:{self.gemini_stream_option}"
            params = {"key": api_key}
            headers = {"Content-Type": "application/json"}
            if self.project_id:
                headers["X-Project-Id"] = self.project_id
            payload = {
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}]
            }
            if system_message:
                payload["systemInstruction"] = {"parts": [{"text": system_message}]}
            response = requests.post(
                url,
                params=params,
                headers=headers,
                json=payload,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            return self._extract_gemini_text(response.json())

        raise ValueError(f"지원하지 않는 H-Chat backend: {self.backend}")

    def generate(
        self,
        user_prompt: str,
        *,
        system_message: str = "",
        timeout_seconds: int | None = None,
    ) -> str:
        api_key, _display = self._resolve_key()
        if not api_key:
            raise RuntimeError(
                "H-Chat API KEY가 감지되지 않았습니다. "
                "Requirement Studio의 api_keys 폴더(또는 Root)에 API_Key류 txt 파일을 두거나 "
                "[API Key 수동 입력]으로 입력한 뒤 다시 연결 테스트해주세요."
            )
        effective_timeout = int(timeout_seconds or self.timeout_seconds)
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retry + 1):
            try:
                text = self._ask_once(
                    user_prompt,
                    system_message,
                    api_key,
                    effective_timeout,
                )
                if not (text or "").strip():
                    raise RuntimeError("H-Chat이 빈 응답을 반환했습니다.")
                return text.strip()
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retry:
                    time.sleep(self.retry_wait_seconds)
        raise RuntimeError(
            f"H-Chat API 호출이 {self.max_retry}회 모두 실패했습니다: {last_exc}"
        ) from last_exc

    def test_connection(self, progress_callback: ProgressCallback = None) -> str:
        def emit(percent: int, message: str):
            if progress_callback:
                progress_callback(percent, message)

        emit(5, "H-Chat 설정 확인")
        if not self.base_url:
            raise RuntimeError("H-Chat Base URL이 비어 있습니다.")

        api_key, display = self._resolve_key()
        emit(20, f"API Key 파일 확인: {display}")
        if not api_key:
            raise RuntimeError("H-Chat API KEY가 감지되지 않았습니다.")

        emit(35, f"Provider/Model 확인: {self.display_name} / {self.model}")
        emit(55, "H-Chat 연결 요청 전송")
        response = self.generate(
            "연결 상태 확인입니다. 정상 수신했다면 HCHAT_OK 라고 한 줄로만 답변하세요.",
            system_message="불필요한 설명 없이 요청한 결과만 출력하세요.",
            timeout_seconds=min(self.timeout_seconds, 60),
        )
        emit(92, "H-Chat 응답 수신 완료")
        if not response.strip():
            raise RuntimeError("H-Chat 연결 시험 응답이 비어 있습니다.")
        emit(97, "H-Chat 응답 상태 검증 완료")
        return response
