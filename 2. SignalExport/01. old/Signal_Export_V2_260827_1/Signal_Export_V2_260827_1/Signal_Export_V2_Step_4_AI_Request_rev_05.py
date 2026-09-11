# -*- coding: utf-8 -*-
# [Excel Compat 연동 변경] rev05: Excel Compat rev03 공통 reader/forward-fill helper 사용
"""
[V2 STEP 4 REV 05 변경점]
- TestCase Excel TC 번호/분류 forward-fill을 Excel Compat rev03 공통 helper로 변경
- pandas FutureWarning을 제거하되 기존 TC 매핑/프롬프트 생성 정책은 유지

Signal_Export_V2_Step_4_AI_Request_rev_03.py

목적
- step_3의 변경된 시그널 모음 txt를 기본 TC별 단일 AI 문의용 txt로 변환
- 후보별 DBC Definition / Description / 값 의미를 고정 4줄 형식으로 부착
- 일반 분할은 사용하지 않고, 안전 상한 초과 시에만 후보 블록 단위 예외 안전 분할
- 모든 설정은 main.py에서 관리
- 이 파일은 순수 실행 모듈 역할만 수행

[최종 반영 사항]
1) step_3 결과(txt)에서 time + CH를 제거하지 않음 (메세지별/시간별 모두 유지)
2) DBC에서 아래를 함께 사용:
   - meaning: choices(값->의미) / unit (값 의미 또는 단위)
   - definition: signal.comment (주로 CM_ SG_)
   - description:
       (a) signal.description
       (b) DBC 텍스트의 BA_ "Description" SG_ ... 직접 파싱 결과
       (c) signal.comments 보완
3) 출력 라인 형식(의도):
   time sec CHx MSG : SIG value (meaning) (definition/description)
   - meaning은 항상 "값 바로 뒤"에 오도록 우선 부착
   - definition/description은 그 다음에 부착 (동일 (CH,msg,sig) 최초 1회만)
   - definition/description 중 빈 값은 생략:
     * definition만 있으면: (definition: ...)
     * description만 있으면: (description: ...)
     * 둘 다 있으면: (definition: ..., description: ...)
   - 단, definition과 description 내용이 완전히 같으면 description은 중복 출력하지 않음
4) DBC 3개 충돌 해결:
   - CH 기반 매핑 우선: (ch, msg, sig)
   - 실패 시 (msg, sig) fallback (우선순위: CH4 > CH3 > CH2)


[V2 REV 03 변경점]
- TestCase Excel reader를 공통 호환 모듈로 전환하여 .xls/.xlsx/.xlsm 지원
- 파일 확장자와 실제 내부 형식이 달라도 signature를 우선하여 XLS=xlrd, XLSX/XLSM=openpyxl 자동 선택
- 기존 TC 매핑/후보 1:1 보존/프롬프트 생성 로직은 변경하지 않음

[V2 REV 02 변경점]
- 저장 후 후보 1:1 검증 시 프롬프트 전체를 정규식 검색하지 않음
- [후보 시그널] ~ 후보_시그널수 구간의 각 후보 블록 첫 줄만 검증
- Definition/Description이 ``Word : Word (Text)`` 형태여도 후보로 오인하지 않음
- 분할 프롬프트별 선언 후보 수와 실제 후보 블록 수를 함께 검증

[REV 21 변경점]
- 기본은 TC당 AI문의용 1개를 생성하되, 최종 후보 프롬프트가 안전 상한(기본 90,000자)을 넘을 때만
  후보 4줄 블록 단위로 _a, _b, ... 예외 안전 분할
- 각 split에는 [파일명]/[TC 정보]/[요청]/[출력 방법]을 반복하고 후보 블록만 나누어 독립 API 호출 가능
- 정상 안전 분할은 warning을 만들지 않고, 단일 후보 블록 자체가 상한 초과하거나 분할 수가 비정상적으로 많을 때만 warning 생성

[REV 20 변경점]
- Step 5용 입력을 그룹형 상세 TXT가 아닌 "변경된 시그널 모음" TXT로 전환
- 후보마다 Message : Signal (변경 상태), 관측값, Definition, Description, 값 의미를 사용
- Definition/Description/값 의미가 없더라도 항목 줄은 빈칸으로 유지
- 값 의미는 최대 8개 또는 250자로 제한
- TC당 AI문의용 파일 1개만 생성하며 일반 _a/_b/_c 분할을 제거

[REV 19 변경점]
- AI 문의용 프롬프트 분할 기준을 라인 수 단독 기준에서 라인 수 + 문자 수 이중 기준으로 변경
- 기본 분할 상한: 관측 본문 2,500줄 또는 160,000자 중 먼저 도달하는 기준
- 한 줄을 중간에서 자르지 않고 줄 경계에서 chunk를 구성하며 _a, _b, ... suffix 규칙은 유지
- 파일별 lines/chars 통계를 로그에 표시해 Step 5 Gateway Timeout 원인 점검을 지원

[REV 18 유지 사항]
- 실패파일만 재실행 시 "입력 txt 단위"가 아니라 "케이스 단위"로 재실행 대상 판정
- 같은 케이스(main_num)에서 메시지별/시간별 중 하나라도 .error 또는 출력 누락이 있으면
  해당 케이스 전체를 step_4 재생성 대상으로 간주
- 케이스 전체 재생성 시 기존 AI문의용 출력(txt 및 split 결과)을 먼저 정리한 뒤 처음부터 다시 생성
- 따라서 일부만 생성된 불완전 케이스도 최종적으로 실패 케이스로 보고 전체 재생성 가능

[추가 반영 사항]
- 엑셀 D열 "예상 결과"를 읽어 [TC 정보]에 추가
- 형식:
    TC 예상 결과: {tc_expected}
- D열이 비어 있거나 값이 없으면:
    TC 예상 결과: 예상결과 없음
- 76-1, 76-2 / 33-1, 33-2 등 서브 번호 구조에 대해
  C열(TC 내용)과 동일한 행단위 논리로 D열(예상 결과)도 함께 매핑
"""

from __future__ import annotations

import re
import traceback
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Sequence

import pandas as pd

from Signal_Export_V2_Excel_Compat_rev_03 import find_excel_file_compat, read_excel_compat, ffill_dataframe_columns_compat
import cantools


# =========================================================
# suffix: _a, _b, ... (26 넘어가면 _aa, _ab...)
# =========================================================
def index_to_suffix(idx0: int) -> str:
    n = idx0
    s = ""
    while True:
        n, r = divmod(n, 26)
        s = chr(ord("a") + r) + s
        if n == 0:
            break
        n -= 1
    return s


# =========================================================
# .error.txt 유틸
# =========================================================
def get_error_log_path_for_input_txt(txt_path: Path) -> Path:
    return txt_path.with_name(f"{txt_path.stem}.error.txt")


def has_error_log_for_input_txt(txt_path: Path) -> bool:
    return get_error_log_path_for_input_txt(txt_path).exists()


def write_error_log_for_input_txt(txt_path: Path, reason: str, exc: Exception | None = None) -> None:
    error_path = get_error_log_path_for_input_txt(txt_path)

    tb_text = ""
    exc_repr = ""
    if exc is not None:
        exc_repr = repr(exc)
        tb_text = traceback.format_exc()

    text = (
        f"[실패 파일]\n{txt_path.name}\n\n"
        f"[원본 경로]\n{txt_path}\n\n"
        f"[실패 단계]\nSTEP 4 - TXT -> AI REQUEST TXT\n\n"
        f"[실패 사유]\n{reason}\n\n"
        f"[예외 메시지]\n{exc_repr}\n\n"
        f"[상세 Traceback]\n{tb_text}"
    )
    error_path.write_text(text, encoding="utf-8")


def remove_error_log_for_input_txt_if_exists(txt_path: Path) -> None:
    error_path = get_error_log_path_for_input_txt(txt_path)
    try:
        if error_path.exists():
            error_path.unlink()
            print(f"[OK] 이전 에러로그 삭제: {error_path.name}")
    except Exception as e:
        print(f"[WARN] 에러로그 삭제 실패: {error_path} ({e})")


# =========================================================
# 공통 유틸
# =========================================================
def read_text_with_fallback(path: Path) -> str:
    encodings = ["utf-8", "cp949", "euc-kr", "utf-8-sig"]
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except Exception:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"인코딩 판별 실패: {path}")


def extract_sort_key_from_filename(name: str):
    m = re.search(r"(\d+)(?:-([\d-]+))?\s*번", name)
    if not m:
        return None

    main_num_str = m.group(1)
    suffix_str = m.group(2)
    main_num = int(main_num_str)

    if suffix_str:
        sub_parts = [int(x) for x in suffix_str.split("-") if x.isdigit()]
        sort_tuple = tuple([main_num] + sub_parts)
        label = f"{main_num_str}-{suffix_str}"
    else:
        sort_tuple = (main_num,)
        label = f"{main_num_str}"

    return main_num, sort_tuple, label


