
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from core.document_normalizer import DocumentNormalizer, NormalizedDocument
from core.prompt_builder import PromptBuilder, PromptPart
from core.requirement_engine import RequirementEngine
from core.visual_evidence import VISION_SYSTEM_MESSAGE, build_visual_prompt, parse_visual_response, save_visual_evidence
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

    def __init__(self, project_root: Path, provider: AIProvider, normalizer: DocumentNormalizer, prompt_builder: PromptBuilder, requirement_engine: RequirementEngine, vision_provider: AIProvider | None = None):
        self.root = Path(project_root).resolve()
        self.provider = provider
        self.vision_provider = vision_provider or provider
        self.normalizer = normalizer
        self.prompt_builder = prompt_builder
        self.requirement_engine = requirement_engine
        self.request_dir = self.root / "work" / "ai_requests"
        self.response_dir = self.root / "work" / "ai_responses"
        self.failure_dir = self.root / "work" / "recovery_failures"
        self.request_dir.mkdir(parents=True, exist_ok=True)
        self.response_dir.mkdir(parents=True, exist_ok=True)
        self.failure_dir.mkdir(parents=True, exist_ok=True)
        self.last_normalized: NormalizedDocument | None = None
        self.vision_config = self._load_vision_config()

    def _load_vision_config(self) -> dict:
        path = self.root / "config" / "provider_config.json"
        defaults = {
            "enabled": True,
            "mode": "inherit_selected_provider",
            "max_images_per_document": 12,
            "max_image_bytes": 5 * 1024 * 1024,
        }
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            vision = data.get("vision") or {}
            defaults.update({k: v for k, v in vision.items() if v is not None})
        except Exception:
            pass
        return defaults

    def _call_visual(self, source: Path, visual: dict, prompt: str) -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        visual_id = visual.get("visual_id") or "IMG"
        base = f"{stamp}_vision_{source.stem}_{visual_id}"
        req_path = self.request_dir / f"{base}.txt"
        rsp_path = self.response_dir / f"{base}.txt"
        image_path = Path(str(visual.get("extracted_path") or ""))
        request_meta = (
            f"[SYSTEM]\n{VISION_SYSTEM_MESSAGE}\n\n[USER]\n{prompt}\n\n"
            f"[IMAGE_METADATA]\nvisual_id={visual_id}\npath={image_path}\n"
            f"mime={visual.get('mime_type')}\nbytes={visual.get('byte_size')}\nsha256={visual.get('sha256')}\n"
            "[IMAGE_PAYLOAD] Base64 image bytes are intentionally NOT saved in this request snapshot.\n"
        )
        req_path.write_text(request_meta, encoding="utf-8")
        response = self.vision_provider.generate_with_images(
            prompt,
            [image_path],
            system_message=VISION_SYSTEM_MESSAGE,
        )
        tmp = rsp_path.with_suffix(rsp_path.suffix + ".tmp")
        tmp.write_text(response, encoding="utf-8")
        tmp.replace(rsp_path)
        return response

    def _analyze_visual_assets(
        self,
        document: Path,
        normalized: NormalizedDocument,
        *,
        log_callback: LogCallback = None,
        cancel_callback: CancelCallback = None,
    ) -> list[dict]:
        assets = list(normalized.visual_assets or [])
        if not assets or not bool(self.vision_config.get("enabled", True)):
            return []

        def log(message: str):
            if log_callback:
                log_callback(message)

        meta = self.vision_provider.metadata()
        if not meta.supports_images:
            for item in assets:
                item["vision_status"] = "unsupported"
            log(f"시각 요소 {len(assets)}개 감지 · {meta.display_name}은 현재 선택 Provider의 Vision 경로 미지원 · Text/Table 분석 계속")
            return []

        max_images = max(0, int(self.vision_config.get("max_images_per_document", 12)))
        max_bytes = max(1, int(self.vision_config.get("max_image_bytes", 5 * 1024 * 1024)))
        supported_mimes = {"image/png", "image/jpeg", "image/webp", "image/gif"}
        evidence: list[dict] = []
        analyzed_count = 0
        skipped_count = 0
        failed_count = 0

        for item in assets:
            self._ensure_not_cancelled(cancel_callback, log_callback)
            if analyzed_count >= max_images:
                item["vision_status"] = "skipped_limit"
                skipped_count += 1
                continue
            if int(item.get("byte_size") or 0) > max_bytes:
                item["vision_status"] = "skipped_size"
                skipped_count += 1
                continue
            mime = str(item.get("mime_type") or "")
            if mime not in supported_mimes:
                item["vision_status"] = "unsupported_format"
                skipped_count += 1
                continue
            image_path = Path(str(item.get("extracted_path") or ""))
            if not image_path.is_file():
                item["vision_status"] = "missing"
                failed_count += 1
                continue

            analyzed_count += 1
            visual_id = item.get("visual_id") or f"IMG-{analyzed_count:03d}"
            log(f"Vision 분석 {analyzed_count}/{min(len(assets), max_images)} · {visual_id} · {image_path.name}")
            try:
                raw = self._call_visual(document, item, build_visual_prompt(item))
                parsed = parse_visual_response(raw, item)
                item["vision_status"] = "analyzed"
                evidence.append(parsed)
            except Exception as exc:
                item["vision_status"] = "failed"
                item["vision_error"] = str(exc)
                failed_count += 1
                log(f"Vision 분석 실패 · {visual_id} · {exc} · Text/Table 분석은 계속")

        normalized.visual_evidence = evidence
        try:
            ir_path = Path(normalized.ir_json_path)
            payload = json.loads(ir_path.read_text(encoding="utf-8")) if ir_path.is_file() else {}
            payload["visual_assets"] = normalized.visual_assets
            payload["visual_evidence"] = evidence
            ir_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            save_visual_evidence(ir_path.parent / "visual_evidence.json", evidence)
        except Exception as exc:
            log(f"Visual Evidence 로컬 저장 경고 · {exc}")

        log(
            f"Vision 처리 완료 · 분석 {len(evidence)}개 / 실패 {failed_count}개 / Skip {skipped_count}개 · "
            "본문/표와 함께 다음 분석 단계에 반영"
        )
        return evidence

    def _ensure_not_cancelled(self, cancel_callback: CancelCallback, log_callback: LogCallback = None):
        if cancel_callback and cancel_callback():
            if log_callback:
                log_callback("사용자 중지 요청 감지 · 안전한 중단 지점에서 작업을 종료합니다.")
            raise PipelineCancelledError("사용자 중지 요청으로 작업이 중지되었습니다.")

    def _exchange_name(self, source: Path, kind: str, part: PromptPart) -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return f"{stamp}_{kind}_{source.stem}_p{part.part_index:02d}of{part.part_count:02d}"

    def _call(self, source: Path, kind: str, part: PromptPart, *, log_callback: LogCallback = None) -> str:
        base = self._exchange_name(source, kind, part)
        req_path = self.request_dir / f"{base}.txt"
        rsp_path = self.response_dir / f"{base}.txt"
        req_path.write_text(f"[SYSTEM]\n{part.system_message}\n\n[USER]\n{part.user_prompt}", encoding="utf-8")
        def provider_progress(_percent: int, message: str):
            if log_callback and message:
                log_callback(message)

        response = self.provider.generate(
            part.user_prompt,
            system_message=part.system_message,
            progress_callback=provider_progress,
        )
        tmp = rsp_path.with_suffix(rsp_path.suffix + ".tmp")
        tmp.write_text(response, encoding="utf-8")
        tmp.replace(rsp_path)
        return response

    def _save_parse_failure_detail(self, source: Path, raw: str, error: Exception, *, label: str) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = self.failure_dir / f"{stamp}_{label}_{source.stem}.txt"
        body = (
            f"source={source}\n"
            f"error={error}\n"
            f"response_chars={len(raw or '')}\n\n"
            "=== RAW RESPONSE ===\n"
            + (raw or "")
        )
        path.write_text(body, encoding="utf-8")
        return path

    def _extract_requirement_with_recovery(
        self,
        document: Path,
        part: PromptPart,
        *,
        part_index: int,
        part_total: int,
        log_callback: LogCallback = None,
        cancel_callback: CancelCallback = None,
    ) -> list[dict]:
        def log(message: str):
            if log_callback:
                log_callback(message)

        raw = self._call(document, "requirements", part, log_callback=log_callback)
        try:
            return [self.requirement_engine.extract_json(raw)]
        except Exception as first_exc:
            detail_path = self._save_parse_failure_detail(document, raw, first_exc, label=f"requirements_p{part_index:02d}")
            log(
                f"Requirement JSON 파싱 실패 · Part {part_index}/{part_total} · "
                f"자동 분할 재추출 시작 · 상세 원문 보존: {detail_path.name}"
            )

        recovery_parts = self.prompt_builder.build_requirement_recovery_parts(part)
        if len(recovery_parts) <= 1:
            raise RuntimeError(
                "Requirement JSON 생성이 완전한 형태로 종료되지 않았습니다. "
                f"자동 분할이 불가능하여 중단했습니다. 상세 원문: {detail_path}"
            )

        parsed: list[dict] = []
        recovery_failures: list[str] = []
        for ridx, recovery_part in enumerate(recovery_parts, start=1):
            self._ensure_not_cancelled(cancel_callback, log_callback)
            log(f"자동 복구 재추출 {ridx}/{len(recovery_parts)} → {self.provider.metadata().display_name}")
            retry_raw = self._call(document, "requirements_recovery", recovery_part, log_callback=log_callback)
            try:
                parsed.append(self.requirement_engine.extract_json(retry_raw))
                log(f"자동 복구 재추출 {ridx}/{len(recovery_parts)} JSON 확인 완료")
            except Exception as retry_exc:
                retry_path = self._save_parse_failure_detail(
                    document, retry_raw, retry_exc, label=f"recovery_{ridx:02d}of{len(recovery_parts):02d}"
                )
                recovery_failures.append(f"{ridx}/{len(recovery_parts)}: {retry_exc} ({retry_path.name})")

        if recovery_failures:
            raise RuntimeError(
                "Requirement JSON 자동 복구에 실패했습니다. "
                f"분할 재추출 {len(recovery_parts)}개 중 {len(recovery_failures)}개 실패. "
                "전체 Raw 응답은 work/recovery_failures에 보존했습니다.\n- "
                + "\n- ".join(recovery_failures)
            )

        log(f"Requirement JSON 자동 복구 완료 · {len(recovery_parts)}개 분할 결과 병합 예정")
        return parsed


    def run_batch_analysis_and_requirements(self, documents, *, stage_callback: StageCallback = None, progress_callback: ProgressCallback = None, log_callback: LogCallback = None, cancel_callback: CancelCallback = None) -> dict:
        docs = [Path(d).resolve() for d in documents]
        if not docs:
            raise RuntimeError("분석할 입력 문서가 없습니다.")

        batch_results = []
        batch_failures = []
        total_docs = len(docs)

        def log(message: str):
            if log_callback:
                log_callback(message)

        for doc_index, document in enumerate(docs, start=1):
            self._ensure_not_cancelled(cancel_callback, log_callback)
            log(f"[{doc_index}/{total_docs}] 문서 작업 시작 · {document.name}")

            def wrapped_stage(no: int, title: str):
                if stage_callback:
                    stage_callback(no, f"[{doc_index}/{total_docs}] {title}")

            def wrapped_progress(overall: int, current: int, message: str):
                batch_overall = round((((doc_index - 1) + (overall / 100.0)) / total_docs) * 100)
                if progress_callback:
                    progress_callback(batch_overall, current, f"[{doc_index}/{total_docs}] {message}")

            try:
                result = self.run_analysis_and_requirements(
                    document,
                    stage_callback=wrapped_stage,
                    progress_callback=wrapped_progress,
                    log_callback=log_callback,
                    cancel_callback=cancel_callback,
                )
                result = dict(result)
                result["document"] = str(document)
                batch_results.append(result)
                log(f"[{doc_index}/{total_docs}] 문서 작업 완료 · {document.name}")
            except PipelineCancelledError:
                raise
            except Exception as exc:
                batch_failures.append({"document": document.name, "error": str(exc)})
                log(f"[{doc_index}/{total_docs}] 문서 작업 실패 · {document.name} · {exc}")
                if progress_callback:
                    progress_callback(round((doc_index / total_docs) * 100), 100, f"[{doc_index}/{total_docs}] 실패 후 다음 문서로 이동")

        if not batch_results:
            details = "\n".join(f"- {x['document']}: {x['error']}" for x in batch_failures)
            raise RuntimeError("모든 입력 문서 처리에 실패했습니다.\n" + details)

        if progress_callback:
            progress_callback(100, 100, "Batch 처리 완료")
        return {
            "batch_results": batch_results,
            "batch_failures": batch_failures,
            "document_count": total_docs,
        }

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
        report(2, 70, f"Document IR 생성: {len(normalized.chunks)} chunks")
        if normalized.visual_assets:
            log(f"시각 요소 {len(normalized.visual_assets)}개 추출 · work/normalized 하위 visuals 저장")
            report(2, 88, f"시각 요소 {len(normalized.visual_assets)}개 로컬 추출 완료")
        finish_stage(2, "로컬 문서 정규화 완료")

        self._ensure_not_cancelled(cancel_callback, log_callback)
        stage(3)
        if normalized.visual_assets:
            report(3, 10, "그림/도식 Vision 분석 준비")
            main_meta = self.provider.metadata()
            vision_meta = self.vision_provider.metadata()
            route_label = "Native" if main_meta.provider_id == vision_meta.provider_id else "Fallback"
            log(
                f"Vision 경로 · Main={main_meta.display_name} / {main_meta.model} · "
                f"Vision={vision_meta.display_name} / {vision_meta.model} ({route_label}) · "
                f"Credential={vision_meta.credential_status}"
            )
            self._analyze_visual_assets(
                document,
                normalized,
                log_callback=log_callback,
                cancel_callback=cancel_callback,
            )
            report(3, 45, f"Visual Evidence {len(normalized.visual_evidence)}개 준비")
            if len(normalized.visual_evidence) == 0:
                statuses = [str(x.get("vision_status") or "unknown") for x in (normalized.visual_assets or [])]
                log(
                    "⚠ Visual Evidence 0개 · 그림 내용은 후속 분석에 반영되지 않습니다. "
                    f"asset_status={statuses} · work/normalized 하위 visual_evidence.json 및 로그를 확인하세요."
                )
        analysis_parts = self.prompt_builder.build_analysis(normalized)
        req_parts = self.prompt_builder.build_requirement_extraction(normalized)
        report(3, 65, f"분석 요청 {len(analysis_parts)}개 생성")
        report(3, 90, f"요구사항 요청 {len(req_parts)}개 생성")
        finish_stage(3, "Text/Table/Visual 통합 AI 요청 생성 완료")

        self._ensure_not_cancelled(cancel_callback, log_callback)
        stage(4)
        analysis_answers: list[str] = []
        total = max(1, len(analysis_parts))
        for idx, part in enumerate(analysis_parts, start=1):
            self._ensure_not_cancelled(cancel_callback, log_callback)
            before = round(((idx - 1) / total) * 80) + 5
            report(4, before, f"문서 분석 요청 {idx}/{total} · {meta.display_name} 응답 대기")
            log(f"문서 분석 요청 {idx}/{total} 전송 → {meta.display_name}")
            analysis_answers.append(self._call(document, "analysis", part, log_callback=log_callback))
            log(f"문서 분석 응답 {idx}/{total} 수신 ← {meta.display_name}")
            after = round((idx / total) * 90)
            report(4, after, f"문서 분석 응답 {idx}/{total} 수신 · 결과 정리 중")
        analysis_text = analysis_answers[0] if len(analysis_answers) == 1 else "\n\n".join(f"=== Analysis Part {idx}/{len(analysis_answers)} ===\n{text}" for idx, text in enumerate(analysis_answers, start=1))
        finish_stage(4, "문서 분석 완료")

        self._ensure_not_cancelled(cancel_callback, log_callback)
        stage(5)
        parsed: list[dict] = []
        total = max(1, len(req_parts))
        for idx, part in enumerate(req_parts, start=1):
            self._ensure_not_cancelled(cancel_callback, log_callback)
            before = round(((idx - 1) / total) * 80) + 5
            report(5, before, f"요구사항 추출 요청 {idx}/{total} · {meta.display_name} 응답 대기")
            log(f"요구사항 추출 요청 {idx}/{total} 전송 → {meta.display_name}")
            extracted_parts = self._extract_requirement_with_recovery(
                document,
                part,
                part_index=idx,
                part_total=total,
                log_callback=log_callback,
                cancel_callback=cancel_callback,
            )
            parsed.extend(extracted_parts)
            log(f"요구사항 추출 응답 {idx}/{total} 수신 ← {meta.display_name}")
            after = round((idx / total) * 90)
            report(5, after, f"요구사항 응답 {idx}/{total} 수신 · 구조 확인 완료")
        finish_stage(5, "Requirement Candidate 추출 완료")

        self._ensure_not_cancelled(cancel_callback, log_callback)
        stage(6)
        report(6, 30, "Chunk별 Requirement 결과 병합")
        merged = self.requirement_engine.merge_results(parsed, source_document=normalized.source_document)
        report(6, 55, "Source Coverage / Reference Integrity / Review Evidence 계산")
        merged = self.requirement_engine.apply_quality_audits(merged, source_text=normalized.compact_text())
        report(6, 75, "Canonical Requirement 구조 검사")
        evaluation = self.requirement_engine.evaluate_structure(merged)
        finish_stage(6, f"구조 검사 완료 · {evaluation['structure_score']}/100")

        self._ensure_not_cancelled(cancel_callback, log_callback)
        stage(7)
        report(7, 30, "Canonical Requirement JSON 저장")
        saved_path = self.requirement_engine.save_result(document, merged)
        report(7, 70, "결과 화면 데이터 준비")
        finish_stage(7, "분석 및 요구사항 추출 완료")

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
                "visual_evidence_count": len(normalized.visual_evidence),
                "visual_evidence_path": str(Path(normalized.ir_json_path).parent / "visual_evidence.json"),
                "total_chars": normalized.total_chars,
                # Local-only normalized text is passed to deterministic exporters for conservative
                # metadata extraction. It is not a second AI result and remains Provider-independent.
                "compact_text": normalized.compact_text(),
            },
        }
