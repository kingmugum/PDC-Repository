from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path


class AliraClient:
    """ALIRA CLI를 Headless 모드로 호출하는 앱용 클라이언트."""

    def __init__(
        self,
        project_root: Path,
        model: str = "hosted_vllm/Qwen/Qwen3.6-27B",
        api_base: str = "http://10.10.10.200:19640/v1",
        timeout_seconds: int = 600,
    ):
        self.project_root = Path(project_root).resolve()

        local_app_data = os.environ.get("LOCALAPPDATA", "")
        self.exe_path = Path(local_app_data) / "Programs" / "alira" / "alira.exe"

        self.model = model
        self.api_base = api_base
        self.timeout_seconds = timeout_seconds

    def exe_exists(self) -> bool:
        return self.exe_path.is_file()

    def ask(self, prompt: str) -> str:
        return self.run_prompt(prompt, agent_type="general_agent")

    def run_prompt(
        self,
        prompt: str,
        *,
        agent_type: str = "general_agent",
        timeout_seconds: int | None = None,
    ) -> str:
        return self._run(
            prompt=prompt,
            agent_type=agent_type,
            cwd=self.project_root,
            disable_permissions=False,
            timeout_seconds=timeout_seconds,
        )

    def test_connection(self, progress_callback=None) -> str:
        """
        앱 시작/수동 재확인용 실제 ALIRA → Qwen 연결 테스트.

        percent는 원격 모델의 정확한 처리율이 아니라,
        앱이 확인 가능한 연결 단계의 진행률이다.
        """

        def emit(percent: int, message: str):
            if progress_callback:
                progress_callback(percent, message)

        timeout_seconds = min(self.timeout_seconds, 60)

        emit(5, "ALIRA 실행 환경 확인")
        if not self.exe_exists():
            raise FileNotFoundError(
                f"ALIRA 실행 파일을 찾을 수 없습니다: {self.exe_path}"
            )

        emit(15, "ALIRA 실행 파일 확인 완료")

        if not self.model or not self.api_base:
            raise RuntimeError("ALIRA Model 또는 API Base 설정이 비어 있습니다.")

        emit(25, "Model / API Base 설정 확인 완료")

        prompt = (
            "ALIRA 연결 상태 확인 요청입니다. "
            "요청을 정상적으로 받았다면 'ALIRA_OK'라고 한 줄로만 답변하세요."
        )

        command = [
            str(self.exe_path),
            "--model",
            self.model,
            "--api-base",
            self.api_base,
            "--agent-type",
            "general_agent",
            "--cwd",
            str(self.project_root),
            "-p",
            prompt,
        ]

        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        emit(40, "ALIRA Headless 연결 요청 준비 완료")

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
                cwd=str(self.project_root),
            )
        except Exception as exc:
            raise RuntimeError(
                f"ALIRA 프로세스 시작에 실패했습니다: {exc}"
            ) from exc

        emit(55, "ALIRA 프로세스 시작 완료")
        emit(65, "사내 Qwen 연결 요청 전송 완료")

        started = time.monotonic()
        last_wait_report = -999.0

        while True:
            try:
                stdout, stderr = process.communicate(timeout=1)
                break
            except subprocess.TimeoutExpired:
                elapsed = time.monotonic() - started

                if elapsed >= timeout_seconds:
                    process.kill()
                    process.communicate()
                    raise RuntimeError(
                        f"ALIRA 응답 대기 시간이 {timeout_seconds}초를 초과했습니다."
                    )

                # 65~88%는 응답 대기 구간을 나타내는 단계 기반 진행률.
                percent = min(
                    88,
                    65 + int((elapsed / timeout_seconds) * 23),
                )

                if elapsed - last_wait_report >= 4:
                    emit(
                        percent,
                        f"사내 Qwen 응답 대기 중... {int(elapsed)}초 경과",
                    )
                    last_wait_report = elapsed

        stdout = (stdout or "").strip()
        stderr = (stderr or "").strip()

        emit(92, "ALIRA 응답 수신 완료")

        if process.returncode != 0:
            details = stderr or stdout or "세부 오류 메시지가 없습니다."
            raise RuntimeError(
                "ALIRA 실행에 실패했습니다.\n\n"
                f"Exit code: {process.returncode}\n"
                f"{details}"
            )

        if not stdout:
            if stderr:
                raise RuntimeError(
                    "ALIRA가 정상 종료되었지만 stdout 응답이 없습니다.\n\n"
                    f"stderr:\n{stderr}"
                )
            raise RuntimeError("ALIRA가 빈 응답을 반환했습니다.")

        emit(97, "응답 상태 검증 완료")
        return stdout

    def analyze_document(self, document_path: Path) -> str:
        document_path = Path(document_path).resolve()

        try:
            relative_path = document_path.relative_to(self.project_root)
        except ValueError as exc:
            raise RuntimeError(
                "분석 문서는 프로젝트 폴더 내부에 있어야 합니다."
            ) from exc

        prompt = f"""
분석 대상 문서: {relative_path.as_posix()}

위 문서를 실제로 읽고 분석하세요.
아직 요구사항 명세서를 생성하거나 요구사항을 재작성하지 마세요.

다음 항목을 한글로 정리하세요.

1. 문서명 및 문서 형식
2. 문서의 목적
3. 주요 장/절 또는 문서 구조
4. 핵심 내용 요약
5. 요구사항으로 판단될 수 있는 내용이 존재하는 영역
6. 추가 확인이 필요하거나 문서만으로 판단하기 어려운 부분

원칙:
- 반드시 제공된 문서 내용만 근거로 분석하세요.
- 문서에 없는 내용은 추정하거나 만들어내지 마세요.
- 읽지 못한 부분이나 해석이 불확실한 부분은 명확히 표시하세요.
- 이번 단계에서는 요구사항을 새로 생성하지 마세요.
""".strip()

        return self._run(
            prompt=prompt,
            agent_type="document_analyzer",
            cwd=self.project_root,
            disable_permissions=True,
        )

    def extract_requirements(self, document_path: Path) -> str:
        document_path = Path(document_path).resolve()

        try:
            relative_path = document_path.relative_to(self.project_root)
        except ValueError as exc:
            raise RuntimeError(
                "요구사항 추출 문서는 프로젝트 폴더 내부에 있어야 합니다."
            ) from exc

        prompt = f"""
현재 요구사항 추출 대상 문서:
{relative_path.as_posix()}

다음 프로젝트 파일을 먼저 읽고 적용하세요.
- policy/requirement_judgment_policy.json
- policy/protected_invariants.json
- contracts/canonical_requirement_schema.json
- reference_library/reference_examples.json

핵심:
- 현재 문서가 factual Source of Truth입니다.
- Reference는 형식/패턴 참고용일 뿐 현재 문서의 사실을 보충하는 데이터가 아닙니다.
- 요구사항 개수를 미리 정하지 마세요.
- Explicit와 Implicit을 정책에 따라 모두 판단하되 별도로 표시하세요.
- 시험 가능한 Atomic behavior 기준으로 분리하세요.
- 부족한 정보는 만들어내지 말고 clarification_needed 및 gaps에 기록하세요.
- 모든 요구사항에 source document / location / text 근거를 남기세요.
- 이번 버전에서는 최종 SWE.6 Test Case를 생성하지 마세요.
- `REQ-STUDIO-CANONICAL-REQ-1.0` JSON object 하나만 반환하세요.
""".strip()

        return self._run(
            prompt=prompt,
            agent_type="requirement_extractor",
            cwd=self.project_root,
            disable_permissions=True,
        )

    def _run(
        self,
        prompt: str,
        agent_type: str,
        cwd: Path,
        disable_permissions: bool,
        timeout_seconds: int | None = None,
    ) -> str:
        if not self.exe_exists():
            raise FileNotFoundError(
                f"ALIRA 실행 파일을 찾을 수 없습니다: {self.exe_path}"
            )

        command = [
            str(self.exe_path),
            "--model",
            self.model,
            "--api-base",
            self.api_base,
            "--agent-type",
            agent_type,
            "--cwd",
            str(cwd),
        ]

        if disable_permissions:
            command.append("--no-permission-enabled")

        command.extend(["-p", prompt])

        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        effective_timeout = timeout_seconds or self.timeout_seconds

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=effective_timeout,
                creationflags=creationflags,
                cwd=str(cwd),
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"ALIRA 응답 대기 시간이 {effective_timeout}초를 초과했습니다."
            ) from exc

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if result.returncode != 0:
            details = stderr or stdout or "세부 오류 메시지가 없습니다."
            raise RuntimeError(
                "ALIRA 실행에 실패했습니다.\n\n"
                f"Exit code: {result.returncode}\n"
                f"{details}"
            )

        if not stdout:
            if stderr:
                raise RuntimeError(
                    "ALIRA가 정상 종료되었지만 stdout 응답이 없습니다.\n\n"
                    f"stderr:\n{stderr}"
                )
            return "(ALIRA가 빈 응답을 반환했습니다.)"

        return stdout