def find_excel_file(base_dir: Path, excel_glob: str) -> Path:
    path = find_excel_file_compat(base_dir, excel_glob, required=True)
    assert path is not None
    return path


# =========================================================
# step_3 출력 txt 위치 유연 수집 + 중복 제거
# =========================================================
def get_analyzed_txt_dir(base_dir: Path) -> Path:
    return base_dir / "분석된 txt 파일"


def collect_source_txt_files(
    base_dir: Path,
    txt_prefix: str,
    analyzed_dir: Optional[Path] = None,
) -> List[Path]:
    candidates: List[Path] = []

    if analyzed_dir is None:
        analyzed_dir = get_analyzed_txt_dir(base_dir)

    if analyzed_dir.exists() and analyzed_dir.is_dir():
        candidates += list(analyzed_dir.glob(f"{txt_prefix} *번*.txt"))

    candidates += list(base_dir.glob(f"{txt_prefix} *번*.txt"))

    output_root = base_dir / "AI_문의용_출력"
    if output_root.exists():
        candidates = [p for p in candidates if not str(p).startswith(str(output_root))]

    best_by_name: Dict[str, Path] = {}
    for p in candidates:
        if "_변경된 시그널 모음" in p.stem:
            continue
        if p.name.endswith(".error.txt"):
            continue

        name = p.name
        prev = best_by_name.get(name)
        if prev is None:
            best_by_name[name] = p
        else:
            if p.stat().st_mtime > prev.stat().st_mtime:
                best_by_name[name] = p

    selected = list(best_by_name.values())
    selected.sort(key=lambda x: x.name)
    return selected


