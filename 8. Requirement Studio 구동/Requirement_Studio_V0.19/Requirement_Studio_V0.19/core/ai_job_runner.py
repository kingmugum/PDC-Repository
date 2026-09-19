
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from core.document_normalizer import DocumentNormalizer, NormalizedDocument
from core.prompt_builder import PromptBuilder, PromptPart
from core.requirement_engine import RequirementEngine
from providers.base import AIProvider

StageCallback = Optional[Callable[[int, str], None]]
ProgressCallback = Optional[Callable[[int, int, str], None]]
LogCallback = Optional[Callable[[str], None]]
CancelCallback = Optional[Callable[[], bool]]


class PipelineCancelledError(RuntimeError):
    pass


class AIJobRunner:
    STAGES = {
        1: "입력/환경 확인",
        2: "문서 정규화",
        3: "분석 요청 생성",
        4: "문서 분석",
        5: "요구사항 추출",
        6: "결과 검증",
        7: "결과 저장",
    }
    STAGE_WEIGHTS = {1: 6, 2: 14, 3: 10, 4: 20, 5: 28, 6: 12, 7: 10}

    def __init__(self, project_root: Path, provider: AIProvider, normalizer: DocumentNormalizer, prompt_builder: PromptBuilder, requirement_engine: RequirementEngine):
        self.root = Path(project_root).resolve()
        self.provider = provider
        self.normalizer = normalizer
        self.prompt_builder = prompt_builder
        self.requirement_engine = requirement_engine
        self.request_dir = self.root / "work" / "ai_requests"
        self.response_dir = self.root / "work" / "ai_responses"
        self.request_dir.mkdir(parents=True, exist_ok=True)
        self.response_dir.mkdir(parents=True, exist_ok=True)
        self.last_normalized: NormalizedDocument | None = None

    def _ensure_not_cancelled(self, cancel_callback: CancelCallback, log_callback: LogCallback = None):
        if cancel_callback and cancel_callback():
            if log_callback:
                log_callback("사용자 중지 요청 감지 · 안전한 중단 지점에서 작업을 종료합니다.")
            raise PipelineCancelledError("사용자 중지 요청으로 작업이 중지되었습니다.")

    def _exchange_name(self, source: Path, kind: str, part: PromptPart) -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{stamp}_{kind}_{source.stem}_p{part.part_index:02d}of{part.part_count:02d}"

    def _call(self, source: Path, kind: str, part: PromptPart) -> str:
        base = self._exchange_name(source, kind, part)
        req_path = self.request_dir / f"{base}.txt"
        rsp_path = self.response_dir / f"{base}.txt"
        req_path.write_text(f"[SYSTEM]\n{part.system_message}\n\n[USER]\n{part.user_prompt}", encoding="utf-8")
        response = self.provider.generate(part.user_prompt, system_message=part.system_message)
        tmp = rsp_path.with_suffix(rsp_path.suffix + ".tmp")
        tmp.write_text(response, encoding="utf-8")
        tmp.replace(rsp_path)
        return response

    def normalize_only(self, document: Path) -> NormalizedDocument:
        self.last_normalized = self.normalizer.normalize(document)
        return self.last_normalized

    def run_analysis_and_requirements(self, document: Path, *, stage_callback: StageCallback = None, progress_callback: ProgressCallback = None, log_callback: LogCallback = None, cancel_callback: CancelCallback = None) -> dict:
        def stage(no: int):
            title = self.STAGES[no]
            self._ensure_not_cancelled(cancel_callback, log_callback)
            if stage_callback:
                stage_callback(no, title)
            log(f"STEP {no} 시작 · {title}")
            report(no, 0, f"{title} 시작")

        def report(no: int, current: int, message: str):
            current = max(0, min(100, int(current)))
            previous = sum(self.STAGE_WEIGHTS[i] for i in range(1, no))
            overall = previous + round(self.STAGE_WEIGHTS[no] * current / 100)
            overall = max(0, min(100, int(overall)))
            if progress_callback:
                progress_callback(overall, current, message)

        def finish_stage(no: int, message: str):
            report(no, 100, message)
            log(f"STEP {no} 완료 · {message}")

        def log(message: str):
            if log_callback:
                log_callback(message)

        document = Path(document).resolve()

        stage(1)
        if not document.is_file():
            raise FileNotFoundError(document)
        meta = self.provider.metadata()
        report(1, 45, f"입력 문서 확인: {document.name}")
        if not meta.model:
            raise RuntimeError("선택된 AI Model 정보가 없습니다.")
        report(1, 80, f"AI Provider 확인: {meta.display_name} / {meta.model}")
        finish_stage(1, "입력 문서와 AI 선택 확인")

        stage(2)
        report(2, 15, "원본 문서 읽기 시작")
        normalized = self.normalize_only(document)
        report(2, 75, f"Document IR 생성: {len(normalized.chunks)} chunks")
        if normalized.visual_assets:
            log(f"시각 요소 {len(normalized.visual_assets)}개 감지 · 현재 Text 경로에서는 직접 전송하지 않음")
        finish_stage(2, "로컬 문서 정규화 완료")

        self._ensure_not_cancelled(cancel_callback, log_callback)
        stage(3)
        analysis_parts = self.prompt_builder.build_analysis(normalized)
        req_parts = self.prompt_builder.build_requirement_extraction(normalized)
        report(3, 55, f"분석 요청 {len(analysis_parts)}개 생성")
        report(3, 85, f"요구사항 요청 {len(req_parts)}개 생성")
        finish_stage(3, "Compact AI 요청 생성 완료")

        self._ensure_not_cancelled(cancel_callback, log_callback)
        stage(4)
        analysis_answers: list[str] = []
        total = max(1, len(analysis_parts))
        for idx, part in enumerate(analysis_parts, start=1):
            self._ensure_not_cancelled(cancel_callback, log_callback)
            before = round(((idx - 1) / total) * 80) + 5
            report(4, before, f"문서 분석 AI 요청 {idx}/{total} 전송 · 응답 대기")
            log(f"분석 요청 {idx}/{total} → {meta.display_name}")
            analysis_answers.append(self._call(document, "analysis", part))
            after = round((idx / total) * 90)
            report(4, after, f"문서 분석 응답 {idx}/{total} 수신")
        analysis_text = analysis_answers[0] if len(analysis_answers) == 1 else "\n\n".join(f"=== Analysis Part {idx}/{len(analysis_answers)} ===\n{text}" for idx, text in enumerate(analysis_answers, start=1))
        finish_stage(4, "문서 분석 완료")

        self._ensure_not_cancelled(cancel_callback, log_callback)
        stage(5)
        parsed: list[dict] = []
        raw_errors: list[str] = []
        total = max(1, len(req_parts))
        for idx, part in enumerate(req_parts, start=1):
            self._ensure_not_cancelled(cancel_callback, log_callback)
            before = round(((idx - 1) / total) * 80) + 5
            report(5, before, f"요구사항 추출 AI 요청 {idx}/{total} 전송 · 응답 대기")
            log(f"요구사항 추출 요청 {idx}/{total} → {meta.display_name}")
            raw = self._call(document, "requirements", part)
            try:
                parsed.append(self.requirement_engine.extract_json(raw))
            except Exception as exc:
                raw_errors.append(f"Part {idx}/{total}: {exc}\n\n{raw}")
            after = round((idx / total) * 90)
            report(5, after, f"요구사항 응답 {idx}/{total} 수신")
        if raw_errors:
            raise RuntimeError("일부 Requirement 응답을 Canonical JSON으로 해석하지 못했습니다.\n\n" + "\n\n---\n\n".join(raw_errors))
        finish_stage(5, "Requirement Candidate 추출 완료")

        self._ensure_not_cancelled(cancel_callback, log_callback)
        stage(6)
        report(6, 30, "Chunk별 Requirement 결과 병합")
        merged = self.requirement_engine.merge_results(parsed, source_document=normalized.source_document)
        report(6, 70, "Canonical Requirement 구조 검사")
        evaluation = self.requirement_engine.evaluate_structure(merged)
        finish_stage(6, f"구조 검사 완료 · {evaluation['structure_score']}/100")

        self._ensure_not_cancelled(cancel_callback, log_callback)
        stage(7)
        report(7, 30, "Canonical Requirement JSON 저장")
        saved_path = self.requirement_engine.save_result(document, merged)
        report(7, 70, "결과 화면 데이터 준비")
        finish_stage(7, "분석 & 요구사항 추출 완료")

        return {
            "analysis_text": analysis_text,
            "requirement_data": merged,
            "evaluation": evaluation,
            "saved_path": str(saved_path),
            "normalized": {
                "source_document": normalized.source_document,
                "source_type": normalized.source_type,
                "chunk_count": len(normalized.chunks),
                "visual_count": len(normalized.visual_assets),
                "total_chars": normalized.total_chars,
            },
        }
