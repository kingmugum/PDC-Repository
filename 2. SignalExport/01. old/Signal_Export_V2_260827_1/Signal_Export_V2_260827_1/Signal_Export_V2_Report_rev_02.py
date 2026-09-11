# -*- coding: utf-8 -*-
"""
Signal_Export_V2_Report.py

목적
- AI답변_결과 폴더를 읽어 HTML 레포트 생성
- 실제 결과 파일이 없어도 샘플 모드로 레포트 양식 확인 가능
- main 계열 파일에서 번호가 없는 Report 생성 모듈로 호출 가능

입력 우선순위
1) AI답변_결과/메세지별/*.txt
2) AI답변_결과/시간별/*.txt
3) 위 결과가 없고 report_sample_if_empty=True이면 내장 샘플 데이터로 레포트 생성

출력
- {base_dir}/Report_결과/Pipeline_Report_YYYYMMDD_HHMMSS.html
- {base_dir}/Report_결과/Pipeline_Report_latest.html

[V2 REV 02 변경점]
- Step 5 실제 출력 경로인 AI_문의용_출력/AI답변_결과를 우선 탐색
- 프로젝트 루트/AI답변_결과는 구버전 호환 경로로 fallback
- 결과 개수 집계와 실제 답변 수집이 동일한 후보 경로를 사용하도록 통일

[REV 03 변경점]
- 기존 Step 6 번호를 제거하고 독립 Report 생성 모듈로 분리
- 파일명을 Signal_Export_V2_Report.py로 변경
- 레포트 생성/자동 오픈용 산출물 형식과 기존 기능은 유지
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import html
import json
import re
import shutil


# =========================================================
# Dataclass
# =========================================================
@dataclass
class ReportCase:
    source_file: str
    output_type: str
    tc_label: str
    title: str
    related_lines: List[str] = field(default_factory=list)
    unrelated_lines: List[str] = field(default_factory=list)
    raw_path: str = ""

    @property
    def related_count(self) -> int:
        return len(self.related_lines)

    @property
    def unrelated_count(self) -> int:
        return len(self.unrelated_lines)

    @property
    def verdict(self) -> str:
        return "연관 메세지 있음" if self.related_count > 0 else "연관 메세지 없음"


# =========================================================
# Common helpers
# =========================================================
def _read_text(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp949", "euc-kr"):
        try:
            return path.read_text(encoding=enc, errors="replace")
        except Exception:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _safe_name(value: str) -> str:
    s = re.sub(r"[^0-9A-Za-z가-힣_\-.]+", "_", value or "")
    return s.strip("_") or "report"


def _fmt_int(value: int) -> str:
    return f"{int(value):,}"


def _normalize_folder_name(s: str) -> str:
    return re.sub(r"[\s_\-]+", "", (s or "").strip().lower())


def _find_log_dir_optional(base_dir: Path) -> Optional[Path]:
    targets = {
        _normalize_folder_name("log파일"),
        _normalize_folder_name("log file"),
        _normalize_folder_name("로그파일"),
        _normalize_folder_name("로그폴더"),
    }
    try:
        for p in base_dir.iterdir():
            if p.is_dir() and _normalize_folder_name(p.name) in targets:
                return p
    except Exception:
        return None
    return None


# =========================================================
# File collection
# =========================================================
def _count_project_inputs(base_dir: Path) -> Dict[str, int]:
    counts = {
        "blf": len(list(base_dir.glob("*.blf"))),
        "asc": len(list(base_dir.glob("*.asc"))),
        "dbc": len(list(base_dir.glob("*.dbc"))),
        "xlsx": len(list(base_dir.glob("*.xlsx"))),
    }

    log_dir = _find_log_dir_optional(base_dir)
    if log_dir:
        counts["blf"] += len(list(log_dir.glob("*.blf")))
        counts["asc"] += len(list(log_dir.glob("*.asc")))

    return counts


def _candidate_answer_roots(base_dir: Path, config) -> List[Path]:
    """Step 5 현행 출력 경로를 우선하고 프로젝트 루트 경로는 호환용으로 사용한다."""
    input_root_name = str(getattr(config, "input_root_dir_name", "AI_문의용_출력"))
    output_root_name = str(getattr(config, "output_root_dir_name", "AI답변_결과"))
    candidates = [
        base_dir / input_root_name / output_root_name,
        base_dir / output_root_name,
    ]
    result: List[Path] = []
    seen = set()
    for path in candidates:
        try:
            key = str(path.resolve())
        except Exception:
            key = str(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _collect_output_counts(base_dir: Path, config) -> Dict[str, int]:
    analyzed_dir = base_dir / "분석된 txt 파일"
    ai_request_root = base_dir / getattr(config, "output_dir", "AI_문의용_출력")
    report_root = base_dir / getattr(config, "report_output_dir_name", "Report_결과")

    answer_files: List[Path] = []
    for root in _candidate_answer_roots(base_dir, config):
        if not root.exists():
            continue
        current = [
            p for p in root.rglob("AI답변_*.txt")
            if not p.name.endswith(".error.txt")
        ]
        if current:
            answer_files = current
            break

    return {
        "message_group": len(list(base_dir.glob("*message_group*.txt"))),
        "analyzed_txt": len(list(analyzed_dir.glob("*.txt"))) if analyzed_dir.exists() else 0,
        "ai_request_txt": len(list(ai_request_root.rglob("AI문의용_*.txt"))) if ai_request_root.exists() else 0,
        "ai_answer_txt": len(answer_files),
        "error_txt": len([p for p in base_dir.rglob("*.error.txt") if "__pycache__" not in str(p)]),
        "existing_reports": len(list(report_root.glob("*.html"))) if report_root.exists() else 0,
    }


def _is_probable_split_file(path: Path) -> bool:
    """
    AI답변_..._a.txt / _b.txt 같은 분할 결과를 식별.
    병합본이 있을 경우 분할 파일은 레포트 대상에서 제외한다.
    """
    m = re.match(r"^(?P<base>.+)_(?P<suffix>[a-z]+)$", path.stem, flags=re.IGNORECASE)
    if not m:
        return False
    base_path = path.with_name(m.group("base") + path.suffix)
    return base_path.exists()


def _collect_answer_files(base_dir: Path, config) -> List[Tuple[Path, str]]:
    for root in _candidate_answer_roots(base_dir, config):
        if not root.exists():
            continue
        result: List[Tuple[Path, str]] = []
        for sub_name in getattr(config, "subfolders", ["메세지별", "시간별"]):
            sub_dir = root / sub_name
            if not sub_dir.exists():
                continue
            for p in sorted(sub_dir.glob("AI답변_*.txt"), key=lambda x: x.name):
                if p.name.endswith(".error.txt"):
                    continue
                if _is_probable_split_file(p):
                    continue
                output_type = "시간별" if "시간별" in p.stem or sub_name == "시간별" else "메세지별"
                result.append((p, output_type))
        if result:
            return result
    return []


# =========================================================
# AI answer parsing
# =========================================================
def _extract_tc_label_from_name(name: str) -> str:
    m = re.search(r"(\d+(?:-\d+)*)\s*번", name)
    if m:
        return m.group(1)
    m = re.search(r"_(\d+(?:-\d+)*)", Path(name).stem)
    if m:
        return m.group(1)
    return "-"


def _is_message_line(line: str) -> bool:
    s = (line or "").strip()
    if not s:
        return False
    if s.startswith("#"):
        return False
    if s in ("연관 있는 메세지", "연관 없는 메세지", "연관 있는 메세지 없음"):
        return False
    if s.startswith("AI답변_") or s.startswith("AI문의용_"):
        return False
    return bool(re.match(r"^(?:\d+(?:\.\d+)?sec\s+)?(?:CH\d+\s+)?\w+\s*:\s*\w+\b", s, flags=re.IGNORECASE))


def _split_related_unrelated(text: str) -> Tuple[str, List[str], List[str]]:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in normalized.split("\n")]
    non_empty = [ln.strip() for ln in lines if ln.strip()]
    title = non_empty[0] if non_empty else "-"

    unrelated_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*연관\s*없는\s*메세지\s*(?:[:：]\s*)?$", line.strip()):
            unrelated_idx = i
            break

    if unrelated_idx is None:
        related_part = lines[1:]
        unrelated_part: List[str] = []
    else:
        related_part = lines[1:unrelated_idx]
        unrelated_part = lines[unrelated_idx + 1:]

    related_lines = []
    for ln in related_part:
        s = ln.strip()
        if _is_message_line(s):
            related_lines.append(s)

    unrelated_lines = []
    for ln in unrelated_part:
        s = ln.strip()
        if _is_message_line(s):
            unrelated_lines.append(s)
        elif "//" in s and ":" in s:
            unrelated_lines.append(s)

    return title, related_lines, unrelated_lines


def _parse_answer_file(path: Path, output_type: str) -> ReportCase:
    text = _read_text(path)
    title, related, unrelated = _split_related_unrelated(text)
    return ReportCase(
        source_file=path.name,
        output_type=output_type,
        tc_label=_extract_tc_label_from_name(path.name),
        title=title,
        related_lines=related,
        unrelated_lines=unrelated,
        raw_path=str(path),
    )


def _make_sample_cases() -> List[ReportCase]:
    return [
        ReportCase(
            source_file="AI답변_3. 편의 장치_01번.txt",
            output_type="메세지별",
            tc_label="01",
            title="AI답변_3. 편의 장치_01번.txt",
            related_lines=[
                "BDC_FrDrLockSts : FrDrLockSts 0x00 (Unlock)",
                "BDC_FrDrLockSts : FrDrLockSts 0x01 (Lock)",
                "CLU_DoorWarning : FrDoorWarning 0x01 (ON)",
            ],
            unrelated_lines=[
                "DATC_TempSet : DrTempSet (degC) // 사유 : 공조 온도 설정 신호로 도어 잠금 TC와 직접 관련 낮음",
                "PDC_SonarInfo : RearObjDist (cm) // 사유 : 주차 거리 정보로 본 TC 기대 결과와 무관",
            ],
        ),
        ReportCase(
            source_file="AI답변_3. 편의 장치_02번.txt",
            output_type="메세지별",
            tc_label="02",
            title="AI답변_3. 편의 장치_02번.txt",
            related_lines=[],
            unrelated_lines=[
                "HU_DisplayMode : DisplayMode (Normal) // 사유 : 화면 모드 변경 신호이며 TC 기대 동작과 불일치",
                "AMP_VolumeLevel : VolumeLevel (Level) // 사유 : 오디오 볼륨 신호로 관련성 낮음",
            ],
        ),
        ReportCase(
            source_file="AI답변_3. 편의 장치_03번_시간별.txt",
            output_type="시간별",
            tc_label="03",
            title="AI답변_3. 편의 장치_03번_시간별.txt",
            related_lines=[
                "12.1000sec CH3 PTGM_TailgateCmd : TailgateOpenReq 0x01 (Request)",
                "12.4500sec CH3 PTGM_TailgateSts : TailgateOpenSts 0x01 (Open)",
            ],
            unrelated_lines=[
                "12.3000sec CH4 CLU_TripInfo : TripMode 0x02 // 사유 : 클러스터 표시 모드로 테일게이트 동작과 직접 관련 없음",
            ],
        ),
    ]


# =========================================================
# Error summary
# =========================================================
def _collect_recent_errors(base_dir: Path, limit: int = 8) -> List[Dict[str, str]]:
    errors = [p for p in base_dir.rglob("*.error.txt") if "__pycache__" not in str(p)]
    errors.sort(key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True)

    out = []
    for p in errors[:limit]:
        text = _read_text(p)
        reason = ""
        m = re.search(r"\[실패 사유\]\s*(.+?)(?:\n\n|\Z)", text, flags=re.DOTALL)
        if not m:
            m = re.search(r"\[추정 사유\]\s*(.+?)(?:\n\n|\Z)", text, flags=re.DOTALL)
        if m:
            reason = " ".join(m.group(1).split())
        out.append({
            "file": p.name,
            "path": str(p),
            "reason": reason[:260] if reason else "상세 사유는 error.txt 확인 필요",
        })
    return out


# =========================================================
# HTML rendering
# =========================================================
def _render_badge(text: str, kind: str) -> str:
    return f'<span class="badge {kind}">{_esc(text)}</span>'


def _render_lines(lines: List[str], max_lines: int = 6) -> str:
    if not lines:
        return '<div class="muted">없음</div>'
    shown = lines[:max_lines]
    items = "".join(f"<li><code>{_esc(ln)}</code></li>" for ln in shown)
    more = "" if len(lines) <= max_lines else f'<li class="muted">... 외 {len(lines) - max_lines}개</li>'
    return f"<ul class=\"line-list\">{items}{more}</ul>"


def _build_html(
    *,
    title: str,
    base_dir: Path,
    created_at: datetime,
    config,
    cases: List[ReportCase],
    input_counts: Dict[str, int],
    output_counts: Dict[str, int],
    recent_errors: List[Dict[str, str]],
    is_sample: bool,
) -> str:
    total_cases = len(cases)
    cases_with_related = sum(1 for c in cases if c.related_count > 0)
    cases_without_related = total_cases - cases_with_related
    total_related = sum(c.related_count for c in cases)
    total_unrelated = sum(c.unrelated_count for c in cases)

    active_category = getattr(config, "active_category", "-")
    category_prefix = getattr(config, "category_prefix", "-")
    ai_provider = getattr(config, "ai_provider", "-")
    model = getattr(config, "gpt_model", "-") if ai_provider == "gpt" else getattr(config, "gemini_model", "-")
    dbc_map = getattr(config, "dbc_name_by_ch", {}) or {}

    mode_badge = _render_badge("샘플 레포트", "warn") if is_sample else _render_badge("실제 결과 레포트", "ok")

    dbc_rows = ""
    if dbc_map:
        for ch, dbc in sorted(dbc_map.items(), key=lambda x: str(x[0])):
            dbc_rows += f"<tr><th>CH{_esc(ch)}</th><td>{_esc(dbc)}</td></tr>"
    else:
        dbc_rows = '<tr><th>DBC</th><td class="muted">선택된 DBC 없음</td></tr>'

    case_rows = ""
    for idx, c in enumerate(cases, 1):
        verdict_kind = "ok" if c.related_count > 0 else "warn"
        case_rows += f"""
        <tr>
          <td class="center">{idx}</td>
          <td>{_esc(c.tc_label)}</td>
          <td>{_esc(c.output_type)}</td>
          <td>{_render_badge(c.verdict, verdict_kind)}</td>
          <td class="right">{_fmt_int(c.related_count)}</td>
          <td class="right">{_fmt_int(c.unrelated_count)}</td>
          <td><div class="file-name">{_esc(c.source_file)}</div><div class="muted small">{_esc(c.title)}</div></td>
        </tr>
        """

    detail_cards = ""
    for c in cases:
        detail_cards += f"""
        <section class="case-card">
          <div class="case-head">
            <div>
              <h3>TC { _esc(c.tc_label) } · { _esc(c.output_type) }</h3>
              <p class="muted">{ _esc(c.source_file) }</p>
            </div>
            <div>{ _render_badge(c.verdict, 'ok' if c.related_count > 0 else 'warn') }</div>
          </div>
          <div class="two-col">
            <div>
              <h4>연관 있는 메세지</h4>
              { _render_lines(c.related_lines) }
            </div>
            <div>
              <h4>연관 없는 메세지 / 제외 근거</h4>
              { _render_lines(c.unrelated_lines) }
            </div>
          </div>
        </section>
        """

    error_rows = ""
    if recent_errors:
        for e in recent_errors:
            error_rows += f"<tr><td>{_esc(e['file'])}</td><td>{_esc(e['reason'])}</td></tr>"
    else:
        error_rows = '<tr><td colspan="2" class="muted center">최근 error.txt 없음</td></tr>'

    json_summary = {
        "created_at": created_at.isoformat(),
        "base_dir": str(base_dir),
        "is_sample": is_sample,
        "total_cases": total_cases,
        "cases_with_related": cases_with_related,
        "cases_without_related": cases_without_related,
        "total_related_messages": total_related,
        "total_unrelated_messages": total_unrelated,
        "input_counts": input_counts,
        "output_counts": output_counts,
    }

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>
:root {{
  --bg: #f6f8fb;
  --paper: #ffffff;
  --text: #111827;
  --muted: #6b7280;
  --line: #e5e7eb;
  --dark: #172033;
  --blue: #2563eb;
  --green-bg: #dcfce7;
  --green-text: #166534;
  --warn-bg: #fff7ed;
  --warn-text: #9a3412;
  --red-bg: #fee2e2;
  --red-text: #991b1b;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: "Malgun Gothic", "Apple SD Gothic Neo", Arial, sans-serif; background: var(--bg); color: var(--text); }}
.header {{ background: linear-gradient(135deg, #111827, #253452); color: white; padding: 34px 44px; }}
.header h1 {{ margin: 0; font-size: 28px; letter-spacing: -0.03em; }}
.header p {{ margin: 10px 0 0; color: #d1d5db; }}
.container {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
.card {{ background: var(--paper); border: 1px solid var(--line); border-radius: 16px; padding: 20px; margin-bottom: 18px; box-shadow: 0 8px 24px rgba(15,23,42,.04); }}
.grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }}
.metric {{ background: #f9fafb; border: 1px solid var(--line); border-radius: 14px; padding: 16px; }}
.metric .label {{ color: var(--muted); font-size: 13px; }}
.metric .value {{ font-size: 26px; font-weight: 800; margin-top: 8px; }}
h2 {{ margin: 0 0 14px; font-size: 19px; }}
h3 {{ margin: 0; font-size: 17px; }}
h4 {{ margin: 0 0 10px; font-size: 14px; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: top; font-size: 14px; }}
th {{ background: #f9fafb; color: #374151; text-align: left; }}
.center {{ text-align: center; }} .right {{ text-align: right; }}
.badge {{ display: inline-flex; align-items:center; border-radius: 999px; padding: 4px 10px; font-weight: 700; font-size: 12px; }}
.badge.ok {{ background: var(--green-bg); color: var(--green-text); }}
.badge.warn {{ background: var(--warn-bg); color: var(--warn-text); }}
.badge.error {{ background: var(--red-bg); color: var(--red-text); }}
.muted {{ color: var(--muted); }} .small {{ font-size: 12px; }}
.file-name {{ font-weight: 700; }}
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.case-card {{ background: var(--paper); border: 1px solid var(--line); border-radius: 16px; padding: 18px; margin-bottom: 14px; }}
.case-head {{ display:flex; justify-content:space-between; gap: 12px; border-bottom: 1px solid var(--line); padding-bottom: 12px; margin-bottom: 14px; }}
.line-list {{ margin: 0; padding-left: 18px; }}
.line-list li {{ margin: 7px 0; }}
code {{ background:#f3f4f6; border:1px solid #e5e7eb; border-radius:8px; padding:2px 5px; white-space:pre-wrap; word-break:break-all; }}
.footer {{ color: var(--muted); font-size: 12px; text-align: center; padding: 24px; }}
@media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr 1fr; }} .two-col {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
  <header class="header">
    <h1>{_esc(title)}</h1>
    <p>{mode_badge} &nbsp; 생성 시각: {_esc(created_at.strftime('%Y-%m-%d %H:%M:%S'))} &nbsp;|&nbsp; 프로젝트: {_esc(base_dir)}</p>
  </header>

  <main class="container">
    <section class="grid card">
      <div class="metric"><div class="label">레포트 대상 파일</div><div class="value">{_fmt_int(total_cases)}</div></div>
      <div class="metric"><div class="label">연관 메세지 있음</div><div class="value">{_fmt_int(cases_with_related)}</div></div>
      <div class="metric"><div class="label">연관 메세지 없음</div><div class="value">{_fmt_int(cases_without_related)}</div></div>
      <div class="metric"><div class="label">총 연관 메세지 수</div><div class="value">{_fmt_int(total_related)}</div></div>
    </section>

    <section class="card">
      <h2>1. 실행 설정 요약</h2>
      <table>
        <tr><th>카테고리</th><td>{_esc(active_category)} / {_esc(category_prefix)}</td></tr>
        <tr><th>AI Provider / Model</th><td>{_esc(ai_provider)} / {_esc(model)}</td></tr>
        <tr><th>입력 파일 수</th><td>BLF {_fmt_int(input_counts.get('blf', 0))}개 · ASC {_fmt_int(input_counts.get('asc', 0))}개 · DBC {_fmt_int(input_counts.get('dbc', 0))}개 · XLSX {_fmt_int(input_counts.get('xlsx', 0))}개</td></tr>
        <tr><th>중간/결과 파일 수</th><td>message_group {_fmt_int(output_counts.get('message_group', 0))}개 · 분석 TXT {_fmt_int(output_counts.get('analyzed_txt', 0))}개 · AI 문의용 {_fmt_int(output_counts.get('ai_request_txt', 0))}개 · AI 답변 {_fmt_int(output_counts.get('ai_answer_txt', 0))}개 · error {_fmt_int(output_counts.get('error_txt', 0))}개</td></tr>
        {dbc_rows}
      </table>
    </section>

    <section class="card">
      <h2>2. TC/결과 파일 요약</h2>
      <table>
        <thead><tr><th>No.</th><th>TC</th><th>구분</th><th>판정</th><th>연관</th><th>제외/무관</th><th>파일</th></tr></thead>
        <tbody>{case_rows}</tbody>
      </table>
    </section>

    <section class="card">
      <h2>3. 최근 오류 요약</h2>
      <table><thead><tr><th>파일</th><th>요약</th></tr></thead><tbody>{error_rows}</tbody></table>
    </section>

    <section class="card">
      <h2>4. 상세 결과</h2>
      {detail_cards}
    </section>

    <section class="card">
      <h2>5. 기계 판독용 요약(JSON)</h2>
      <pre><code>{_esc(json.dumps(json_summary, ensure_ascii=False, indent=2))}</code></pre>
    </section>
  </main>

  <div class="footer">Generated by Signal_Export_V2_Report_rev_01.py</div>
</body>
</html>
"""


