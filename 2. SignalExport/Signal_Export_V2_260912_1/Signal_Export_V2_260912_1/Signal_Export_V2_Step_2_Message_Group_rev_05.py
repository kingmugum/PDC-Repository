# -*- coding: utf-8 -*-
# [Excel Compat 연동 변경] rev05: Excel Compat rev03 공통 reader/forward-fill helper 사용
"""
[V2 STEP 2 REV 05 변경점]
- TestCase Excel TC 번호/분류 forward-fill을 Excel Compat rev03 공통 helper로 변경
- pandas FutureWarning을 제거하되 TC 매핑 결과는 기존과 동일하게 유지

Signal_Export_V2_Step_2_Message_Group_rev_03.py

목적
- DBC 파일들을 스캔하여 message_group txt 생성
- 기본 동작은 Rev01의 Rule 기반(include sender/message name + exclude) 로직을 그대로 유지
- GUI/Main의 step_2_ai_enhancement=True일 때만 선택적으로 AI 후보 보강 수행

[V2 STEP2 REV 03 변경점]
- TestCase Excel을 .xls/.xlsx/.xlsm 및 확장자-실제형식 불일치까지 공통 Excel Compat reader로 처리
- XLS는 xlrd>=2.0.1, XLSX/XLSM은 openpyxl을 실제 signature 기준으로 자동 선택
- 기존 Step 2 AI 후보 보강 로직은 변경하지 않음

[V2 STEP2 REV 02 변경점]
- Step 2 AI 후보 보강 옵션 추가 (기본 OFF)
- OFF: Rev01과 동일한 export_message_group() 실행 경로만 사용
- ON: 기존 Rule 결과를 먼저 생성한 뒤 아래 AI 보강을 추가 수행
  1) 선택된 DBC 전체 Message를 Message Name + Sender + Receiver 기준으로 1차 AI 평가
  2) 모든 Message를 HIGH / POSSIBLE / LOW로 빠짐없이 분류하고 Python에서 응답 완전성 검증
  3) HIGH/POSSIBLE 중 기존 Rule 후보가 아닌 Message에 대해서만 Signal Name을 제공해 2차 AI 검토
  4) 2차 KEEP Message만 기존 Rule 후보에 추가 (AI는 기존 후보 삭제 불가)
  5) exclude_keywords는 Hard Rule로 유지하여 AI가 제외 대상을 복원하지 못함
- 대형 DBC 대응: 1차 Message / 2차 Signal 검토 입력을 문자 수 기준으로 자동 분할
- AI 응답에서 실제 DBC에 없는 Message를 추가할 수 없도록 item/message 완전성 검증
- API/응답/런타임 오류가 발생하면 AI 보강을 포기하고 기존 Rule message_group으로 정상 진행
- AI 검토 결과는 Step2_AI_후보검토_{카테고리}.json에 기록

사전 설치
    py -m pip install cantools pandas openpyxl xlrd>=2.0.1 openai requests
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
import json
import re
import time

import cantools

from Signal_Export_V2_Excel_Compat_rev_03 import find_excel_file_compat, read_excel_compat, ffill_dataframe_columns_compat

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

try:
    from openai import AzureOpenAI
except Exception:  # pragma: no cover
    AzureOpenAI = None


# =========================================================
# 기존 Rule 기반 Step 2 (Rev01 로직 유지)
# =========================================================
def compile_token_regexes(keywords: Iterable[str], ignore_case: bool) -> list[re.Pattern]:
    flags = re.IGNORECASE if ignore_case else 0
    return [
        re.compile(rf"(^|_){re.escape(str(kw))}(_|$)", flags)
        for kw in keywords
        if str(kw).strip()
    ]


def token_match_any(text: str, token_regexes: list[re.Pattern]) -> bool:
    return any(rx.search(text) for rx in token_regexes)


def resolve_dbc_paths(base_dir: Path, dbc_files: list[str]) -> list[Path]:
    dbc_paths = []

    if not dbc_files:
        raise FileNotFoundError("dbc_files_step2가 비어 있음")

    for name in dbc_files:
        p = Path(name)
        if not p.is_absolute():
            p = base_dir / name

        if not p.exists():
            raise FileNotFoundError(f"DBC 파일을 찾지 못했습니다: {p}")

        dbc_paths.append(p)

    return dbc_paths


def export_message_group(
    base_dir: Path,
    include_keywords: list[str],
    include_message_name_keywords: list[str],
    exclude_keywords: list[str],
    include_ignore_case: bool,
    include_message_name_ignore_case: bool,
    dbc_files: list[str],
    output_txt: str,
) -> Path:
    """
    DBC들을 스캔하여 message_group txt 생성.
    중요: AI 옵션 OFF 시 Rev01과 동일한 실행 함수/출력 형식을 유지한다.
    """
    include_sender_rxs = compile_token_regexes(include_keywords, include_ignore_case)

    include_msgname_rxs = (
        compile_token_regexes(include_message_name_keywords, include_message_name_ignore_case)
        if include_message_name_keywords
        else []
    )

    # exclude는 항상 대소문자 무시
    exclude_rxs = compile_token_regexes(exclude_keywords, ignore_case=True) if exclude_keywords else []

    dbc_paths = resolve_dbc_paths(base_dir, dbc_files)

    matched_sender_nodes = set()
    selected_names = set()

    # =====================================================
    # 1차: ECU(sender) 이름에 include_keywords가 있는 sender만 수집
    # =====================================================
    for dbc_path in dbc_paths:
        print(f"[SCAN-1] {dbc_path.name} (collect matched ECUs)")
        db = cantools.database.load_file(str(dbc_path))

        for msg in db.messages:
            msg_name = msg.name
            senders = msg.senders or []

            # 제외: 메시지명 또는 sender에 제외 토큰 있으면 스킵
            if exclude_rxs:
                if token_match_any(msg_name, exclude_rxs) or any(token_match_any(s, exclude_rxs) for s in senders):
                    continue

            for s in senders:
                if token_match_any(s, include_sender_rxs):
                    matched_sender_nodes.add(s)

    # =====================================================
    # 2차:
    # - matched_sender_nodes가 송신자인 모든 메시지 포함
    # - 또는 메시지명에 include_message_name_keywords가 있으면 그 메시지만 추가 포함
    # =====================================================
    for dbc_path in dbc_paths:
        print(f"[SCAN-2] {dbc_path.name} (include all msgs of matched ECUs + matched msg names)")
        db = cantools.database.load_file(str(dbc_path))

        for msg in db.messages:
            msg_name = msg.name
            senders = msg.senders or []

            if exclude_rxs:
                if token_match_any(msg_name, exclude_rxs) or any(token_match_any(s, exclude_rxs) for s in senders):
                    continue

            ecu_matched = any(s in matched_sender_nodes for s in senders)
            msgname_matched = token_match_any(msg_name, include_msgname_rxs) if include_msgname_rxs else False

            if ecu_matched or msgname_matched:
                selected_names.add(msg_name)

    sorted_names = sorted(selected_names, key=str.upper)

    out_path = base_dir / output_txt
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"#INCLUDE(sender only): {', '.join(include_keywords)}\n")

        if include_message_name_keywords:
            f.write(f"#INCLUDE(message name only): {', '.join(include_message_name_keywords)}\n")

        if exclude_keywords:
            f.write(f"#EXCLUDE(case-insensitive): {', '.join(exclude_keywords)}\n")

        for p in dbc_paths:
            f.write(f"#DBC: {p.name}\n")

        if matched_sender_nodes:
            f.write("#Matched ECU(Transmitter): " + ", ".join(sorted(matched_sender_nodes)) + "\n")

        for name in sorted_names:
            f.write(name + "\n")

    print(f"[OK] saved: {out_path}")
    print(f"[OK] matched ECU count: {len(matched_sender_nodes)}")
    print(f"[OK] unique message count: {len(sorted_names)}")

    return out_path


# =========================================================
# AI 후보 보강: 데이터 구조
# =========================================================
@dataclass
class MessageInfo:
    name: str
    dbc_files: Set[str] = field(default_factory=set)
    senders: Set[str] = field(default_factory=set)
    receivers: Set[str] = field(default_factory=set)
    signals: Set[str] = field(default_factory=set)


@dataclass
class SignalReviewItem:
    item_id: str
    message_name: str
    part_index: int
    part_count: int
    signals: List[str]


# =========================================================
# AI 후보 보강: 공통 유틸
# =========================================================
def _read_rule_message_group(path: Path) -> Tuple[List[str], Set[str]]:
    headers: List[str] = []
    names: Set[str] = set()
    text = path.read_text(encoding="utf-8", errors="replace")
    for raw in text.splitlines():
        line = raw.rstrip("\r\n")
        if line.startswith("#"):
            headers.append(line)
        elif line.strip():
            names.add(line.strip())
    return headers, names


def _rewrite_message_group_with_union(path: Path, headers: Sequence[str], names: Iterable[str]) -> None:
    lines = list(headers) + sorted({str(x).strip() for x in names if str(x).strip()}, key=str.upper)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _safe_token(value: str) -> str:
    s = re.sub(r"[^0-9A-Za-z가-힣_\-.]+", "_", str(value or "").strip())
    return s.strip("_") or "category"


def _collect_dbc_message_infos(
    dbc_paths: Sequence[Path],
    exclude_keywords: Sequence[str],
) -> Dict[str, MessageInfo]:
    exclude_rxs = compile_token_regexes(exclude_keywords, ignore_case=True) if exclude_keywords else []
    result: Dict[str, MessageInfo] = {}

    for dbc_path in dbc_paths:
        print(f"[AI-STEP2][DBC] 전체 Message 스캔: {dbc_path.name}")
        db = cantools.database.load_file(str(dbc_path))
        for msg in getattr(db, "messages", []) or []:
            name = str(getattr(msg, "name", "") or "").strip()
            if not name:
                continue
            senders = [str(x).strip() for x in (getattr(msg, "senders", None) or []) if str(x).strip()]
            if exclude_rxs and (token_match_any(name, exclude_rxs) or any(token_match_any(s, exclude_rxs) for s in senders)):
                continue

            info = result.setdefault(name, MessageInfo(name=name))
            info.dbc_files.add(dbc_path.name)
            info.senders.update(senders)

            msg_receivers = [str(x).strip() for x in (getattr(msg, "receivers", None) or []) if str(x).strip()]
            info.receivers.update(msg_receivers)

            for sig in getattr(msg, "signals", []) or []:
                sig_name = str(getattr(sig, "name", "") or "").strip()
                if sig_name:
                    info.signals.add(sig_name)
                sig_receivers = [str(x).strip() for x in (getattr(sig, "receivers", None) or []) if str(x).strip()]
                info.receivers.update(sig_receivers)

    return result


def _find_excel_file(base_dir: Path, excel_glob: str) -> Path:
    path = find_excel_file_compat(base_dir, excel_glob, required=True)
    assert path is not None
    return path


def _load_category_tc_summary(config) -> Tuple[Path, List[dict], str]:
    if pd is None:
        raise ImportError("pandas 패키지가 설치되지 않았습니다. Step 2 AI 보강에 pandas가 필요합니다.")

    base_dir = Path(config.base_dir)
    excel_path = _find_excel_file(base_dir, str(getattr(config, "excel_glob", "TestCase_모음*.xls*")))
    sheet_name = str(getattr(config, "category_prefix", "") or "").strip()
    if not sheet_name:
        raise ValueError("Step 2 AI 보강용 category_prefix가 비어 있습니다.")

    df = read_excel_compat(excel_path, sheet_name=sheet_name, header=None)
    start_idx = max(0, int(getattr(config, "start_row_excel", 2) or 2) - 1)
    no_idx = int(getattr(config, "tc_no_column_index", 0) or 0)
    class_idx = int(getattr(config, "tc_class_column_index", 1) or 1)
    tc_idx = int(getattr(config, "tc_column_index", 2) or 2)
    expected_idx = int(getattr(config, "tc_expected_col_idx", 3) if hasattr(config, "tc_expected_col_idx") else 3)

    ffill_dataframe_columns_compat(df, start_idx, [no_idx, class_idx])

    rows: List[dict] = []
    counters: Dict[str, int] = {}
    for i in range(start_idx, len(df)):
        no_val = df.iat[i, no_idx] if no_idx < len(df.columns) else None
        if pd.isna(no_val):
            continue
        no_text = str(no_val).strip()
        try:
            no_text = str(int(float(no_text)))
        except Exception:
            pass
        counters[no_text] = counters.get(no_text, 0) + 1
        sub_no = counters[no_text]

        class_val = df.iat[i, class_idx] if class_idx < len(df.columns) else None
        tc_val = df.iat[i, tc_idx] if tc_idx < len(df.columns) else None
        expected_val = df.iat[i, expected_idx] if expected_idx < len(df.columns) else None

        def clean(v) -> str:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return ""
            return re.sub(r"\s+", " ", str(v).strip())

        tc_text = clean(tc_val)
        expected = clean(expected_val)
        tc_class = clean(class_val)
        if not tc_text and not expected:
            continue
        label = no_text if sub_no == 1 else f"{no_text}-{sub_no}"
        rows.append({"label": label, "class": tc_class, "text": tc_text, "expected": expected})

    if not rows:
        raise ValueError(f"선택 카테고리 시트에서 TC 내용을 찾지 못했습니다: {sheet_name}")

    summary_lines = [f"[카테고리] {sheet_name}"]
    for row in rows:
        summary_lines.append(f"TC {row['label']}")
        if row["class"]:
            summary_lines.append(f"분류: {row['class']}")
        summary_lines.append(f"내용: {row['text'] or '-'}")
        summary_lines.append(f"예상 결과: {row['expected'] or '-'}")
        summary_lines.append("")

    summary = "\n".join(summary_lines).strip()
    max_tc_chars = int(getattr(config, "step_2_ai_tc_context_max_chars", 60000) or 60000)
    if len(summary) > max_tc_chars:
        # 모든 TC를 유지하되 각 항목의 장문을 균등하게 줄여 전체 컨텍스트를 제한한다.
        compact_lines = [f"[카테고리] {sheet_name}"]
        per_row = max(180, int((max_tc_chars - 1000) / max(len(rows), 1)))
        for row in rows:
            body = f"TC {row['label']} | {row['class']} | {row['text']} | 예상: {row['expected']}"
            if len(body) > per_row:
                body = body[:per_row - 3].rstrip() + "..."
            compact_lines.append(body)
        summary = "\n".join(compact_lines)
        print(f"[AI-STEP2][WARN] TC 컨텍스트가 커서 항목별 요약 적용: {len(rows)}건 / {len(summary):,} chars")

    return excel_path, rows, summary


def _message_block(info: MessageInfo) -> str:
    return (
        f"Message: {info.name}\n"
        f"DBC: {', '.join(sorted(info.dbc_files)) or '-'}\n"
        f"Sender: {', '.join(sorted(info.senders)) or '-'}\n"
        f"Receiver: {', '.join(sorted(info.receivers)) or '-'}"
    )


def _chunk_blocks(blocks: Sequence[Tuple[str, str]], max_chars: int) -> List[List[Tuple[str, str]]]:
    max_chars = max(8000, int(max_chars or 50000))
    chunks: List[List[Tuple[str, str]]] = []
    current: List[Tuple[str, str]] = []
    current_chars = 0
    for key, block in blocks:
        block_chars = len(block) + 2
        if current and current_chars + block_chars > max_chars:
            chunks.append(current)
            current = []
            current_chars = 0
        current.append((key, block))
        current_chars += block_chars
    if current:
        chunks.append(current)
    return chunks


def _extract_json_object(text: str) -> dict:
    s = (text or "").strip()
    if not s:
        raise ValueError("AI 응답이 비어 있습니다.")
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)
    try:
        data = json.loads(s)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        data = json.loads(s[start:end + 1])
        if isinstance(data, dict):
            return data
    raise ValueError("AI 응답에서 JSON object를 찾지 못했습니다.")


# =========================================================
# API 호출 (Step 5와 동일 provider/config 정책)
# =========================================================
def _create_gpt_client(config):
    if AzureOpenAI is None:
        raise ImportError("openai 패키지가 설치되지 않았습니다. py -m pip install openai 필요")
    headers = {}
    project_id = str(getattr(config, "project_id", "") or "").strip()
    if project_id:
        headers["X-Project-Id"] = project_id
    return AzureOpenAI(
        azure_endpoint=str(getattr(config, "base_url", "") or ""),
        api_key=str(getattr(config, "api_key", "") or ""),
        api_version=str(getattr(config, "api_version", "2025-04-01-preview") or "2025-04-01-preview"),
        default_headers=headers if headers else None,
    )


def _extract_gemini_text(resp_json: dict) -> str:
    candidates = resp_json.get("candidates") or []
    if candidates:
        content = (candidates[0] or {}).get("content") or {}
        parts = content.get("parts") or []
        texts = [str(p.get("text")) for p in parts if p.get("text")]
        if texts:
            return "".join(texts)
    for key in ("outputText", "text", "result"):
        if isinstance(resp_json.get(key), str):
            return resp_json[key]
    return json.dumps(resp_json, ensure_ascii=False)


def ask_ai_with_txt_content(txt_content: str, config) -> str:
    provider = str(getattr(config, "ai_provider", "gpt") or "gpt").lower()
    use_system = bool(getattr(config, "use_system_message", True))
    system_message = str(getattr(config, "system_message", "") or "")

    if provider == "gpt":
        client = _create_gpt_client(config)
        messages = []
        if use_system and system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": txt_content})
        completion = client.chat.completions.create(
            model=str(getattr(config, "gpt_model", "") or ""),
            messages=messages,
        )
        content = completion.choices[0].message.content
        return content if content is not None else ""

    if provider == "gemini":
        if requests is None:
            raise ImportError("requests 패키지가 설치되지 않았습니다. py -m pip install requests 필요")
        base_url = str(getattr(config, "base_url", "") or "").rstrip("/")
        model = str(getattr(config, "gemini_model", "") or "")
        stream_option = str(getattr(config, "gemini_stream_option", "generateContent") or "generateContent")
        url = f"{base_url}/models/{model}:{stream_option}"
        params = {"key": str(getattr(config, "api_key", "") or "")}
        headers = {"Content-Type": "application/json"}
        project_id = str(getattr(config, "project_id", "") or "").strip()
        if project_id:
            headers["X-Project-Id"] = project_id
        payload = {"contents": [{"role": "user", "parts": [{"text": txt_content}]}]}
        if use_system and system_message:
            payload["systemInstruction"] = {"parts": [{"text": system_message}]}
        r = requests.post(url, params=params, headers=headers, json=payload, timeout=120)
        r.raise_for_status()
        return _extract_gemini_text(r.json())

    raise ValueError(f"지원하지 않는 ai_provider: {provider}")


def _ask_json_with_retry(prompt: str, config, validator, label: str) -> dict:
    max_retry = max(1, int(getattr(config, "max_retry", 3) or 3))
    retry_wait = float(getattr(config, "retry_wait_seconds", 2.0) or 2.0)
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retry + 1):
        try:
            raw = ask_ai_with_txt_content(prompt, config)
            data = _extract_json_object(raw)
            validator(data)
            return data
        except Exception as exc:
            last_exc = exc
            print(f"[AI-STEP2][WARN] {label} AI 응답 검증/호출 실패 {attempt}/{max_retry}: {exc}")
            if attempt < max_retry:
                time.sleep(retry_wait)
    raise RuntimeError(f"{label} AI 호출이 {max_retry}회 모두 실패했습니다: {last_exc}")


# =========================================================
# 1차 AI: 전체 Message Name + Sender + Receiver 분류
# =========================================================
def _build_first_scan_prompt(tc_summary: str, chunk: Sequence[Tuple[str, str]], idx: int, total: int) -> str:
    message_text = "\n\n".join(block for _key, block in chunk)
    expected_names = [key for key, _block in chunk]
    return f"""