# =========================================================
# DBC: meaning/definition/description 로드
# =========================================================
def _squash_spaces_one_line(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    s = re.sub(r"[\r\n\t]+", " ", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()


def _pick_description_from_comments(raw_comments) -> str:
    if not raw_comments:
        return ""

    if isinstance(raw_comments, dict):
        candidate = (
            raw_comments.get("EN")
            or raw_comments.get(None)
            or next((v for v in raw_comments.values() if v), "")
        )
        return _squash_spaces_one_line(candidate)

    if isinstance(raw_comments, str):
        return _squash_spaces_one_line(raw_comments)

    return ""


# =========================================================
# DBC 텍스트에서 BA_ "Description" SG_ 직접 파싱
# =========================================================
def parse_ba_description_map_from_dbc_text(dbc_path: Path) -> Dict[Tuple[int, str], str]:
    text = read_text_with_fallback(dbc_path)
    out: Dict[Tuple[int, str], str] = {}

    prefix = 'BA_ "Description" SG_'
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith(prefix):
            continue

        rest = s[len(prefix):].strip()

        parts = rest.split(None, 2)
        if len(parts) < 3:
            continue
        fid_str, sig, remainder = parts[0], parts[1], parts[2]

        try:
            fid = int(fid_str)
        except Exception:
            continue

        remainder = remainder.strip()
        if not remainder.startswith('"'):
            continue

        end = remainder.rfind('";')
        if end == -1:
            continue

        raw_txt = remainder[1:end]
        raw_txt = raw_txt.replace(r"\\", "\\").replace(r"\"", '"')

        out[(fid, sig)] = _squash_spaces_one_line(raw_txt)

    return out


def _build_dbc_maps(base_dir: Path, dbc_name_by_ch: dict) -> Tuple[dict, dict]:
    by_ch: Dict[int, Dict[Tuple[str, str], dict]] = {}
    fallback: Dict[Tuple[str, str], dict] = {}

    ch_priority = [4, 3, 2]
    ordered = [ch for ch in ch_priority if ch in dbc_name_by_ch] + [
        ch for ch in dbc_name_by_ch.keys() if ch not in ch_priority
    ]

    for ch in ordered:
        dbc_name = dbc_name_by_ch[ch]
        dbc_path = base_dir / dbc_name
        if not dbc_path.exists():

            print(f"[WARN] DBC 파일이 없어 스킵: CH{ch} {dbc_name}")
            continue

        try:
            db = cantools.database.load_file(str(dbc_path))
        except Exception as e:
            print(f"[WARN] DBC 로드 실패: CH{ch} {dbc_name} ({e})")
            continue

        ba_desc_map: Dict[Tuple[int, str], str] = {}
        try:
            ba_desc_map = parse_ba_description_map_from_dbc_text(dbc_path)
            print(f'[INFO] CH{ch} parsed BA_"Description" count: {len(ba_desc_map)}')
        except Exception as e:
            print(f'[WARN] CH{ch} BA_"Description" 파싱 실패: {e}')
            ba_desc_map = {}

        per_ch: Dict[Tuple[str, str], dict] = {}
        msg_count = 0
        sig_count = 0

        comment_count = 0
        description_count = 0
        both_count = 0

        desc_from_field = 0
        desc_from_ba_text = 0
        desc_from_comments = 0

        for msg in getattr(db, "messages", []) or []:
            msg_count += 1
            frame_id = getattr(msg, "frame_id", None)

            for sig in getattr(msg, "signals", []) or []:
                key = (msg.name, sig.name)

                unit = (getattr(sig, "unit", None) or "") or ""
                choices = dict(getattr(sig, "choices", {}) or {})

                raw_comment = getattr(sig, "comment", "")
                raw_description = getattr(sig, "description", "")
                raw_comments = getattr(sig, "comments", None)

                comment = _squash_spaces_one_line(raw_comment or "")

                description = _squash_spaces_one_line(raw_description or "")
                if description:
                    desc_from_field += 1
                else:
                    if frame_id is not None:
                        ba_desc = ba_desc_map.get((int(frame_id), sig.name), "") or ""
                        ba_desc = _squash_spaces_one_line(ba_desc)
                    else:
                        ba_desc = ""

                    if ba_desc:
                        description = ba_desc
                        desc_from_ba_text += 1
                    else:
                        description = _pick_description_from_comments(raw_comments)
                        if description:
                            desc_from_comments += 1

                if comment and description and comment == description:
                    description = ""

                if comment:
                    comment_count += 1
                if description:
                    description_count += 1
                if comment and description:
                    both_count += 1

                info = {
                    "unit": str(unit) if unit else "",
                    "choices": choices,
                    "comment": comment,
                    "description": description,
                }

                per_ch[key] = info

                if key not in fallback:
                    fallback[key] = info

                sig_count += 1

        by_ch[ch] = per_ch
        print(f"[OK] DBC loaded: CH{ch} msgs={msg_count}, signals={sig_count} ({dbc_name})")
        print(f"[INFO] CH{ch} comment={comment_count}, description={description_count}, both={both_count}")
        print(
            f"[INFO] CH{ch} description source: "
            f"sig.description={desc_from_field}, "
            f'BA_"Description"(text)={desc_from_ba_text}, '
            f"sig.comments={desc_from_comments}"
        )

    print(f"[OK] Fallback entries: {len(fallback)}")
    return by_ch, fallback


def _get_info_for_signal(ch: Optional[int], msg: str, sig: str, by_ch: dict, fallback: dict) -> Optional[dict]:
    if not msg or not sig:
        return None

    if ch is not None:
        per = by_ch.get(ch, {})
        info = per.get((msg, sig))
        if info is not None:
            return info

    return fallback.get((msg, sig))


# =========================================================
# 엑셀 TC 로드
# =========================================================
def load_tc_map_from_excel(
    excel_path: Path,
    sheet_name: str,
    tc_no_col_idx: int,
    tc_class_col_idx: int,
    tc_col_idx: int,
    tc_expected_col_idx: int,
    start_row_excel: int,
    intentional_blank_token: str,
):
    if not excel_path.exists():
        raise FileNotFoundError(f"엑셀 파일이 없음: {excel_path}")

    df = read_excel_compat(excel_path, sheet_name=sheet_name, header=None)
    start_idx = start_row_excel - 1

    ffill_dataframe_columns_compat(df, start_idx, [tc_no_col_idx, tc_class_col_idx])

    tc_map = {}
    counters = {}
    last_text = {}

    for i in range(start_idx, len(df)):
        no_val = df.iat[i, tc_no_col_idx] if tc_no_col_idx < len(df.columns) else None
        if pd.isna(no_val):
            continue

        try:
            tc_no = int(float(str(no_val).strip()))
        except Exception:
            continue

        sub_no = counters.get(tc_no, 0) + 1
        counters[tc_no] = sub_no

        class_val = df.iat[i, tc_class_col_idx] if tc_class_col_idx < len(df.columns) else None
        tc_class = "" if pd.isna(class_val) else str(class_val).strip()

        raw = df.iat[i, tc_col_idx] if tc_col_idx < len(df.columns) else None
        if pd.isna(raw):
            tc_text = last_text.get(tc_no, "")
        else:
            s = str(raw).strip()
            if s == intentional_blank_token:
                tc_text = ""
                last_text[tc_no] = ""
            else:
                tc_text = s
                last_text[tc_no] = tc_text

        raw_expected = df.iat[i, tc_expected_col_idx] if tc_expected_col_idx < len(df.columns) else None
        if pd.isna(raw_expected):
            tc_expected = "예상결과 없음"
        else:
            s_expected = str(raw_expected).strip()
            if not s_expected or s_expected == intentional_blank_token:
                tc_expected = "예상결과 없음"
            else:
                tc_expected = s_expected

        tc_map[(tc_no, sub_no)] = (tc_class, tc_text, tc_expected)

    return tc_map


# =========================================================
# 입력 라인 파싱
# =========================================================
_TIME_CH_PREFIX_RE = re.compile(
    r"^\s*(?P<t>\d+(?:\.\d+)?)sec\s+(?P<ch>CH\d+)\s+(?P<body>.*)$",
    re.IGNORECASE,
)
_TIME_ONLY_PREFIX_RE = re.compile(
    r"^\s*(?P<t>\d+(?:\.\d+)?)sec\s+(?P<body>.*)$",
    re.IGNORECASE,
)

_BODY_MSGSIGVAL_RE = re.compile(
    r"^(?P<msg>\w+)\s*:\s*(?P<sig>\w+)\s+(?P<val>0x[0-9A-Fa-f]+|[-+]?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def parse_time_ch_and_body(line: str) -> Tuple[Optional[float], Optional[int], str]:
    s = (line or "").strip()
    if not s:
        return None, None, ""

    m = _TIME_CH_PREFIX_RE.match(s)
    if m:
        t = float(m.group("t"))
        ch_str = m.group("ch").upper()
        try:
            ch = int(ch_str.replace("CH", ""))
        except Exception:
            ch = None
        return t, ch, m.group("body").strip()

    m = _TIME_ONLY_PREFIX_RE.match(s)
    if m:
        t = float(m.group("t"))
        return t, None, m.group("body").strip()

    return None, None, s


def ensure_prefix_time_ch(t: Optional[float], ch: Optional[int], body: str) -> str:
    body = (body or "").strip()
    if not body:
        return ""

    if t is None and ch is None:
        return body
    if t is not None and ch is None:
        return f"{t:.4f}sec {body}"
    if t is None and ch is not None:
        return f"CH{ch} {body}"
    return f"{t:.4f}sec CH{ch} {body}"


def extract_msg_sig_val_from_body(body: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    m = _BODY_MSGSIGVAL_RE.match((body or "").strip())
    if not m:
        return None, None, None
    return m.group("msg"), m.group("sig"), m.group("val")


# =========================================================
# change line 확장
# =========================================================
def split_change_line_to_values(body: str) -> List[str]:
    m = re.match(
        r"^(\w+)\s*:\s*(\w+)\s+(0x[0-9A-Fa-f]+)\s*[→\-]+\s*(0x[0-9A-Fa-f]+)\s*$",
        (body or "").strip()
    )
    if not m:
        return [(body or "").strip()]

    msg_name, sig_name, old_val, new_val = m.groups()
    return [
        f"{msg_name} : {sig_name} {old_val}",
        f"{msg_name} : {sig_name} {new_val}",
    ]


# =========================================================
# AI 문의용 프롬프트 작성
# =========================================================
_MIN_UNRELATED_LINES_IF_NONEMPTY = 10


def build_ai_prompt(
    tc_label: str,
    tc_class: str,
    tc_text: str,
    tc_expected: str,
    source_txt_name: str,
    source_txt_body: str,
    line_count: int,
    require_time_prefix: bool = False,
) -> str:
    time_rule = ""
    if require_time_prefix:
        time_rule = """
[시간별 출력 규칙(필수)]
- "연관 있는 메세지"에 기재하는 각 줄은 반드시 원문에 있는 시간 prefix를 포함할 것.
  예: "12.345sec CH3 MESSAGE : SIGNAL 0x01 (meaning) (definition: ..., description: ...)"
- 시간 prefix 형식은 반드시 "{숫자}sec"로 시작해야 함. (예: 0.000sec, 12sec, 12.345sec 모두 허용)
- CH 표기는 있으면 포함, 없으면 생략 가능.
- "연관 없는 메세지" 섹션에는 시간 prefix가 없어도 됨.
- 위 규칙을 지키지 못하면, 반드시 "형식 오류(재출력 필요)"라고 적고 전체를 다시 출력할 것.
"""

    use_doc_rule = """
[추가 분석 규칙(필수)]
- 각 줄의 값 뒤 괄호 정보(meaning)와, 문장 끝 괄호의 (definition: ...), (description: ...) 내용을 반드시 참고하여
  TC와의 연관성을 판단하고, "연관 없는 메세지"의 사유에도 근거로 반영할 것.
- 또한 [TC 정보]의 "TC 내용"과 "TC 예상 결과"를 함께 참고하여 연관 메세지를 판단할 것.
- 단, 출력 시에는 원문 줄을 그대로 적되(중복 제거 규칙 유지), 임의로 definition/description을 수정/재작성하지 말 것.

""".strip()

    return f"""[파일명]
{source_txt_name}

[TC 정보]
TC 순번: {tc_label}번
TC 분류: {tc_class}
TC 내용: {tc_text}
TC 예상 결과: {tc_expected}

[요청]
아래의 차량 메세지 로그에 대해서, 위의 TC내용과 TC 예상 결과를 기준으로 연관성 있는 메세지를 출력

{use_doc_rule}

[출력 방법]
1) 다른 별도의 설명은 적지 말것
2) 연관된 메세지를 쓸 때, [연관 있는 메세지 양식]대로 기재
3) 연관 없는 것은 아래 [연관 없는 메세지 양식]대로 쓸 것
4) 분석 후 결과 출력 시, txt 명칭을 맨 위에 기재할 것
5) 만약 연관 있는 메세지가 하나도 없다면, txt 명칭 아래에 연관 있는 메세지 없음이라고 기재할 것

[연관 있는 메세지 양식]
1) 테스트 케이스와 연관된 메세지를 그대로 기재
2) Default 값이나 Invalid 값도 기재
3) 중간에 변화한 값이 있다면 그것도 기재
4) 1줄 당 1개의 메세지 : 시그널로 기재하되, 중복이 있다면 1줄만 쓸 것

[연관 없는 메세지 양식]
1) 맨 아래에 따로 기재할 것
2) "연관 없는 메세지"를 제목으로 쓸 것
3) 메세지 : 시그널 ( ) 형식에서, 동일한 시그널이고 값만 다른 경우, 1개로 묶어서 쓸 것
4) 1개의 시그널 단위 당 1줄로 쓰되, 메세지 : 시그널 ( ) // 사유 : ~~~ 형식으로 쓸 것

{time_rule}

[관측된 시그널 목록]
{source_txt_body}

[필수 검증 규칙]
- 만약 "연관 있는 메세지 없음"을 출력하는 경우에도 반드시 "연관 없는 메세지" 섹션을 출력할 것.
- "변경점 목록"이 비어있지 않다면, "연관 없는 메세지" 섹션에는 최소 {_MIN_UNRELATED_LINES_IF_NONEMPTY}줄 이상의 항목을 작성할 것.
- 위 규칙을 지키지 못하면, 반드시 "형식 오류(재출력 필요)"라고 적고 전체를 다시 출력할 것.
변경점_라인수: {line_count}
"""


def _text_char_count(lines: List[str]) -> int:
    """줄 사이 개행 1자를 포함한 본문 문자 수를 계산한다."""
    if not lines:
        return 0
    return sum(len(line) for line in lines) + max(0, len(lines) - 1)


def _split_lines_by_dual_limits(
    lines: List[str],
    max_lines: int,
    max_chars: int,
) -> List[List[str]]:
    """
    줄 경계를 보존하면서 라인 수/문자 수 상한 중 먼저 도달하는 기준으로 분할한다.

    - 한 줄 자체가 max_chars보다 길면 해당 줄만 하나의 chunk로 둔다.
    - 빈 chunk는 만들지 않는다.
    """
    max_lines = max(1, int(max_lines))
    max_chars = max(1, int(max_chars))

    chunks: List[List[str]] = []
    current: List[str] = []
    current_chars = 0

    for line in lines:
        added_chars = len(line) + (1 if current else 0)
        exceeds_lines = bool(current) and len(current) >= max_lines
        exceeds_chars = bool(current) and (current_chars + added_chars > max_chars)

        if exceeds_lines or exceeds_chars:
            chunks.append(current)
            current = []
            current_chars = 0
            added_chars = len(line)

        current.append(line)
        current_chars += added_chars

    if current:
        chunks.append(current)

    return chunks


def write_ai_prompt_split_if_needed(
    output_dir: Path,
    output_base_name: str,
    tc_label: str,
    tc_class: str,
    tc_text: str,
    tc_expected: str,
    source_txt_name: str,
    transformed_body: str,
    split_lines_threshold: int,
    split_lines_per_file: int,
    split_chars_threshold: int,
    split_chars_per_file: int,
    require_time_prefix: bool = False,
) -> List[Path]:
    lines = transformed_body.splitlines()
    total_lines = len(lines)
    total_chars = _text_char_count(lines)
    created_paths: List[Path] = []

    if total_lines == 0:
        prompt_text = build_ai_prompt(
            tc_label=tc_label,
            tc_class=tc_class,
            tc_text=tc_text,
            tc_expected=tc_expected,
            source_txt_name=source_txt_name,
            source_txt_body="",
            line_count=0,
            require_time_prefix=require_time_prefix,
        )
        out_path = output_dir / f"{output_base_name}.txt"
        out_path.write_text(prompt_text, encoding="utf-8-sig")
        print(f"[WARN] 변경점 목록이 비어있음: {out_path.name}")
        created_paths.append(out_path)
        return created_paths

    # 두 기준을 모두 만족할 때만 단일 파일로 저장한다.
    if total_lines <= split_lines_threshold and total_chars <= split_chars_threshold:
        prompt_text = build_ai_prompt(
            tc_label=tc_label,
            tc_class=tc_class,
            tc_text=tc_text,
            tc_expected=tc_expected,
            source_txt_name=source_txt_name,
            source_txt_body=transformed_body,
            line_count=total_lines,
            require_time_prefix=require_time_prefix,
        )
        out_path = output_dir / f"{output_base_name}.txt"
        out_path.write_text(prompt_text, encoding="utf-8-sig")
        print(
            f"[OK] 생성됨: {out_path.name} "
            f"(lines={total_lines}, chars={total_chars})"
        )
        created_paths.append(out_path)
        return created_paths

    chunks = _split_lines_by_dual_limits(
        lines=lines,
        max_lines=split_lines_per_file,
        max_chars=split_chars_per_file,
    )
    print(
        f"[INFO] 큰 파일 이중 기준 분할 저장: base={output_base_name} | "
        f"lines={total_lines}, chars={total_chars} | chunks={len(chunks)} | "
        f"limits={split_lines_per_file} lines / {split_chars_per_file} chars"
    )

    for i, chunk_lines in enumerate(chunks):
        body_part = "\n".join(chunk_lines)
        part_lines = len(chunk_lines)
        part_chars = len(body_part)

        suffix = index_to_suffix(i)
        prompt_text = build_ai_prompt(
            tc_label=tc_label,
            tc_class=tc_class,
            tc_text=tc_text,
            tc_expected=tc_expected,
            source_txt_name=source_txt_name,
            source_txt_body=body_part,
            line_count=part_lines,
            require_time_prefix=require_time_prefix,
        )

        out_path = output_dir / f"{output_base_name}_{suffix}.txt"
        out_path.write_text(prompt_text, encoding="utf-8-sig")
        print(
            f"[OK] 생성됨: {out_path.name} "
            f"(part {i+1}/{len(chunks)}, lines={part_lines}, chars={part_chars})"
        )
        created_paths.append(out_path)

    return created_paths


# =========================================================
# meaning / doc 부착
# =========================================================
def _format_meaning(value_str: str, info: Optional[dict]) -> str:
    if not info:
        return ""

    unit = (info.get("unit") or "").strip()
    choices = info.get("choices") or {}

    if isinstance(value_str, str) and value_str.lower().startswith("0x"):
        try:
            dec = int(value_str, 16)
        except Exception:
            dec = None
        if dec is not None and choices:
            meaning = choices.get(dec)
            if meaning is not None and str(meaning).strip():
                return f" ({str(meaning).strip()})"

    if unit:
        return f" ({unit})"

    return ""


def _format_doc_suffix(comment: str, description: str) -> str:
    definition = _squash_spaces_one_line(comment)
    description = _squash_spaces_one_line(description)

    parts = []
    if definition:
        parts.append(f"definition: {definition}")
    if description:
        parts.append(f"description: {description}")

    if not parts:
        return ""
    return " (" + ", ".join(parts) + ")"


def _attach_meaning_then_doc_once(
    t: Optional[float],
    ch: Optional[int],
    body: str,
    by_ch: dict,
    fallback: dict,
    seen_doc_keys: set,
) -> str:
    body = (body or "").strip()
    if not body:
        return ""

    msg, sig, val = extract_msg_sig_val_from_body(body)
    info = _get_info_for_signal(ch, msg or "", sig or "", by_ch, fallback)

    meaning_suffix = _format_meaning(val or "", info)
    line0 = ensure_prefix_time_ch(t, ch, body + meaning_suffix)

    if not msg or not sig:
        return line0

    seen_key = (ch, msg, sig)
    if seen_key in seen_doc_keys:
        return line0

    comment = (info.get("comment") if info else "") or ""
    description = (info.get("description") if info else "") or ""
    doc_suffix = _format_doc_suffix(comment, description)

    if not doc_suffix:
        return line0

    seen_doc_keys.add(seen_key)
    return f"{line0}{doc_suffix}"


def transform_log_text_keep_time_ch(
    log_text: str,
    dbc_by_ch: dict,
    dbc_fallback: dict,
    dedup_window_sec: float,
) -> str:
    lines_out: List[str] = []
    recent: Dict[str, List[float]] = {}
    seen_doc_keys = set()

    for raw_line in (log_text or "").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        t, ch, body0 = parse_time_ch_and_body(raw_line)
        if not body0:
            continue

        expanded_bodies = split_change_line_to_values(body0)

        for body in expanded_bodies:
            if not body:
                continue

            line = _attach_meaning_then_doc_once(
                t=t,
                ch=ch,
                body=body,
                by_ch=dbc_by_ch,
                fallback=dbc_fallback,
                seen_doc_keys=seen_doc_keys,
            )

            if not line:
                continue

            if t is not None:
                lst = recent.get(line, [])
                windowed = [pt for pt in lst if abs(t - pt) <= dedup_window_sec]
                if windowed:
                    recent[line] = windowed
                    continue
                windowed.append(t)
                recent[line] = windowed

            lines_out.append(line)

    return "\n".join(lines_out)


# =========================================================
# step_4 출력 경로 / 케이스 유틸
# =========================================================
def build_output_base_names_for_label(txt_prefix: str, label: str) -> Tuple[str, str]:
    msg_base = f"AI문의용_{txt_prefix}_{label}번"
    time_base = f"AI문의용_{txt_prefix}_{label}번_시간별"
    return msg_base, time_base


def glob_case_output_files(out_dir: Path, output_base_name: str) -> List[Path]:
    matched = sorted([p for p in out_dir.glob(f"{output_base_name}*.txt") if p.is_file()], key=lambda x: x.name)
    return matched


def cleanup_case_generated_outputs(out_msg_dir: Path, out_time_dir: Path, txt_prefix: str, label: str) -> None:
    msg_base, time_base = build_output_base_names_for_label(txt_prefix, label)

    for p in glob_case_output_files(out_msg_dir, msg_base):
        try:
            p.unlink()
            print(f"[RETRY] 기존 메시지별 출력 삭제: {p.name}")
        except Exception as e:
            print(f"[WARN] 기존 메시지별 출력 삭제 실패: {p} ({e})")

    for p in glob_case_output_files(out_time_dir, time_base):
        try:
            p.unlink()
            print(f"[RETRY] 기존 시간별 출력 삭제: {p.name}")
        except Exception as e:
            print(f"[WARN] 기존 시간별 출력 삭제 실패: {p} ({e})")


def is_case_incomplete_for_step4(
    msg_files: List[Tuple[tuple, str, Path, bool]],
    time_files: List[Tuple[tuple, str, Path, bool]],
    out_msg_dir: Path,
    out_time_dir: Path,
    txt_prefix: str,
) -> Tuple[bool, List[str]]:
    reasons: List[str] = []

    for _sort_tuple, label, txt_path, _ in msg_files:
        if has_error_log_for_input_txt(txt_path):
            reasons.append(f"메시지별 입력 .error 존재: {txt_path.name}")

        msg_base, _ = build_output_base_names_for_label(txt_prefix, label)
        generated = glob_case_output_files(out_msg_dir, msg_base)
        if not generated:
            reasons.append(f"메시지별 출력 누락: {msg_base}*.txt")

    for _sort_tuple, label, txt_path, _ in time_files:
        if has_error_log_for_input_txt(txt_path):
            reasons.append(f"시간별 입력 .error 존재: {txt_path.name}")

        _, time_base = build_output_base_names_for_label(txt_prefix, label)
        generated = glob_case_output_files(out_time_dir, time_base)
        if not generated:
            reasons.append(f"시간별 출력 누락: {time_base}*.txt")

    return (len(reasons) > 0), reasons


# =========================================================
# 실행부
# =========================================================
def _legacy_run(config) -> None:
    base_dir = Path(config.base_dir)
    active_category = config.active_category
    category_prefix = config.category_prefix

    excel_glob = config.excel_glob
    output_dir_name = config.output_dir
    output_dir_msg_name = config.output_dir_msg
    output_dir_time_name = config.output_dir_time

    dedup_window_sec = float(config.dedup_window_sec)
    split_lines_threshold = int(config.split_lines_threshold)
    split_lines_per_file = int(config.split_lines_per_file)
    split_chars_threshold = int(getattr(config, "split_chars_threshold", 160000))
    split_chars_per_file = int(getattr(config, "split_chars_per_file", 160000))

    intentional_blank_token = config.intentional_blank_token
    tc_no_column_index = int(config.tc_no_column_index)
    tc_class_column_index = int(
        config.tc_class_col_idx if hasattr(config, "tc_class_col_idx") else config.tc_class_column_index
    )
    tc_column_index = int(config.tc_col_idx if hasattr(config, "tc_col_idx") else config.tc_column_index)
    tc_expected_col_idx = int(
        config.tc_expected_col_idx if hasattr(config, "tc_expected_col_idx") else 3
    )
    start_row_excel = int(config.start_row_excel)

    sheet_name = category_prefix
    txt_prefix = category_prefix

    print(f"[DEBUG] cantools version: {getattr(cantools, '__version__', 'unknown')}")

    try:
        excel_path = find_excel_file(base_dir, excel_glob)
    except Exception as e:
        print(f"[ERROR] 엑셀 파일 선택 실패: {e}")
        return

    output_root = base_dir / output_dir_name
    out_msg_dir = output_root / output_dir_msg_name
    out_time_dir = output_root / output_dir_time_name
    out_msg_dir.mkdir(parents=True, exist_ok=True)
    out_time_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] ACTIVE_CATEGORY = {active_category}")
    print(f"[INFO] SHEET_NAME      = {sheet_name}")
    print(f"[INFO] TXT_PREFIX      = {txt_prefix}")
    print(f"[INFO] EXCEL_FILE      = {excel_path.name}")
    print(f"[INFO] OUTPUT_ROOT     = {output_root}")

    dbc_by_ch, dbc_fallback = _build_dbc_maps(
        base_dir=base_dir,
        dbc_name_by_ch=dict(config.dbc_name_by_ch),
    )

    try:
        tc_map = load_tc_map_from_excel(
            excel_path=excel_path,
            sheet_name=sheet_name,
            tc_no_col_idx=tc_no_column_index,
            tc_class_col_idx=tc_class_column_index,
            tc_col_idx=tc_column_index,
            tc_expected_col_idx=tc_expected_col_idx,
            start_row_excel=start_row_excel,
            intentional_blank_token=intentional_blank_token,
        )
    except Exception as e:
        print(f"[ERROR] 엑셀 읽기 실패: {e}")
        return

    if not tc_map:
        print("[ERROR] TC 내용을 하나도 읽지 못함")
        return

    print(f"[OK] TC key 개수(번호-서브 조합): {len(tc_map)}")

    analyzed_dir = get_analyzed_txt_dir(base_dir)
    source_txts = collect_source_txt_files(
        base_dir=base_dir,
        txt_prefix=txt_prefix,
        analyzed_dir=analyzed_dir,
    )

    grouped_files: Dict[int, List[Tuple[tuple, str, Path, bool]]] = {}

    for p in source_txts:
        parsed = extract_sort_key_from_filename(p.name)
        if parsed is None:
            continue

        main_num, sort_tuple, label = parsed
        is_timeorder = p.name.endswith("_시간순.txt")
        grouped_files.setdefault(main_num, []).append((sort_tuple, label, p, is_timeorder))

    created_count_msg = 0
    created_count_time = 0

    for main_num in sorted(grouped_files.keys()):
        file_list = grouped_files[main_num]
        msg_files_all = sorted([f for f in file_list if not f[3]], key=lambda x: x[0])
        time_files_all = sorted([f for f in file_list if f[3]], key=lambda x: x[0])

        msg_files = list(msg_files_all)
        time_files = list(time_files_all)

        if getattr(config, "retry_failed_only", False):
            incomplete, reasons = is_case_incomplete_for_step4(
                msg_files=msg_files_all,
                time_files=time_files_all,
                out_msg_dir=out_msg_dir,
                out_time_dir=out_time_dir,
                txt_prefix=txt_prefix,
            )

            print(f"[INFO] 실패파일만 재실행 모드(step_4, main_num={main_num})")
            print(f"[INFO] 메시지별 입력 수: {len(msg_files_all)}")
            print(f"[INFO] 시간별 입력 수  : {len(time_files_all)}")

            if not incomplete:
                print(f"[INFO] main_num={main_num} 케이스는 온전하여 step_4 재실행 대상 아님")
                continue

            print(f"[RETRY][CASE] main_num={main_num} 케이스 전체 재생성 대상")
            for reason in reasons:
                print(f"  - {reason}")

            labels_to_cleanup = set()
            for _sort_tuple, label, _txt_path, _ in msg_files_all:
                labels_to_cleanup.add(label)
            for _sort_tuple, label, _txt_path, _ in time_files_all:
                labels_to_cleanup.add(label)

            for label in sorted(labels_to_cleanup):
                cleanup_case_generated_outputs(
                    out_msg_dir=out_msg_dir,
                    out_time_dir=out_time_dir,
                    txt_prefix=txt_prefix,
                    label=label,
                )

        # A) 메시지별 처리
        for idx, (_sort_tuple, label, txt_path, _) in enumerate(msg_files, 1):
            key = (main_num, idx)

            try:
                if key in tc_map:
                    tc_class, tc_text, tc_expected = tc_map[key]
                else:
                    fallback_key = (main_num, 1)
                    if fallback_key in tc_map:
                        tc_class, tc_text, tc_expected = tc_map[fallback_key]
                        print(f"[WARN] 엑셀에 {main_num}-{idx}번 TC가 없어 {main_num}-1번 TC로 대체: {txt_path.name}")
                    else:
                        reason = f"엑셀에 {main_num}-{idx}번 TC와 {main_num}-1번 TC가 모두 없음"
                        write_error_log_for_input_txt(txt_path, reason=reason)
                        print(f"[WARN] {reason}: {txt_path.name}")
                        continue

                txt_body = read_text_with_fallback(txt_path).strip()

                transformed_body = transform_log_text_keep_time_ch(
                    log_text=txt_body,
                    dbc_by_ch=dbc_by_ch,
                    dbc_fallback=dbc_fallback,
                    dedup_window_sec=dedup_window_sec,
                )

                output_base = f"AI문의용_{txt_prefix}_{label}번"
                created_paths = write_ai_prompt_split_if_needed(
                    output_dir=out_msg_dir,
                    output_base_name=output_base,
                    tc_label=label,
                    tc_class=tc_class,
                    tc_text=tc_text,
                    tc_expected=tc_expected,
                    source_txt_name=txt_path.name,
                    transformed_body=transformed_body,
                    split_lines_threshold=split_lines_threshold,
                    split_lines_per_file=split_lines_per_file,
                    split_chars_threshold=split_chars_threshold,
                    split_chars_per_file=split_chars_per_file,
                    require_time_prefix=False,
                )

                if not created_paths:
                    raise RuntimeError(f"메시지별 출력 파일 생성 결과가 비어 있음: {txt_path.name}")

                created_count_msg += len(created_paths)
                remove_error_log_for_input_txt_if_exists(txt_path)

            except Exception as e:
                reason = f"메시지별 AI문의용 txt 생성 실패: {e}"
                write_error_log_for_input_txt(txt_path, reason=reason, exc=e)
                print(f"[ERROR] {txt_path} ({e})")
                continue

        # B) 시간별 처리
        for idx, (_sort_tuple, label, txt_path, _) in enumerate(time_files, 1):
            key = (main_num, idx)

            try:
                if key in tc_map:
                    tc_class, tc_text, tc_expected = tc_map[key]
                else:
                    fallback_key = (main_num, 1)
                    if fallback_key in tc_map:
                        tc_class, tc_text, tc_expected = tc_map[fallback_key]
                        print(f"[WARN] 엑셀에 {main_num}-{idx}번 TC가 없어 {main_num}-1번 TC로 대체: {txt_path.name}")
                    else:
                        reason = f"엑셀에 {main_num}-{idx}번 TC와 {main_num}-1번 TC가 모두 없음"
                        write_error_log_for_input_txt(txt_path, reason=reason)
                        print(f"[WARN] {reason}: {txt_path.name}")
                        continue

                txt_body = read_text_with_fallback(txt_path).strip()

                transformed_body = transform_log_text_keep_time_ch(
                    log_text=txt_body,
                    dbc_by_ch=dbc_by_ch,
                    dbc_fallback=dbc_fallback,
                    dedup_window_sec=dedup_window_sec,
                )

                output_base = f"AI문의용_{txt_prefix}_{label}번_시간별"
                created_paths = write_ai_prompt_split_if_needed(
                    output_dir=out_time_dir,
                    output_base_name=output_base,
                    tc_label=label,
                    tc_class=tc_class,
                    tc_text=tc_text,
                    tc_expected=tc_expected,
                    source_txt_name=txt_path.name,
                    transformed_body=transformed_body,
                    split_lines_threshold=split_lines_threshold,
                    split_lines_per_file=split_lines_per_file,
                    split_chars_threshold=split_chars_threshold,
                    split_chars_per_file=split_chars_per_file,
                    require_time_prefix=True,
                )

                if not created_paths:
                    raise RuntimeError(f"시간별 출력 파일 생성 결과가 비어 있음: {txt_path.name}")

                created_count_time += len(created_paths)
                remove_error_log_for_input_txt_if_exists(txt_path)

            except Exception as e:
                reason = f"시간별 AI문의용 txt 생성 실패: {e}"
                write_error_log_for_input_txt(txt_path, reason=reason, exc=e)
                print(f"[ERROR] {txt_path} ({e})")
                continue

    print(f"\n[OK] 완료:")
    print(f"  - 메세지별: {created_count_msg}개 -> {out_msg_dir}")
    print(f"  - 시간별  : {created_count_time}개 -> {out_time_dir}")



# =========================================================
# Signal Export V2 - Step 4 REV 02
# - Step 3의 "변경된 시그널 모음 TXT"를 1:1 보존
# - Step 4에서만 DBC Definition / Description / Choices 부착
# - 파싱 불가 행, 중복 후보, 후보 집합 불일치는 조용히 누락하지 않고 실패 처리
# =========================================================
_CHANGED_CANDIDATE_RE = re.compile(
    r"^(?P<msg>[A-Za-z_][\w\-]*)\s*:\s*(?P<sig>[A-Za-z_][\w\-]*)\s*(?P<status>\([^\r\n]*\))\s*$",
    re.IGNORECASE,
)


def collect_candidate_summary_files(base_dir: Path, txt_prefix: str) -> List[Path]:
    analyzed_dir = get_analyzed_txt_dir(base_dir)
    candidates: List[Path] = []
    if analyzed_dir.exists():
        candidates.extend(analyzed_dir.glob(f"{txt_prefix} *번_변경된 시그널 모음.txt"))
    candidates.extend(base_dir.glob(f"{txt_prefix} *번_변경된 시그널 모음.txt"))
    best: Dict[str, Path] = {}
    for path in candidates:
        if not path.is_file() or path.name.endswith('.error.txt') or path.name.endswith('.warning.txt'):
            continue
        prev = best.get(path.name)
        if prev is None or path.stat().st_mtime > prev.stat().st_mtime:
            best[path.name] = path
    return sorted(best.values(), key=lambda p: p.name)


def _truncate_field(value: object, limit: int) -> str:
    text = _squash_spaces_one_line(str(value or ''))
    if len(text) <= limit:
        return text
    return text[:max(0, limit - 8)].rstrip() + ' ...생략'


def _format_choice_table(info: Optional[dict], max_items: int = 8, max_chars: int = 250) -> str:
    if not info:
        return ''
    choices = info.get('choices') or {}
    if not choices:
        return ''
    parts: List[str] = []
    try:
        ordered = sorted(dict(choices).items(), key=lambda kv: int(kv[0]))
    except Exception:
        ordered = list(dict(choices).items())
    truncated = len(ordered) > max_items
    for raw_key, raw_value in ordered[:max_items]:
        try:
            key_text = f"0x{int(raw_key):X}"
        except Exception:
            key_text = str(raw_key)
        parts.append(f"{key_text} {str(raw_value).strip()}")
    result = ' / '.join(parts)
    if truncated:
        result += ' / ... (나머지 생략)'
    if len(result) > max_chars:
        result = result[:max(0, max_chars - 16)].rstrip(' /') + ' / ... (나머지 생략)'
    return result


def parse_candidate_summary(log_text: str) -> Tuple[List[Tuple[str, str, str, str]], List[str], List[str]]:
    """Step 3 후보 행을 손실 없이 파싱한다."""
    parsed: List[Tuple[str, str, str, str]] = []
    invalid_lines: List[str] = []
    duplicate_pairs: List[str] = []
    seen: set[Tuple[str, str]] = set()
    for line_no, raw in enumerate((log_text or '').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        match = _CHANGED_CANDIDATE_RE.match(line)
        if not match:
            invalid_lines.append(f"L{line_no}: {raw}")
            continue
        msg = match.group('msg')
        sig = match.group('sig')
        status = match.group('status').strip()
        key = (msg, sig)
        if key in seen:
            duplicate_pairs.append(f"{msg} : {sig}")
            continue
        seen.add(key)
        parsed.append((msg, sig, status, line))
    return parsed, invalid_lines, duplicate_pairs


_DETAIL_OBS_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)?sec\s+)?(?:CH\d+\s+)?"
    r"(?P<msg>[A-Za-z_][\w\-]*)\s*:\s*(?P<sig>[A-Za-z_][\w\-]*)\s+(?P<tail>.+)$",
    re.IGNORECASE,
)
_VALUE_TOKEN_RE = re.compile(r"0x[0-9A-Fa-f]+|[-+]?\d+(?:\.\d+)?")


def _find_case_detail_file(base_dir: Path, filename: str) -> Optional[Path]:
    candidates = [base_dir / "분석된 txt 파일" / filename, base_dir / filename]
    existing = [p for p in candidates if p.is_file()]
    return max(existing, key=lambda p: p.stat().st_mtime) if existing else None


def collect_observed_values(base_dir: Path, prefix: str, label: str) -> Dict[Tuple[str, str], List[str]]:
    """그룹형 상세와 시간순 상세에서 Message:Signal별 실제 관측값을 순서 보존하여 수집한다."""
    filenames = [f"{prefix} {label}번.txt", f"{prefix} {label}번_시간순.txt"]
    result: Dict[Tuple[str, str], List[str]] = {}
    seen_by_key: Dict[Tuple[str, str], set[str]] = {}
    for filename in filenames:
        path = _find_case_detail_file(base_dir, filename)
        if path is None:
            continue
        for raw in read_text_with_fallback(path).splitlines():
            m = _DETAIL_OBS_RE.match(raw.strip())
            if not m:
                continue
            key = (m.group('msg'), m.group('sig'))
            values = _VALUE_TOKEN_RE.findall(m.group('tail'))
            if not values:
                continue
            bucket = result.setdefault(key, [])
            seen = seen_by_key.setdefault(key, set())
            for value in values:
                normalized = ('0x' + value[2:].upper()) if value.lower().startswith('0x') else value
                if normalized not in seen:
                    seen.add(normalized)
                    bucket.append(normalized)
    return result


def _format_observed_values(values: List[str], max_items: int = 8, max_chars: int = 180) -> str:
    if not values:
        return ''
    text = ' → '.join(values[:max_items])
    if len(values) > max_items:
        text += ' → ...'
    if len(text) > max_chars:
        text = text[:max_chars - 6].rstrip() + ' ...'
    return text


def transform_candidate_summary(
    log_text: str,
    dbc_fallback: dict,
    observed_values: Dict[Tuple[str, str], List[str]],
) -> Tuple[str, List[dict]]:
    candidates, invalid_lines, duplicate_pairs = parse_candidate_summary(log_text)
    if invalid_lines:
        sample = '\n'.join(invalid_lines[:20])
        raise ValueError(
            f"변경된 시그널 모음에서 파싱할 수 없는 후보 행 {len(invalid_lines)}개가 있습니다.\n{sample}"
        )
    if duplicate_pairs:
        sample = ', '.join(duplicate_pairs[:20])
        raise ValueError(f"변경된 시그널 모음에 중복 Message:Signal {len(duplicate_pairs)}개가 있습니다: {sample}")

    blocks: List[str] = []
    manifest_items: List[dict] = []
    emitted_pairs: List[Tuple[str, str]] = []
    for msg, sig, status, raw_line in candidates:
        info = dbc_fallback.get((msg, sig)) or {}
        definition = _truncate_field(info.get('comment', ''), 150)
        description = _truncate_field(info.get('description', ''), 200)
        value_meaning = _format_choice_table(info, max_items=8, max_chars=250)
        observed_text = _format_observed_values(observed_values.get((msg, sig), []))
        blocks.append(
            f"{msg} : {sig} {status}\n"
            f"관측값 : {observed_text}\n"
            f"Definition : {definition}\n"
            f"Description : {description}\n"
            f"값 의미 : {value_meaning}"
        )
        emitted_pairs.append((msg, sig))
        manifest_items.append({
            'message': msg,
            'signal': sig,
            'change_status': status,
            'source_line': raw_line,
            'dbc_matched': bool(info),
            'observed_values': list(observed_values.get((msg, sig), [])),
            'definition': definition,
            'description': description,
            'value_meaning': value_meaning,
        })

    source_pairs = [(msg, sig) for msg, sig, _status, _raw in candidates]
    if source_pairs != emitted_pairs:
        raise RuntimeError('Step 3 후보 순서/집합과 Step 4 출력 후보가 일치하지 않습니다.')
    if len(source_pairs) != len(manifest_items):
        raise RuntimeError('Step 3 후보 수와 Step 4 후보 수가 일치하지 않습니다.')

    return '\n\n'.join(blocks), manifest_items


def build_candidate_ai_prompt(
    tc_label: str,
    tc_class: str,
    tc_text: str,
    tc_expected: str,
    source_txt_name: str,
    candidate_body: str,
    candidate_count: int,
    part_index: int | None = None,
    part_count: int | None = None,
) -> str:
    part_section = ""
    if part_index is not None and part_count is not None and part_count > 1:
        part_section = f"\n[안전 분할 정보]\n{part_index}/{part_count}\n"

    return f"""[파일명]
{source_txt_name}
{part_section}
[TC 정보]
TC 순번: {tc_label}번
TC 분류: {tc_class}
TC 내용: {tc_text}
TC 예상 결과: {tc_expected}

[요청]
아래 후보 시그널 중 위 TC의 사용자 조작, 동작 조건 또는 시스템 반응과 관련 가능성이 있는 Message : Signal을 선정하세요.
후보의 변경 상태, 실제 관측값, DBC Definition, Description, 값 의미를 근거로 판단하세요.

[출력 방법]
1) 첫 줄에는 위 [파일명]을 그대로 기재하세요.
2) 다음 줄에 "연관 있는 메세지"를 기재하세요.
3) 관련 후보는 "Message : Signal // 사유 : ..." 형식으로 한 신호당 한 줄만 작성하세요.
4) 관련 후보가 없으면 "연관 있는 메세지 없음"을 작성하세요.
5) 마지막에는 "연관 없는 메세지"를 제목으로 기재하고, 제외 후보를 "Message : Signal // 사유 : ..." 형식으로 작성하세요.
6) Message Name과 Signal Name은 후보 원문과 정확히 동일하게 유지하세요.
7) 후보에 없는 Message : Signal을 새로 만들지 마세요.
8) 모든 후보를 관련 또는 비관련 중 하나로 빠짐없이 분류하세요.
9) 다른 별도 설명이나 Markdown 코드블록은 작성하지 마세요.

[후보 시그널]
{candidate_body}

후보_시그널수: {candidate_count}
"""


def _candidate_blocks(candidate_body: str) -> List[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", candidate_body or "") if block.strip()]


_PROMPT_CANDIDATE_SECTION_RE = re.compile(
    r"(?ms)^\[후보 시그널\]\s*\r?\n(?P<body>.*?)^\s*후보_시그널수:\s*(?P<count>\d+)\s*$"
)


def _extract_saved_prompt_candidate_pairs(prompt_text: str, *, source_name: str = '') -> List[Tuple[str, str]]:
    """저장된 Step 4 프롬프트에서 실제 후보 블록의 첫 줄만 추출한다.

    프롬프트 전체를 정규식으로 검색하면 Definition/Description 값이 우연히
    ``Word : Word (Text)`` 형태일 때 후보로 오인할 수 있다. 따라서
    ``[후보 시그널]`` ~ ``후보_시그널수:`` 구간만 자르고, 빈 줄로 구분된
    각 5줄 후보 블록의 첫 줄만 후보 형식으로 검증한다.
    """
    match = _PROMPT_CANDIDATE_SECTION_RE.search(prompt_text or '')
    if match is None:
        label = f' ({source_name})' if source_name else ''
        raise RuntimeError(f'Step 4 저장 프롬프트의 후보 구간을 찾지 못했습니다{label}.')

    body = match.group('body')
    declared_count = int(match.group('count'))
    blocks = _candidate_blocks(body)
    pairs: List[Tuple[str, str]] = []
    invalid_blocks: List[str] = []

    for index, block in enumerate(blocks, 1):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        first_line = lines[0]
        candidate_match = _CHANGED_CANDIDATE_RE.fullmatch(first_line)
        if candidate_match is None:
            invalid_blocks.append(f'block {index}: {first_line}')
            continue
        pairs.append((candidate_match.group('msg'), candidate_match.group('sig')))

    if invalid_blocks:
        label = f' ({source_name})' if source_name else ''
        sample = '\n'.join(invalid_blocks[:20])
        raise RuntimeError(
            f'Step 4 저장 프롬프트 후보 블록 첫 줄 형식 오류 {len(invalid_blocks)}개{label}.\n{sample}'
        )

    if len(pairs) != declared_count:
        label = f' ({source_name})' if source_name else ''
        raise RuntimeError(
            f'Step 4 저장 프롬프트 후보 선언 수 불일치{label}: '
            f'declared={declared_count}, parsed={len(pairs)}'
        )

    return pairs


def _partition_candidate_blocks_by_prompt_limit(
    blocks: Sequence[str],
    *,
    max_chars: int,
    tc_label: str,
    tc_class: str,
    tc_text: str,
    tc_expected: str,
    source_txt_name: str,
) -> Tuple[List[List[str]], List[str]]:
    if max_chars <= 0:
        return [list(blocks)], []
    chunks: List[List[str]] = []
    current: List[str] = []
    warnings: List[str] = []

    def render(test_blocks: Sequence[str]) -> str:
        return build_candidate_ai_prompt(
            tc_label=tc_label, tc_class=tc_class, tc_text=tc_text,
            tc_expected=tc_expected, source_txt_name=source_txt_name,
            candidate_body="\n\n".join(test_blocks), candidate_count=len(test_blocks),
            part_index=999, part_count=999,
        )

    for block in blocks:
        proposed = current + [block]
        if current and len(render(proposed)) > max_chars:
            chunks.append(current)
            current = [block]
        else:
            current = proposed
        if len(render([block])) > max_chars:
            warnings.append(f"단일 후보 블록이 안전 상한을 초과함: {len(render([block]))}자 / 상한 {max_chars}자")
    if current or not chunks:
        chunks.append(current)
    return chunks, warnings


def _cleanup_single_prompt_outputs(out_dir: Path, output_base: str) -> None:
    for path in out_dir.glob(f"{output_base}*.txt"):
        if path.is_file():
            try:
                path.unlink()
                print(f"[CLEANUP] 이전 AI문의용 출력 삭제: {path.name}")
            except Exception as exc:
                print(f"[WARN] 이전 출력 삭제 실패: {path} ({exc})")


def write_candidate_prompt_with_safe_split(
    *, out_dir: Path, output_base: str, tc_label: str, tc_class: str,
    tc_text: str, tc_expected: str, source_txt_name: str,
    candidate_body: str, safe_split_max_chars: int,
    max_split_parts_warning: int,
) -> Tuple[List[Path], List[str]]:
    blocks = _candidate_blocks(candidate_body)
    single_prompt = build_candidate_ai_prompt(
        tc_label=tc_label, tc_class=tc_class, tc_text=tc_text,
        tc_expected=tc_expected, source_txt_name=source_txt_name,
        candidate_body="\n\n".join(blocks), candidate_count=len(blocks),
    )
    _cleanup_single_prompt_outputs(out_dir, output_base)
    if len(single_prompt) <= safe_split_max_chars or len(blocks) <= 1:
        output_path = out_dir / f"{output_base}.txt"
        output_path.write_text(single_prompt, encoding="utf-8-sig")
        warnings: List[str] = []
        if len(single_prompt) > safe_split_max_chars:
            warnings.append(f"단일 후보 프롬프트가 안전 상한을 초과함: {len(single_prompt)}자 / 상한 {safe_split_max_chars}자")
        return [output_path], warnings

    chunks, warnings = _partition_candidate_blocks_by_prompt_limit(
        blocks, max_chars=safe_split_max_chars, tc_label=tc_label,
        tc_class=tc_class, tc_text=tc_text, tc_expected=tc_expected,
        source_txt_name=source_txt_name,
    )
    created: List[Path] = []
    part_count = len(chunks)
    if part_count > max_split_parts_warning:
        warnings.append(f"안전 분할 수가 권장 수를 초과함: {part_count}개 / 권장 최대 {max_split_parts_warning}개")
    for idx, chunk in enumerate(chunks, 1):
        suffix = index_to_suffix(idx - 1)
        output_path = out_dir / f"{output_base}_{suffix}.txt"
        prompt = build_candidate_ai_prompt(
            tc_label=tc_label, tc_class=tc_class, tc_text=tc_text,
            tc_expected=tc_expected, source_txt_name=source_txt_name,
            candidate_body="\n\n".join(chunk), candidate_count=len(chunk),
            part_index=idx, part_count=part_count,
        )
        output_path.write_text(prompt, encoding="utf-8-sig")
        created.append(output_path)
        if len(prompt) > safe_split_max_chars:
            warnings.append(f"분할 후에도 상한 초과: {output_path.name} / {len(prompt)}자 / 상한 {safe_split_max_chars}자")
    return created, warnings


def _write_candidate_manifest(
    manifest_dir: Path,
    output_base: str,
    source: Path,
    manifest_items: List[dict],
    prompt_paths: List[Path],
) -> Path:
    import json
    manifest_dir.mkdir(parents=True, exist_ok=True)
    path = manifest_dir / f"{output_base}.candidates.json"
    payload = {
        'status': 'OK',
        'source_file': source.name,
        'candidate_count': len(manifest_items),
        'prompt_files': [p.name for p in prompt_paths],
        'candidates': manifest_items,
    }
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)
    return path


def run(config) -> None:
    base_dir = Path(config.base_dir)
    txt_prefix = config.category_prefix
    excel_path = find_excel_file(base_dir, config.excel_glob)
    output_root = base_dir / config.output_dir
    out_msg_dir = output_root / config.output_dir_msg
    out_time_dir = output_root / config.output_dir_time
    manifest_dir = output_root / '후보목록'
    out_msg_dir.mkdir(parents=True, exist_ok=True)
    out_time_dir.mkdir(parents=True, exist_ok=True)

    _dbc_by_ch, dbc_fallback = _build_dbc_maps(base_dir, dict(config.dbc_name_by_ch))
    tc_class_col_idx = int(config.tc_class_col_idx if hasattr(config, 'tc_class_col_idx') else config.tc_class_column_index)
    tc_col_idx = int(config.tc_col_idx if hasattr(config, 'tc_col_idx') else config.tc_column_index)
    tc_expected_col_idx = int(config.tc_expected_col_idx if hasattr(config, 'tc_expected_col_idx') else 3)
    tc_map = load_tc_map_from_excel(
        excel_path=excel_path, sheet_name=config.category_prefix,
        tc_no_col_idx=int(config.tc_no_column_index),
        tc_class_col_idx=tc_class_col_idx, tc_col_idx=tc_col_idx,
        tc_expected_col_idx=tc_expected_col_idx,
        start_row_excel=int(config.start_row_excel),
        intentional_blank_token=config.intentional_blank_token,
    )

    safe_split_max_chars = int(getattr(config, 'candidate_prompt_safe_split_chars', 90000) or 90000)
    max_split_parts_warning = int(getattr(config, 'candidate_prompt_max_split_parts_warning', 10) or 10)
    source_files = collect_candidate_summary_files(base_dir, txt_prefix)
    if not source_files:
        print('[WARN] Step 4 대상 변경된 시그널 모음 TXT를 찾지 못했습니다.')
        return

    created = 0
    failed = 0
    counters: Dict[int, int] = {}
    for current, source in enumerate(source_files, 1):
        parsed = extract_sort_key_from_filename(source.name)
        if parsed is None:
            print(f"[WARN] TC 번호 추출 실패: {source.name}")
            failed += 1
            continue
        main_num, _sort_tuple, label = parsed
        sub_no = counters.get(main_num, 0) + 1
        counters[main_num] = sub_no
        tc_key = (main_num, sub_no)
        if tc_key not in tc_map:
            tc_key = (main_num, 1)
        if tc_key not in tc_map:
            reason = f"엑셀에서 TC 정보를 찾지 못함: {main_num}-{sub_no}"
            write_error_log_for_input_txt(source, reason=reason)
            print(f"[ERROR] {reason}")
            failed += 1
            continue

        tc_class, tc_text, tc_expected = tc_map[tc_key]
        output_base = f"AI문의용_{txt_prefix}_{label}번"
        warning_path = out_msg_dir / f"{output_base}.warning.txt"
        try:
            source_text = read_text_with_fallback(source)
            observed_values = collect_observed_values(base_dir, txt_prefix, label)
            body, manifest_items = transform_candidate_summary(source_text, dbc_fallback, observed_values)
            candidate_count = len(manifest_items)
            created_paths, split_warnings = write_candidate_prompt_with_safe_split(
                out_dir=out_msg_dir, output_base=output_base, tc_label=label,
                tc_class=tc_class, tc_text=tc_text, tc_expected=tc_expected,
                source_txt_name=source.name, candidate_body=body,
                safe_split_max_chars=safe_split_max_chars,
                max_split_parts_warning=max_split_parts_warning,
            )
            manifest_path = _write_candidate_manifest(
                manifest_dir, output_base, source, manifest_items, created_paths
            )

            # 저장된 프롬프트에서 후보 구간의 각 블록 첫 줄만 읽어 1:1 보존을 검증한다.
            # Definition/Description 줄이 우연히 ``Word : Word (Text)`` 형태여도
            # 후보로 오인하지 않도록 프롬프트 전체 정규식 검색은 사용하지 않는다.
            saved_pairs: List[Tuple[str, str]] = []
            for prompt_path in created_paths:
                saved_pairs.extend(
                    _extract_saved_prompt_candidate_pairs(
                        read_text_with_fallback(prompt_path),
                        source_name=prompt_path.name,
                    )
                )
            source_pairs = [(item['message'], item['signal']) for item in manifest_items]
            if saved_pairs != source_pairs:
                source_set = set(source_pairs)
                saved_set = set(saved_pairs)
                missing_pairs = [pair for pair in source_pairs if pair not in saved_set]
                extra_pairs = [pair for pair in saved_pairs if pair not in source_set]
                raise RuntimeError(
                    "Step 4 저장 후 후보 1:1 검증 실패: "
                    f"source={len(source_pairs)}, prompt={len(saved_pairs)}, "
                    f"missing={missing_pairs[:10]}, extra={extra_pairs[:10]}"
                )

            if split_warnings:
                warning_lines = [
                    '[STEP 4 후보 프롬프트 안전 분할 경고]',
                    f'원본 후보 파일: {source.name}', f'후보 수: {candidate_count}',
                    f'생성 파일 수: {len(created_paths)}', f'안전 상한: {safe_split_max_chars}자',
                    '', '[경고 내용]', *[f'- {item}' for item in split_warnings],
                ]
                warning_path.write_text('\n'.join(warning_lines) + '\n', encoding='utf-8-sig')
            elif warning_path.exists():
                warning_path.unlink()

            remove_error_log_for_input_txt_if_exists(source)
            sizes = ', '.join(f"{p.name}={p.stat().st_size}B" for p in created_paths)
            mode = '단일' if len(created_paths) == 1 else f'예외 안전 분할 {len(created_paths)}개'
            print(
                f"[{current}/{len(source_files)}] [OK] {mode} | candidates={candidate_count} | "
                f"1:1 검증=PASS | manifest={manifest_path.name} | {sizes}"
            )
            created += len(created_paths)
        except Exception as exc:
            write_error_log_for_input_txt(source, reason=f"후보 AI문의용 생성 실패: {exc}", exc=exc)
            print(f"[{current}/{len(source_files)}] [ERROR] {source.name}: {exc}")
            failed += 1

    print('\n[STEP 4 SUMMARY]')
    print(f'대상 후보 파일: {len(source_files)}')
    print(f'생성 프롬프트: {created}')
    print(f'실패: {failed}')
    print('후보 보존 정책: Step 3 Message:Signal 집합과 Step 4 프롬프트 1:1 일치 필수')
    if failed:
        raise RuntimeError(f'Step 4 실패 파일이 있습니다: {failed}개')



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
