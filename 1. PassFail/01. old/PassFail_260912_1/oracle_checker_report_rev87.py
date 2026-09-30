# -*- coding: utf-8 -*-
"""
oracle_checker_report_rev87.py

Oracle Checker 결과 HTML 레포트 생성 모듈.
- GUI의 결과 상세 탭에서 [결과 레포트 출력] 버튼을 누르면 호출된다.
- Report_Sample_Pipeline_Report.html의 카드/표/배지 스타일을 참고하되,
  Oracle Checker의 FinalCheckResult 구조에 맞춰 PASS/FAIL/N/A/ERROR 결과를 정리한다.
- rev87: rev49 레포트 기능을 유지하고 모듈/HTML 생성 표기를 rev87으로 동기화한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import datetime as _dt
import html
import json


_STATUS_LABELS = {
    "PASS": "PASS",
    "FAIL": "FAIL",
    "N/A": "N/A",
    "ERROR": "ERROR",
    "검토중": "검토중",
    "대기중": "대기중",
    "": "-",
    None: "-",
}


def _e(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _text(value: Any, default: str = "-") -> str:
    if value is None:
        return default
    s = str(value)
    return s if s.strip() else default


def _fmt_dt(value: Any) -> str:
    if value is None:
        return "-"
    try:
        if isinstance(value, _dt.datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return str(value)


def _fmt_float(value: Any, ndigits: int = 3) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{ndigits}f}"
    except Exception:
        return str(value)


def _status_norm(status: Any) -> str:
    s = str(status or "").strip()
    if not s:
        return ""
    return s.upper() if s.upper() in {"PASS", "FAIL", "N/A", "ERROR"} else s


def _badge_class(status: Any) -> str:
    s = _status_norm(status)
    if s == "PASS":
        return "ok"
    if s in {"FAIL", "ERROR"}:
        return "error"
    if s == "N/A":
        return "warn"
    return "neutral"


def _badge(status: Any) -> str:
    s = _STATUS_LABELS.get(status, _STATUS_LABELS.get(_status_norm(status), _text(status)))
    return f'<span class="badge {_badge_class(status)}">{_e(s)}</span>'


def _join_expectations(expectations: Iterable[Any]) -> str:
    lines: List[str] = []
    for exp in expectations or []:
        msg = _text(getattr(exp, "message", ""), "")
        sig = _text(getattr(exp, "signal", ""), "")
        val = _text(getattr(exp, "expected_value_raw", ""), "")
        lines.append(f"{msg} : {sig} = {val}")
    return "\n".join(lines) if lines else "-"


def _result_counts(results: List[Any]) -> Dict[str, int]:
    counts = {"PASS": 0, "FAIL": 0, "N/A": 0, "ERROR": 0, "OTHER": 0}
    for result in results:
        s = _status_norm(getattr(result, "final_status", ""))
        if s in counts:
            counts[s] += 1
        else:
            counts["OTHER"] += 1
    return counts


def _iter_check_rows(result: Any, source: str, role: str) -> List[Tuple[Any, Optional[Any]]]:
    """source=realtime/log, role=input/output인 조건과 관측 결과를 짝지어 반환."""
    condition = getattr(result, "condition", None)
    if condition is None:
        return []

    expectations = list(getattr(condition, "input_conditions" if role == "input" else "output_conditions", []) or [])
    check = getattr(result, "realtime_result" if source == "realtime" else "log_result", None)
    checks = []
    if check is not None:
        checks = list(getattr(check, "input_results" if role == "input" else "output_results", []) or [])

    out: List[Tuple[Any, Optional[Any]]] = []
    for idx, exp in enumerate(expectations):
        one = checks[idx] if idx < len(checks) else None
        out.append((exp, one))
    return out


def _condition_table_html(result: Any, source: str, title: str) -> str:
    rows: List[str] = []
    for role, role_name in (("input", "입력"), ("output", "출력")):
        for pos, (exp, one) in enumerate(_iter_check_rows(result, source, role), start=1):
            rows.append(
                "<tr>"
                f"<td class='center'>{_e(role_name)}{pos}</td>"
                f"<td>{_e(getattr(exp, 'message', ''))}</td>"
                f"<td>{_e(getattr(exp, 'signal', ''))}</td>"
                f"<td class='center'>{_e(getattr(exp, 'expected_value_raw', ''))}</td>"
                f"<td class='center'>{_e(_text(getattr(one, 'observed_value_raw', None), '-'))}</td>"
                f"<td class='center'>{_badge(getattr(one, 'status', '') if one is not None else '')}</td>"
                f"<td>{_e(_text(getattr(one, 'message', ''), '-'))}</td>"
                "</tr>"
            )

    if not rows:
        rows.append("<tr><td colspan='7' class='muted center'>표시할 결과 없음</td></tr>")

    return (
        f"<h4>{_e(title)}</h4>"
        "<table class='compact'>"
        "<thead><tr><th>구분</th><th>Message</th><th>Signal</th><th>Expected</th><th>Actual</th><th>상태</th><th>메시지</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _summary_table_html(results: List[Any]) -> str:
    rows: List[str] = []
    for no, result in enumerate(results, start=1):
        c = getattr(result, "condition", None)
        rt = getattr(result, "realtime_result", None)
        lg = getattr(result, "log_result", None)
        rows.append(
            "<tr>"
            f"<td class='center'>{no}</td>"
            f"<td>{_e(getattr(c, 'tc_no', '-'))}</td>"
            f"<td>{_e(getattr(c, 'subcategory', '-'))}</td>"
            f"<td class='center'>{_badge(getattr(result, 'final_status', ''))}</td>"
            f"<td class='center'>{_badge(getattr(rt, 'status', '') if rt is not None else '')}</td>"
            f"<td class='center'>{_badge(getattr(lg, 'status', '') if lg is not None else '')}</td>"
            f"<td class='center'>{_e(_text(getattr(result, 'final_observed_value_raw', None), '-'))}</td>"
            f"<td>{_e(_text(Path(getattr(result, 'used_log_path', '')).name if getattr(result, 'used_log_path', '') else '', '-'))}</td>"
            f"<td>{_e(_text(getattr(result, 'final_message', ''), '-'))}</td>"
            "</tr>"
        )
    if not rows:
        rows.append("<tr><td colspan='9' class='muted center'>표시할 결과 없음</td></tr>")
    return "".join(rows)


def _issue_table_html(results: List[Any]) -> str:
    issue_results = [r for r in results if _status_norm(getattr(r, "final_status", "")) != "PASS"]
    if not issue_results:
        return "<tr><td colspan='5' class='muted center'>FAIL / N/A / ERROR 결과 없음</td></tr>"

    rows: List[str] = []
    for result in issue_results:
        c = getattr(result, "condition", None)
        failed_lines: List[str] = []
        for source, source_name in (("realtime", "실시간"), ("log", "로그")):
            for role, role_name in (("input", "입력"), ("output", "출력")):
                for exp, one in _iter_check_rows(result, source, role):
                    status = _status_norm(getattr(one, "status", "") if one is not None else "")
                    if status and status != "PASS":
                        failed_lines.append(
                            f"{source_name}/{role_name} · {getattr(exp, 'message', '')}:{getattr(exp, 'signal', '')} "
                            f"Expected={getattr(exp, 'expected_value_raw', '')}, "
                            f"Actual={_text(getattr(one, 'observed_value_raw', None), '-')} ({status})"
                        )
        if not failed_lines:
            failed_lines.append(_text(getattr(result, "final_message", ""), "미충족 상세 없음"))

        rows.append(
            "<tr>"
            f"<td>{_e(getattr(c, 'tc_no', '-'))}</td>"
            f"<td>{_e(getattr(c, 'subcategory', '-'))}</td>"
            f"<td class='center'>{_badge(getattr(result, 'final_status', ''))}</td>"
            f"<td><ul class='line-list'>{''.join(f'<li><code>{_e(x)}</code></li>' for x in failed_lines[:8])}</ul></td>"
            f"<td>{_e(_text(getattr(result, 'final_message', ''), '-'))}</td>"
            "</tr>"
        )
    return "".join(rows)


def _detail_cards_html(results: List[Any]) -> str:
    cards: List[str] = []
    for result in results:
        c = getattr(result, "condition", None)
        if c is None:
            continue
        rt = getattr(result, "realtime_result", None)
        lg = getattr(result, "log_result", None)
        inputs = _join_expectations(getattr(c, "input_conditions", [])).splitlines()
        outputs = _join_expectations(getattr(c, "output_conditions", [])).splitlines()

        input_list = "".join(f"<li><code>{_e(x)}</code></li>" for x in inputs) if inputs else "<li class='muted'>없음</li>"
        output_list = "".join(f"<li><code>{_e(x)}</code></li>" for x in outputs) if outputs else "<li class='muted'>없음</li>"

        cards.append(
            "<section class='case-card'>"
            "<div class='case-head'>"
            "<div>"
            f"<h3>TC {_e(getattr(c, 'tc_no', '-'))} · {_e(getattr(c, 'subcategory', '-'))}</h3>"
            f"<p class='muted'>Elapsed: {_e(_fmt_float(getattr(result, 'elapsed_sec', None)))} sec · Used log: {_e(_text(getattr(result, 'used_log_path', None), '-'))}</p>"
            "</div>"
            f"<div>{_badge(getattr(result, 'final_status', ''))}</div>"
            "</div>"
            "<div class='two-col'>"
            "<div>"
            "<h4>TC 내용 / 예상 결과</h4>"
            f"<p><b>내용</b><br>{_e(_text(getattr(c, 'tc_content', ''), '-'))}</p>"
            f"<p><b>예상 결과</b><br>{_e(_text(getattr(c, 'tc_expected_result', ''), '-'))}</p>"
            "</div>"
            "<div>"
            "<h4>입력/출력 조건</h4>"
            f"<p><b>입력 조건</b></p><ul class='line-list'>{input_list}</ul>"
            f"<p><b>출력 조건</b></p><ul class='line-list'>{output_list}</ul>"
            "</div>"
            "</div>"
            "<div class='detail-grid'>"
            f"<div>{_condition_table_html(result, 'realtime', '실시간 판정 상세')}</div>"
            f"<div>{_condition_table_html(result, 'log', '로그 재검토 상세')}</div>"
            "</div>"
            "<div class='final-box'>"
            f"<b>최종 메시지</b><br>{_e(_text(getattr(result, 'final_message', ''), '-'))}<br>"
            f"<span class='muted small'>Started: {_e(_fmt_dt(getattr(result, 'started_at', None)))} / Ended: {_e(_fmt_dt(getattr(result, 'ended_at', None)))}</span>"
            "</div>"
            "</section>"
        )
    return "".join(cards) if cards else "<div class='muted center'>상세 결과 없음</div>"


def _settings_rows_html(settings: Optional[Dict[str, Any]]) -> str:
    settings = settings or {}
    rows = [
        ("Oracle Excel", settings.get("excel_path") or "-"),
        ("차종 시트", settings.get("sheet_name") or "-"),
        ("Bus Name", settings.get("bus_name") or "CAN"),
        ("CANoe 논리 CAN", settings.get("channels") or "-"),
        ("DBC", settings.get("dbc_mapping") or "-"),
        ("로그 폴더", settings.get("log_dir") or "-"),
        ("수동 로그 파일", settings.get("log_file") or "-"),
        ("옵션", settings.get("options") or "-"),
    ]
    return "".join(f"<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>" for k, v in rows)


def _machine_summary(results: List[Any], settings: Optional[Dict[str, Any]], created_at: _dt.datetime) -> Dict[str, Any]:
    counts = _result_counts(results)
    return {
        "created_at": created_at.isoformat(),
        "tool": "Oracle Checker",
        "total_cases": len(results),
        "pass": counts["PASS"],
        "fail": counts["FAIL"],
        "na": counts["N/A"],
        "error": counts["ERROR"],
        "other": counts["OTHER"],
        "settings": settings or {},
        "results": [
            {
                "tc_no": getattr(getattr(r, "condition", None), "tc_no", ""),
                "subcategory": getattr(getattr(r, "condition", None), "subcategory", ""),
                "final_status": getattr(r, "final_status", ""),
                "realtime_status": getattr(getattr(r, "realtime_result", None), "status", ""),
                "log_status": getattr(getattr(r, "log_result", None), "status", ""),
                "observed": getattr(r, "final_observed_value_raw", None),
                "used_log_path": getattr(r, "used_log_path", ""),
                "message": getattr(r, "final_message", ""),
            }
            for r in results
        ],
    }


def build_final_results_report_html(
    results: Iterable[Any],
    settings: Optional[Dict[str, Any]] = None,
    title: str = "Oracle Checker 최종 판정 레포트",
) -> str:
    results = list(results or [])
    created_at = _dt.datetime.now()
    counts = _result_counts(results)
    pass_rate = (counts["PASS"] / len(results) * 100.0) if results else 0.0
    summary_json = json.dumps(_machine_summary(results, settings, created_at), ensure_ascii=False, indent=2, default=str)

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)}</title>
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
  --neutral-bg: #e5e7eb;
  --neutral-text: #374151;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: "Malgun Gothic", "Apple SD Gothic Neo", Arial, sans-serif; background: var(--bg); color: var(--text); }}
.header {{ background: linear-gradient(135deg, #111827, #253452); color: white; padding: 34px 44px; }}
.header h1 {{ margin: 0; font-size: 28px; letter-spacing: -0.03em; }}
.header p {{ margin: 10px 0 0; color: #d1d5db; }}
.container {{ max-width: 1280px; margin: 0 auto; padding: 24px; }}
.card {{ background: var(--paper); border: 1px solid var(--line); border-radius: 16px; padding: 20px; margin-bottom: 18px; box-shadow: 0 8px 24px rgba(15,23,42,.04); }}
.grid {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; }}
.metric {{ background: #f9fafb; border: 1px solid var(--line); border-radius: 14px; padding: 16px; }}
.metric .label {{ color: var(--muted); font-size: 13px; }}
.metric .value {{ font-size: 26px; font-weight: 800; margin-top: 8px; }}
h2 {{ margin: 0 0 14px; font-size: 19px; }}
h3 {{ margin: 0; font-size: 17px; }}
h4 {{ margin: 14px 0 10px; font-size: 14px; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: top; font-size: 14px; }}
th {{ background: #f9fafb; color: #374151; text-align: left; }}
.compact th, .compact td {{ padding: 7px 8px; font-size: 12px; }}
.center {{ text-align: center; }} .right {{ text-align: right; }}
.badge {{ display: inline-flex; align-items:center; border-radius: 999px; padding: 4px 10px; font-weight: 700; font-size: 12px; white-space: nowrap; }}
.badge.ok {{ background: var(--green-bg); color: var(--green-text); }}
.badge.warn {{ background: var(--warn-bg); color: var(--warn-text); }}
.badge.error {{ background: var(--red-bg); color: var(--red-text); }}
.badge.neutral {{ background: var(--neutral-bg); color: var(--neutral-text); }}
.muted {{ color: var(--muted); }} .small {{ font-size: 12px; }}
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.detail-grid {{ display: grid; grid-template-columns: 1fr; gap: 14px; margin-top: 14px; }}
.case-card {{ background: var(--paper); border: 1px solid var(--line); border-radius: 16px; padding: 18px; margin-bottom: 14px; }}
.case-head {{ display:flex; justify-content:space-between; gap: 12px; border-bottom: 1px solid var(--line); padding-bottom: 12px; margin-bottom: 14px; }}
.line-list {{ margin: 0; padding-left: 18px; }}
.line-list li {{ margin: 7px 0; }}
.final-box {{ margin-top: 14px; background: #f9fafb; border: 1px solid var(--line); border-radius: 12px; padding: 12px; }}
code {{ background:#f3f4f6; border:1px solid #e5e7eb; border-radius:8px; padding:2px 5px; white-space:pre-wrap; word-break:break-all; }}
pre {{ white-space: pre-wrap; word-break: break-word; }}
.footer {{ color: var(--muted); font-size: 12px; text-align: center; padding: 24px; }}
@media (max-width: 1000px) {{ .grid {{ grid-template-columns: 1fr 1fr; }} .two-col {{ grid-template-columns: 1fr; }} }}
@media print {{ body {{ background: white; }} .container {{ max-width: none; padding: 12px; }} .card, .case-card {{ box-shadow: none; break-inside: avoid; }} }}
</style>
</head>
<body>
  <header class="header">
    <h1>{_e(title)}</h1>
    <p><span class="badge neutral">Oracle Checker</span> &nbsp; 생성 시각: {_e(created_at.strftime('%Y-%m-%d %H:%M:%S'))} &nbsp;|&nbsp; 결과 수: {_e(len(results))}</p>
  </header>

  <main class="container">
    <section class="grid card">
      <div class="metric"><div class="label">전체 TC 결과</div><div class="value">{len(results)}</div></div>
      <div class="metric"><div class="label">PASS</div><div class="value">{counts['PASS']}</div></div>
      <div class="metric"><div class="label">FAIL</div><div class="value">{counts['FAIL']}</div></div>
      <div class="metric"><div class="label">N/A · ERROR</div><div class="value">{counts['N/A'] + counts['ERROR']}</div></div>
      <div class="metric"><div class="label">PASS율</div><div class="value">{pass_rate:.1f}%</div></div>
    </section>

    <section class="card">
      <h2>1. 실행 설정 요약</h2>
      <table>{_settings_rows_html(settings)}</table>
    </section>

    <section class="card">
      <h2>2. 최종 결과 요약</h2>
      <table>
        <thead><tr><th>No.</th><th>TC</th><th>소분류</th><th>최종</th><th>실시간</th><th>로그</th><th>Observed</th><th>사용 로그</th><th>최종 메시지</th></tr></thead>
        <tbody>{_summary_table_html(results)}</tbody>
      </table>
    </section>

    <section class="card">
      <h2>3. 미충족/오류 요약</h2>
      <table>
        <thead><tr><th>TC</th><th>소분류</th><th>판정</th><th>미충족 조건</th><th>최종 메시지</th></tr></thead>
        <tbody>{_issue_table_html(results)}</tbody>
      </table>
    </section>

    <section class="card">
      <h2>4. 상세 결과</h2>
      {_detail_cards_html(results)}
    </section>

    <section class="card">
      <h2>5. 기계 판독용 요약(JSON)</h2>
      <pre><code>{_e(summary_json)}</code></pre>
    </section>
  </main>

  <div class="footer">Generated by oracle_checker_report_rev87.py</div>
</body>
</html>"""


def export_final_results_to_html(
    results: Iterable[Any],
    output_path: str | Path,
    settings: Optional[Dict[str, Any]] = None,
    title: str = "Oracle Checker 최종 판정 레포트",
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_text = build_final_results_report_html(results, settings=settings, title=title)
    output_path.write_text(html_text, encoding="utf-8")
    return output_path