[목적]
아래 TestCase 카테고리와 관련될 가능성이 있는 CAN Message를 넓게 탐색한다.
이 단계는 누락 방지가 최우선이므로 확실히 무관하지 않은 항목은 POSSIBLE로 남긴다.

[중요 규칙]
1. 아래 입력 Message를 하나도 누락하지 말고 각각 정확히 1회 평가한다.
2. 반드시 입력에 실제 존재하는 Message 이름만 그대로 사용한다. 새 이름을 만들거나 철자를 바꾸지 않는다.
3. Signal 정보는 아직 제공되지 않았다. Message Name, Sender, Receiver를 근거로만 판단한다.
4. 등급은 HIGH / POSSIBLE / LOW 셋 중 하나만 사용한다.
5. HIGH: TC와 직접 관련 가능성이 높음.
6. POSSIBLE: 이름/ECU 관계상 관련 가능성을 배제할 수 없음. 애매하면 POSSIBLE.
7. LOW: TC와 관련성이 매우 낮다고 판단됨.
8. JSON 외 텍스트는 출력하지 않는다.

[TestCase]
{tc_summary}

[Message chunk {idx}/{total}]
{message_text}

[반드시 평가해야 하는 Message 이름]
{json.dumps(expected_names, ensure_ascii=False)}

