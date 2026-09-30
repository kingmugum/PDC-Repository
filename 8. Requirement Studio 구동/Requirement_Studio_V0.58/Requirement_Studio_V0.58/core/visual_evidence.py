from __future__ import annotations

import json
import re
from pathlib import Path


VISION_SYSTEM_MESSAGE = (
    "당신은 자동차/소프트웨어 사양 문서의 그림과 도식을 분석하는 Vision Assistant입니다. "
    "이미지에서 직접 확인되는 사실과 의미 해석, 확인할 수 없는 사항을 엄격히 분리하세요. "
    "보이지 않는 신호명, 수치, 통신방식, 제어주기, 방향, 상태값을 추측하여 확정하지 마세요. "
    "반환은 Markdown 없이 JSON object 하나만 출력하세요."
)


def build_visual_prompt(visual: dict) -> str:
    visual_id = visual.get("visual_id") or "IMG"
    locator = visual.get("source_locator") or visual.get("source") or "unknown"
    return f"""다음 사양서 이미지를 직접 보고 Visual Evidence를 생성하세요.

[VISUAL_ID] {visual_id}
[SOURCE_LOCATOR] {locator}

반드시 아래 JSON 구조만 반환하세요.
{{
  "visual_id": "{visual_id}",
  "observed": ["이미지에서 직접 확인되는 객체/텍스트/선/화살표/배치 사실"],
  "interpreted": ["자동차 제어기/사양 관점에서 합리적으로 해석 가능한 의미. 단, 해석임을 유지"],
  "not_confirmed": ["이미지만으로 확정할 수 없는 신호명/수치/통신방식/방향/조건"],
  "summary": "한두 문장 요약"
}}

규칙:
- observed에는 실제로 보이는 내용만 작성하세요.
- interpreted에는 가능성/의미 해석만 작성하세요.
- not_confirmed에는 확정 불가능한 사항을 명확히 적으세요.
- 이미지에 없는 사실은 만들지 마세요.
""".strip()


def _strip_fence(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*```$", "", value)
    return value.strip()


def parse_visual_response(raw: str, visual: dict) -> dict:
    visual_id = visual.get("visual_id") or "IMG"
    value = _strip_fence(raw)
    try:
        data = json.loads(value)
        if not isinstance(data, dict):
            raise ValueError("Vision response root is not an object")
    except Exception:
        # Preserve useful text without pretending it is verified structure.
        data = {
            "visual_id": visual_id,
            "observed": [],
            "interpreted": [],
            "not_confirmed": ["Vision 응답을 구조화 JSON으로 해석하지 못했습니다."],
            "summary": value[:4000],
            "parse_status": "raw_fallback",
        }

    def as_list(key: str) -> list[str]:
        item = data.get(key, [])
        if isinstance(item, list):
            return [str(x).strip() for x in item if str(x).strip()]
        if item in (None, ""):
            return []
        return [str(item).strip()]

    result = {
        "visual_id": visual_id,
        "source_locator": visual.get("source_locator") or visual.get("source") or "",
        "image_path": visual.get("extracted_path") or "",
        "mime_type": visual.get("mime_type") or "",
        "sha256": visual.get("sha256") or "",
        "byte_size": visual.get("byte_size") or 0,
        "status": "analyzed",
        "observed": as_list("observed"),
        "interpreted": as_list("interpreted"),
        "not_confirmed": as_list("not_confirmed"),
        "summary": str(data.get("summary") or "").strip(),
    }
    if data.get("parse_status"):
        result["parse_status"] = data["parse_status"]
    return result


def evidence_block(item: dict) -> str:
    return (
        f"[VISUAL {item.get('visual_id')} | {item.get('source_locator')} | status={item.get('status')}]\n"
        f"Observed: {json.dumps(item.get('observed', []), ensure_ascii=False)}\n"
        f"Interpreted: {json.dumps(item.get('interpreted', []), ensure_ascii=False)}\n"
        f"Not Confirmed: {json.dumps(item.get('not_confirmed', []), ensure_ascii=False)}\n"
        f"Summary: {item.get('summary', '')}"
    )


def save_visual_evidence(path: Path, items: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"visual_evidence": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