# =========================================================
# Run
# =========================================================
def generate_report(config) -> Path:
    base_dir = Path(config.base_dir).expanduser().resolve()
    report_dir = base_dir / getattr(config, "report_output_dir_name", "Report_결과")
    report_dir.mkdir(parents=True, exist_ok=True)

    created_at = datetime.now()
    report_title = getattr(config, "report_title", "AI 로그 분석 결과 레포트")
    sample_if_empty = bool(getattr(config, "report_sample_if_empty", True))

    answer_files = _collect_answer_files(base_dir, config)
    cases = [_parse_answer_file(path, output_type) for path, output_type in answer_files]

    is_sample = False
    if not cases and sample_if_empty:
        is_sample = True
        cases = _make_sample_cases()

    input_counts = _count_project_inputs(base_dir)
    output_counts = _collect_output_counts(base_dir, config)
    recent_errors = _collect_recent_errors(base_dir)

    html_text = _build_html(
        title=report_title,
        base_dir=base_dir,
        created_at=created_at,
        config=config,
        cases=cases,
        input_counts=input_counts,
        output_counts=output_counts,
        recent_errors=recent_errors,
        is_sample=is_sample,
    )

    timestamp = created_at.strftime("%Y%m%d_%H%M%S")
    out_path = report_dir / f"Pipeline_Report_{timestamp}.html"
    latest_path = report_dir / "Pipeline_Report_latest.html"

    out_path.write_text(html_text, encoding="utf-8")
    try:
        shutil.copyfile(out_path, latest_path)
    except Exception:
        pass

    print(f"[REPORT] mode = {'sample' if is_sample else 'actual'}")
    print(f"[REPORT] answer_files = {len(answer_files)}")
    print(f"[REPORT] cases = {len(cases)}")
    print(f"[REPORT] saved = {out_path}")
    print(f"[REPORT] latest = {latest_path}")
    return out_path


def run(config) -> None:
    generate_report(config)



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