[출력 JSON]
{{
  "assessments": [
    {{"message": "입력 Message 이름", "level": "HIGH|POSSIBLE|LOW", "reason": "짧은 근거"}}
  ]
}}
""".strip()


def _validate_first_scan(data: dict, expected_names: Sequence[str]) -> None:
    rows = data.get("assessments")
    if not isinstance(rows, list):
        raise ValueError("assessments 배열이 없습니다.")
    expected = set(expected_names)
    seen: Set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("assessments 항목 형식 오류")
        name = str(row.get("message", "") or "").strip()
        level = str(row.get("level", "") or "").strip().upper()
        if name not in expected:
            raise ValueError(f"입력에 없는 Message 응답: {name}")
        if name in seen:
            raise ValueError(f"Message 중복 응답: {name}")
        if level not in {"HIGH", "POSSIBLE", "LOW"}:
            raise ValueError(f"잘못된 level: {name}={level}")
        seen.add(name)
    missing = expected - seen
    if missing:
        raise ValueError(f"Message 응답 누락 {len(missing)}개: {sorted(missing)[:10]}")


def _run_first_scan(infos: Dict[str, MessageInfo], tc_summary: str, config) -> Dict[str, dict]:
    blocks = [(name, _message_block(infos[name])) for name in sorted(infos, key=str.upper)]
    max_chars = int(getattr(config, "step_2_ai_message_chunk_chars", 50000) or 50000)
    chunks = _chunk_blocks(blocks, max_chars=max_chars)
    result: Dict[str, dict] = {}
    print(f"[AI-STEP2] 1차 Message Scan: {len(blocks)} messages / {len(chunks)} chunks")

    for idx, chunk in enumerate(chunks, 1):
        expected_names = [key for key, _ in chunk]
        prompt = _build_first_scan_prompt(tc_summary, chunk, idx, len(chunks))
        data = _ask_json_with_retry(
            prompt,
            config,
            validator=lambda d, names=expected_names: _validate_first_scan(d, names),
            label=f"1차 Message Scan {idx}/{len(chunks)}",
        )
        for row in data["assessments"]:
            name = str(row["message"]).strip()
            result[name] = {
                "level": str(row["level"]).strip().upper(),
                "reason": str(row.get("reason", "") or "").strip(),
            }
        print(f"[AI-STEP2] 1차 완료 {idx}/{len(chunks)}: {len(expected_names)} messages")
    return result


# =========================================================
# 2차 AI: 후보 Message의 Signal Name 검토
# =========================================================
def _make_signal_review_items(infos: Dict[str, MessageInfo], message_names: Sequence[str], per_part: int) -> List[SignalReviewItem]:
    result: List[SignalReviewItem] = []
    per_part = max(30, int(per_part or 200))
    for name in sorted(set(message_names), key=str.upper):
        signals = sorted(infos[name].signals, key=str.upper)
        if not signals:
            signals = ["(Signal 정보 없음)"]
        parts = [signals[i:i + per_part] for i in range(0, len(signals), per_part)] or [[]]
        total = len(parts)
        for idx, sigs in enumerate(parts, 1):
            result.append(SignalReviewItem(
                item_id=f"M{len(result)+1:05d}",
                message_name=name,
                part_index=idx,
                part_count=total,
                signals=sigs,
            ))
    return result


def _signal_review_block(item: SignalReviewItem, info: MessageInfo) -> str:
    return (
        f"ItemID: {item.item_id}\n"
        f"Message: {item.message_name}\n"
        f"Part: {item.part_index}/{item.part_count}\n"
        f"Sender: {', '.join(sorted(info.senders)) or '-'}\n"
        f"Receiver: {', '.join(sorted(info.receivers)) or '-'}\n"
        f"Signals: {', '.join(item.signals)}"
    )


def _build_second_scan_prompt(tc_summary: str, chunk: Sequence[Tuple[str, str]], idx: int, total: int) -> str:
    item_text = "\n\n".join(block for _key, block in chunk)
    expected_ids = [key for key, _ in chunk]
    return f"""
