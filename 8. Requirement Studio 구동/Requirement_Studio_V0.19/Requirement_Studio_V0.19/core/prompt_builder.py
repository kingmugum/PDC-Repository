from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from core.document_normalizer import NormalizedDocument


@dataclass
class PromptPart:
    part_index: int
    part_count: int
    system_message: str
    user_prompt: str


class PromptBuilder:
    """Provider가 바뀌어도 동일한 업무 의미의 Prompt를 만드는 공통 계층."""

    SAFE_REQUEST_CHARS = 90000  # Signal Export의 H-Chat 안전 분할 기준을 참고

    def __init__(self, project_root: Path):
        root = Path(project_root).resolve()
        self.root = root
        self.policy_path = root / "policy" / "requirement_judgment_policy.json"
        self.invariants_path = root / "policy" / "protected_invariants.json"
        self.schema_path = root / "contracts" / "canonical_requirement_schema.json"
        self.reference_path = root / "reference_library" / "reference_examples.json"

    @staticmethod
    def _json_min(path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    def _compact_reference(self) -> dict:
        data = self._json_min(self.reference_path)
        swe1 = []
        keys = [
            "기능명", "요구사항", "사용자 입력", "시스템 입력/전제", "처리/동작",
            "출력", "판정 기준", "실패 상황", "변경 금지 조건", "확인 필요 사항",
        ]
        for item in data.get("swe1_examples", []):
            fields = item.get("fields", {})
            swe1.append({
                "project": item.get("project"),
                **{k: fields.get(k) for k in keys if fields.get(k) not in (None, "")},
            })
        swe6 = []
        for item in data.get("swe6_examples", []):
            fields = item.get("fields", {})
            swe6.append({k: v for k, v in fields.items() if v not in (None, "")})
        return {
            "purpose": data.get("purpose"),
            "swe1_examples": swe1,
            "swe6_examples": swe6,
        }

    @staticmethod
    def _blocks(doc: NormalizedDocument) -> list[str]:
        blocks = []
        max_chunk_chars = 50000
        for c in doc.chunks:
            text = c.text or ""
            if len(text) <= max_chunk_chars:
                blocks.append(f"[SRC {c.chunk_id} | {c.location} | {c.kind}]\n{text}")
                continue
            parts = [text[i:i + max_chunk_chars] for i in range(0, len(text), max_chunk_chars)]
            for idx, part in enumerate(parts, start=1):
                blocks.append(
                    f"[SRC {c.chunk_id}.S{idx} | {c.location} | {c.kind} | CONT {idx}/{len(parts)}]\n{part}"
                )
        return blocks

    @staticmethod
    def _pack(blocks: list[str], max_chars: int) -> list[str]:
        parts: list[str] = []
        current: list[str] = []
        size = 0
        for block in blocks:
            bsize = len(block) + 2
            if current and size + bsize > max_chars:
                parts.append("\n\n".join(current))
                current = []
                size = 0
            current.append(block)
            size += bsize
        if current:
            parts.append("\n\n".join(current))
        return parts or [""]

    def build_analysis(self, doc: NormalizedDocument) -> list[PromptPart]:
        system = (
            "당신은 자동차/소프트웨어 사양 문서를 분석하는 AI입니다. "
            "제공된 SOURCE 내용만 사용하고 문서에 없는 사실은 만들지 마세요."
        )
        header = (
            f"문서명: {doc.source_document}\n"
            f"문서형식: {doc.source_type}\n"
            f"그림/미디어 수: {len(doc.visual_assets)}\n\n"
            "다음 내용을 분석하세요. 아직 Requirement를 생성하지 마세요.\n"
            "1. 문서 목적\n2. 주요 구조\n3. 핵심 내용\n4. 요구사항 후보가 존재하는 영역\n"
            "5. 불명확/추가확인 필요 사항\n"
        )
        available = max(15000, self.SAFE_REQUEST_CHARS - len(header) - len(system) - 2000)
        bodies = self._pack(self._blocks(doc), available)
        return [
            PromptPart(i + 1, len(bodies), system, f"{header}\n[PART {i+1}/{len(bodies)}]\n{body}")
            for i, body in enumerate(bodies)
        ]

    def build_requirement_extraction(self, doc: NormalizedDocument) -> list[PromptPart]:
        policy = self._json_min(self.policy_path)
        invariants = self._json_min(self.invariants_path)
        schema = self._json_min(self.schema_path)
        reference = self._compact_reference()

        system = (
            "당신은 자동차/소프트웨어 Requirement Engineer입니다. "
            "현재 SOURCE가 유일한 factual Source of Truth입니다. "
            "Reference는 산출물 구조와 판단 패턴만 참고하고 도메인 사실을 복사하지 마세요. "
            "원문에 없는 수치/신호/상태/시간을 만들지 말고 부족하면 Gap/TBD로 표시하세요. "
            "반환은 Markdown 설명 없이 REQ-STUDIO-CANONICAL-REQ-1.0 JSON object 하나만 출력하세요."
        )
        context = (
            "[EDITABLE_JUDGMENT_POLICY]\n"
            + json.dumps(policy, ensure_ascii=False, separators=(",", ":"))
            + "\n\n[PROTECTED_INVARIANTS]\n"
            + json.dumps(invariants, ensure_ascii=False, separators=(",", ":"))
            + "\n\n[OUTPUT_SCHEMA]\n"
            + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
            + "\n\n[REFERENCE_EXAMPLES]\n"
            + json.dumps(reference, ensure_ascii=False, separators=(",", ":"))
            + f"\n\n[DOCUMENT_META]\nname={doc.source_document};type={doc.source_type};visuals={len(doc.visual_assets)}"
        )
        available = max(12000, self.SAFE_REQUEST_CHARS - len(context) - len(system) - 4000)
        bodies = self._pack(self._blocks(doc), available)
        prompts = []
        for i, body in enumerate(bodies):
            part_note = (
                f"[PART {i+1}/{len(bodies)}]\n"
                "이 PART에 포함된 SOURCE만 근거로 Requirement Candidate를 추출하세요. "
                "요구사항 수를 미리 정하지 말고 시험 가능한 Atomic behavior 기준으로 판단하세요. "
                "모든 Requirement에 source_evidence(document/location/text)를 넣으세요. "
                "Explicit/Implicit은 derivation_type으로 구분하고 Implicit은 derivation_reason을 작성하세요. "
                "최종 SWE.6 Test Case는 아직 생성하지 마세요."
            )
            prompts.append(PromptPart(i + 1, len(bodies), system, f"{context}\n\n{part_note}\n\n[SOURCE]\n{body}"))
        return prompts