[목적]
1차 Message Name/Sender/Receiver 검토에서 HIGH 또는 POSSIBLE로 남았지만 기존 Rule 후보에는 없던 Message를 Signal Name까지 보고 재검토한다.

[중요 규칙]
1. 아래 ItemID를 하나도 누락하지 말고 각각 정확히 1회 평가한다.
2. 판단은 KEEP / DROP 둘 중 하나만 사용한다.
3. 누락 방지가 우선이다. Signal 이름 중 하나라도 현재 TC의 입력/명령/상태/결과 판정/조건과 합리적으로 관련될 수 있으면 KEEP한다.
4. 확실히 관련성이 낮은 경우에만 DROP한다.
5. Part가 여러 개인 Message는 같은 Message의 Signal 목록이 분할된 것이다. 각 Part를 독립적으로 평가한다.
6. JSON 외 텍스트는 출력하지 않는다.

[TestCase]
{tc_summary}

[Signal review chunk {idx}/{total}]
{item_text}

[반드시 평가해야 하는 ItemID]
{json.dumps(expected_ids, ensure_ascii=False)}

[출력 JSON]
{{
  "assessments": [
    {{"item_id": "M00001", "decision": "KEEP|DROP", "reason": "짧은 근거"}}
  ]
}}
""".strip()


def _validate_second_scan(data: dict, expected_ids: Sequence[str]) -> None:
    rows = data.get("assessments")
    if not isinstance(rows, list):
        raise ValueError("assessments 배열이 없습니다.")
    expected = set(expected_ids)
    seen: Set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("assessments 항목 형식 오류")
        item_id = str(row.get("item_id", "") or "").strip()
        decision = str(row.get("decision", "") or "").strip().upper()
        if item_id not in expected:
            raise ValueError(f"입력에 없는 ItemID 응답: {item_id}")
        if item_id in seen:
            raise ValueError(f"ItemID 중복 응답: {item_id}")
        if decision not in {"KEEP", "DROP"}:
            raise ValueError(f"잘못된 decision: {item_id}={decision}")
        seen.add(item_id)
    missing = expected - seen
    if missing:
        raise ValueError(f"ItemID 응답 누락 {len(missing)}개: {sorted(missing)[:10]}")


def _run_second_scan(
    infos: Dict[str, MessageInfo],
    message_names: Sequence[str],
    tc_summary: str,
    config,
) -> Tuple[Set[str], Dict[str, List[dict]]]:
    per_part = int(getattr(config, "step_2_ai_signals_per_part", 200) or 200)
    items = _make_signal_review_items(infos, message_names, per_part=per_part)
    by_id = {item.item_id: item for item in items}
    blocks = [(item.item_id, _signal_review_block(item, infos[item.message_name])) for item in items]
    max_chars = int(getattr(config, "step_2_ai_signal_chunk_chars", 60000) or 60000)
    chunks = _chunk_blocks(blocks, max_chars=max_chars)
    print(f"[AI-STEP2] 2차 Signal Scan: {len(message_names)} messages / {len(items)} items / {len(chunks)} chunks")

    decisions: Dict[str, List[dict]] = {name: [] for name in message_names}
    for idx, chunk in enumerate(chunks, 1):
        expected_ids = [key for key, _ in chunk]
        prompt = _build_second_scan_prompt(tc_summary, chunk, idx, len(chunks))
        data = _ask_json_with_retry(
            prompt,
            config,
            validator=lambda d, ids=expected_ids: _validate_second_scan(d, ids),
            label=f"2차 Signal Scan {idx}/{len(chunks)}",
        )
        for row in data["assessments"]:
            item_id = str(row["item_id"]).strip()
            item = by_id[item_id]
            decisions.setdefault(item.message_name, []).append({
                "item_id": item_id,
                "part": f"{item.part_index}/{item.part_count}",
                "decision": str(row["decision"]).strip().upper(),
                "reason": str(row.get("reason", "") or "").strip(),
            })
        print(f"[AI-STEP2] 2차 완료 {idx}/{len(chunks)}: {len(expected_ids)} items")

    keep: Set[str] = set()
    for name, rows in decisions.items():
        # Message가 signal part로 쪼개진 경우 어느 한 part라도 KEEP이면 Message 전체 KEEP (Recall 우선)
        if any(row.get("decision") == "KEEP" for row in rows):
            keep.add(name)
    return keep, decisions


# =========================================================
# AI 보강 전체 실행 / 진단 기록
# =========================================================
def _write_ai_diagnostic(base_dir: Path, config, payload: dict) -> Path:
    safe = _safe_token(str(getattr(config, "active_category", "category") or "category"))
    path = base_dir / f"Step2_AI_후보검토_{safe}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[AI-STEP2] 진단 결과 저장: {path.name}")
    return path


def _write_ai_failure_note(base_dir: Path, config, reason: str) -> Path:
    safe = _safe_token(str(getattr(config, "active_category", "category") or "category"))
    path = base_dir / f"Step2_AI_후보검토_{safe}_실패.txt"
    text = (
        "[Step 2 AI 후보 보강 실패]\n"
        "AI 보강은 기존 Rule 기반 Step 2를 대체하지 않으므로, 기존 message_group 결과로 계속 진행합니다.\n\n"
        f"[사유]\n{reason}\n"
    )
    path.write_text(text, encoding="utf-8-sig")
    print(f"[AI-STEP2][WARN] 실패 기록 저장: {path.name}")
    return path


def enhance_message_group_with_ai(rule_output_path: Path, config) -> Set[str]:
    base_dir = Path(config.base_dir)
    headers, rule_names = _read_rule_message_group(rule_output_path)
    dbc_paths = resolve_dbc_paths(base_dir, list(config.dbc_files_step2))
    infos = _collect_dbc_message_infos(dbc_paths, list(config.exclude_keywords))
    if not infos:
        raise ValueError("AI 보강 검토 대상 DBC Message가 없습니다.")

    excel_path, tc_rows, tc_summary = _load_category_tc_summary(config)
    first = _run_first_scan(infos, tc_summary, config)

    level_counts = {"HIGH": 0, "POSSIBLE": 0, "LOW": 0}
    for row in first.values():
        level = row.get("level", "LOW")
        if level in level_counts:
            level_counts[level] += 1

    second_candidates = sorted(
        [name for name, row in first.items() if row.get("level") in {"HIGH", "POSSIBLE"} and name not in rule_names],
        key=str.upper,
    )

    if second_candidates:
        ai_keep, second_details = _run_second_scan(infos, second_candidates, tc_summary, config)
    else:
        ai_keep, second_details = set(), {}

    # 실제 DBC Message + exclude 적용 후 pool에서만 추가되므로 hallucination/Hard Exclude 복원 불가
    ai_additions = {name for name in ai_keep if name in infos and name not in rule_names}
    final_names = set(rule_names) | ai_additions
    _rewrite_message_group_with_union(rule_output_path, headers, final_names)

    provider = str(getattr(config, "ai_provider", "gpt") or "gpt")
    model = str(getattr(config, "gpt_model", "") or "") if provider == "gpt" else str(getattr(config, "gemini_model", "") or "")
    diagnostic = {
        "status": "OK",
        "mode": "Step 2 AI 후보 보강",
        "active_category": str(getattr(config, "active_category", "") or ""),
        "category_prefix": str(getattr(config, "category_prefix", "") or ""),
        "excel_file": excel_path.name,
        "tc_count": len(tc_rows),
        "ai_provider": provider,
        "model": model,
        "dbc_files": [p.name for p in dbc_paths],
        "dbc_message_count_after_hard_exclude": len(infos),
        "rule_candidate_count": len(rule_names),
        "first_scan_level_counts": level_counts,
        "second_scan_candidate_count": len(second_candidates),
        "ai_addition_count": len(ai_additions),
        "final_message_count": len(final_names),
        "ai_additions": sorted(ai_additions, key=str.upper),
        "first_scan": first,
        "second_scan": second_details,
        "policy": {
            "rule_candidates_can_be_removed_by_ai": False,
            "exclude_keywords_are_hard_rule": True,
            "ai_failure_falls_back_to_rule_result": True,
        },
    }
    _write_ai_diagnostic(base_dir, config, diagnostic)

    failure_note = base_dir / f"Step2_AI_후보검토_{_safe_token(str(getattr(config, 'active_category', 'category')))}_실패.txt"
    if failure_note.exists():
        try:
            failure_note.unlink()
        except Exception:
            pass

    print(f"[AI-STEP2] Rule 후보: {len(rule_names)}")
    print(f"[AI-STEP2] AI 추가 후보: {len(ai_additions)}")
    print(f"[AI-STEP2] 최종 message_group: {len(final_names)}")
    if ai_additions:
        print("[AI-STEP2] 추가 Message:")
        for name in sorted(ai_additions, key=str.upper):
            print(f"  + {name}")
    return ai_additions


# =========================================================
# 실행부
# =========================================================
def run(config) -> None:
    """main.py에서 호출하는 진입점."""
    base_dir = Path(config.base_dir)

    include_keywords = list(config.include_keywords)
    include_message_name_keywords = list(config.include_message_name_keywords)
    exclude_keywords = list(config.exclude_keywords)

    include_ignore_case = bool(config.include_ignore_case)
    include_message_name_ignore_case = bool(config.include_message_name_ignore_case)

    dbc_files = list(config.dbc_files_step2)
    output_txt = config.output_txt_step2
    ai_enhancement = bool(getattr(config, "step_2_ai_enhancement", False))

    print(f"[INFO] ACTIVE_CATEGORY = {config.active_category}")
    print(f"[INFO] INCLUDE_KEYWORDS = {include_keywords}")
    print(f"[INFO] INCLUDE_MESSAGE_NAME_KEYWORDS = {include_message_name_keywords}")
    print(f"[INFO] EXCLUDE_KEYWORDS = {exclude_keywords}")
    print(f"[INFO] INCLUDE_IGNORE_CASE = {include_ignore_case}")
    print(f"[INFO] INCLUDE_MESSAGE_NAME_IGNORE_CASE = {include_message_name_ignore_case}")
    print(f"[INFO] OUTPUT_TXT = {output_txt}")
    print(f"[INFO] STEP_2_AI_ENHANCEMENT = {ai_enhancement}")

    if not include_keywords and not include_message_name_keywords:
        print("[WARN] include 키워드가 비어 있음. 결과가 비어 있을 수 있음.")

    # 중요: 항상 기존 Rule 기반 Step 2를 먼저 그대로 수행한다.
    out_path = export_message_group(
        base_dir=base_dir,
        include_keywords=include_keywords,
        include_message_name_keywords=include_message_name_keywords,
        exclude_keywords=exclude_keywords,
        include_ignore_case=include_ignore_case,
        include_message_name_ignore_case=include_message_name_ignore_case,
        dbc_files=dbc_files,
        output_txt=output_txt,
    )

    if not ai_enhancement:
        print("[AI-STEP2] 옵션 OFF: 기존 Rule 기반 Step 2 결과를 그대로 사용합니다.")
        return

    print("[AI-STEP2] 옵션 ON: 기존 Rule 결과를 보존한 상태에서 AI 후보 보강을 시작합니다.")
    try:
        enhance_message_group_with_ai(out_path, config)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        print(f"[AI-STEP2][WARN] AI 후보 보강 실패 -> 기존 Rule 결과로 계속 진행: {reason}")
        _write_ai_failure_note(base_dir, config, reason)



def _load_latest_v2_main_module():
    """같은 폴더의 Signal_Export_V2_Main_rev_xx.py 중 가장 높은 rev를 로드한다."""
    import importlib.util
    import re as _re
    import sys as _sys
    code_dir = Path(__file__).resolve().parent
    base = "Signal_Export_V2_Main"
    rx = _re.compile(rf"^{_re.escape(base)}(?:[_\-.])rev(?:[_\-.])?(\d+)\.py$", _re.IGNORECASE)
    best = None
    for path in code_dir.glob(f"{base}*.py"):
        m = rx.match(path.name)
        if not m:
            continue
        rev = int(m.group(1))
        if best is None or rev > best[0]:
            best = (rev, path)
    selected = best[1] if best else code_dir / f"{base}.py"
    if not selected.is_file():
        raise FileNotFoundError(f"{base}_rev_xx.py를 찾지 못했습니다: {code_dir}")
    module_name = f"_dyn_{base}_{selected.stem}"
    spec = importlib.util.spec_from_file_location(module_name, str(selected))
    if spec is None or spec.loader is None:
        raise ImportError(f"Main 모듈 spec 생성 실패: {selected}")
    module = importlib.util.module_from_spec(spec)
    _sys.modules[module_name] = module
    spec.loader.exec_module(module)
    print(f"[INFO] Selected latest V2 Main: {selected.name}")
    return module


def main() -> None:
    main_module = _load_latest_v2_main_module()
    run(main_module.build_config())


if __name__ == "__main__":
    main()
