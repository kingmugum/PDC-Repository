from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any


_BG = "#F4F7FB"
_PANEL = "#FFFFFF"
_BORDER = "#D8E1EC"
_TEXT = "#172033"
_MUTED = "#66758A"
_BLUE = "#0B73D9"

_CARD_STYLES = {
    "neutral": {"bg": "#EEF2F7", "border": "#D6DEE8", "accent": "#24415F"},
    "attention": {"bg": "#FFF5DD", "border": "#F2CF76", "accent": "#C65A00"},
    "success": {"bg": "#EAF7EE", "border": "#A8D9B4", "accent": "#08752E"},
    "error": {"bg": "#FDECEC", "border": "#F1B5BA", "accent": "#B30D18"},
}

_STATUS_STYLES = {
    "neutral": {"bg": "#EEF2F7", "fg": "#2D3C50"},
    "attention": {"bg": "#FFF0C7", "fg": "#C45A00"},
    "success": {"bg": "#DCF4E4", "fg": "#08752E"},
    "error": {"bg": "#FCE1E3", "fg": "#B30D18"},
    "info": {"bg": "#E8F1FA", "fg": "#24527C"},
}


def _center_window(window: tk.Toplevel, parent: tk.Misc, width: int, height: int) -> None:
    try:
        parent.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = max(0, px + (pw - width) // 2)
        y = max(0, py + (ph - height) // 2)
    except Exception:
        sw = window.winfo_screenwidth()
        sh = window.winfo_screenheight()
        x = max(0, (sw - width) // 2)
        y = max(0, (sh - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def _card(parent: tk.Misc, *, label: str, value: int, tone: str, icon: str) -> tk.Frame:
    style = _CARD_STYLES[tone]
    outer = tk.Frame(parent, bg=style["border"], padx=1, pady=1)
    inner = tk.Frame(outer, bg=style["bg"], padx=18, pady=13)
    inner.pack(fill="both", expand=True)

    tk.Label(
        inner,
        text=icon,
        bg=style["bg"],
        fg=style["accent"],
        font=("Segoe UI Symbol", 23, "bold"),
    ).pack(side="left", padx=(0, 14))

    text_box = tk.Frame(inner, bg=style["bg"])
    text_box.pack(side="left", fill="both", expand=True)
    tk.Label(
        text_box,
        text=label,
        bg=style["bg"],
        fg=_TEXT,
        font=("Segoe UI", 10, "bold"),
        anchor="w",
    ).pack(anchor="w")
    tk.Label(
        text_box,
        text=str(value),
        bg=style["bg"],
        fg=style["accent"],
        font=("Segoe UI", 23, "bold"),
        anchor="w",
    ).pack(anchor="w", pady=(1, 0))
    return outer


def _status_chip(parent: tk.Misc, text: str, tone: str) -> tk.Label:
    style = _STATUS_STYLES.get(tone, _STATUS_STYLES["neutral"])
    return tk.Label(
        parent,
        text=text,
        bg=style["bg"],
        fg=style["fg"],
        padx=14,
        pady=4,
        font=("Segoe UI", 9, "bold"),
        relief="flat",
    )


def _scrollable_details(parent: tk.Misc, details: list[dict[str, str]]) -> None:
    header = tk.Frame(parent, bg="#F7F9FC", height=34)
    header.pack(fill="x")
    header.pack_propagate(False)

    widths = (54, 430, 1)
    tk.Label(header, text="No.", bg="#F7F9FC", fg=_TEXT, font=("Segoe UI", 9, "bold"), width=6).grid(row=0, column=0, sticky="nsew", padx=(4, 0))
    tk.Label(header, text="파일명", bg="#F7F9FC", fg=_TEXT, font=("Segoe UI", 9, "bold"), anchor="w").grid(row=0, column=1, sticky="nsew", padx=(10, 8))
    tk.Label(header, text="사유", bg="#F7F9FC", fg=_TEXT, font=("Segoe UI", 9, "bold"), anchor="w").grid(row=0, column=2, sticky="nsew", padx=(10, 8))
    header.grid_columnconfigure(0, minsize=widths[0])
    header.grid_columnconfigure(1, minsize=widths[1])
    header.grid_columnconfigure(2, weight=1)

    body_wrap = tk.Frame(parent, bg=_PANEL)
    body_wrap.pack(fill="both", expand=True)

    canvas = tk.Canvas(body_wrap, bg=_PANEL, highlightthickness=0, bd=0)
    scrollbar = ttk.Scrollbar(body_wrap, orient="vertical", command=canvas.yview)
    rows = tk.Frame(canvas, bg=_PANEL)
    window_id = canvas.create_window((0, 0), window=rows, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def _on_rows_configure(_event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas_configure(event):
        canvas.itemconfigure(window_id, width=event.width)

    rows.bind("<Configure>", _on_rows_configure)
    canvas.bind("<Configure>", _on_canvas_configure)

    for idx, detail in enumerate(details, start=1):
        row_bg = "#FFFFFF" if idx % 2 else "#FBFCFE"
        row = tk.Frame(rows, bg=row_bg, highlightbackground="#E4EAF1", highlightthickness=1)
        row.pack(fill="x", expand=True)
        row.grid_columnconfigure(0, minsize=widths[0])
        row.grid_columnconfigure(1, minsize=widths[1])
        row.grid_columnconfigure(2, weight=1)

        tk.Label(row, text=str(idx), bg=row_bg, fg=_TEXT, font=("Segoe UI", 9), width=6).grid(row=0, column=0, sticky="ns", padx=(4, 0), pady=9)
        tk.Label(
            row,
            text=detail.get("filename") or "대상 전체",
            bg=row_bg,
            fg=_TEXT,
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=410,
        ).grid(row=0, column=1, sticky="nsew", padx=(10, 8), pady=9)
        tk.Label(
            row,
            text=detail.get("reason") or "-",
            bg=row_bg,
            fg="#344054",
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=460,
        ).grid(row=0, column=2, sticky="nsew", padx=(10, 12), pady=9)

    if not details:
        tk.Label(
            rows,
            text="상세 확인이 필요한 항목이 없습니다.",
            bg=_PANEL,
            fg=_MUTED,
            font=("Segoe UI", 9),
            pady=18,
        ).pack(fill="x")


def show_result_dialog(parent: tk.Misc, model: dict[str, Any]) -> None:
    """Show a single, glanceable modal for BoardRepo upload/download results."""
    host = parent.winfo_toplevel()
    dialog = tk.Toplevel(host)
    dialog.title(str(model.get("title") or "BoardRepo 결과 확인"))
    dialog.configure(bg=_BG)
    dialog.resizable(True, True)
    dialog.minsize(920, 620)
    dialog.transient(host)

    target_rows = list(model.get("target_rows") or [])
    details = list(model.get("details") or [])
    height = min(840, max(650, 540 + min(len(details), 5) * 34))
    _center_window(dialog, host, 1060, height)

    header = tk.Frame(dialog, bg="#F7FAFE", padx=22, pady=16)
    header.pack(fill="x")
    tk.Label(
        header,
        text="▣",
        bg="#F7FAFE",
        fg="#163A63",
        font=("Segoe UI Symbol", 18, "bold"),
    ).pack(side="left", padx=(0, 10))
    tk.Label(
        header,
        text=str(model.get("title") or "BoardRepo 결과 확인"),
        bg="#F7FAFE",
        fg="#10233F",
        font=("Segoe UI", 16, "bold"),
    ).pack(side="left")

    close_btn = tk.Button(
        header,
        text="×",
        command=dialog.destroy,
        bg="#F7FAFE",
        fg="#22344A",
        activebackground="#E9EFF6",
        activeforeground="#22344A",
        relief="flat",
        bd=0,
        font=("Segoe UI", 18),
        cursor="hand2",
        padx=5,
    )
    close_btn.pack(side="right")

    content = tk.Frame(dialog, bg=_BG, padx=20, pady=18)
    content.pack(fill="both", expand=True)

    counts = model.get("counts") or {}
    cards = tk.Frame(content, bg=_BG)
    cards.pack(fill="x")
    card_specs = [
        ("미선택", int(counts.get("unselected", 0)), "neutral", "▤"),
        ("확인 필요", int(counts.get("attention", 0)), "attention", "⚠"),
        ("실행 완료", int(counts.get("success", 0)), "success", "✓"),
        ("오류", int(counts.get("error", 0)), "error", "✕"),
    ]
    for col, (label, value, tone, icon) in enumerate(card_specs):
        cards.grid_columnconfigure(col, weight=1, uniform="cards")
        widget = _card(cards, label=label, value=value, tone=tone, icon=icon)
        widget.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 7, 0 if col == 3 else 7))

    target_panel = tk.Frame(content, bg=_BORDER, padx=1, pady=1)
    target_panel.pack(fill="x", pady=(18, 0))
    target_inner = tk.Frame(target_panel, bg=_PANEL)
    target_inner.pack(fill="x")
    tk.Label(
        target_inner,
        text=f"{model.get('operation_label', '처리')} 대상 목록 ({len(target_rows)}개)",
        bg="#F7F9FC",
        fg=_TEXT,
        font=("Segoe UI", 11, "bold"),
        anchor="w",
        padx=18,
        pady=10,
    ).pack(fill="x")

    for idx, row_info in enumerate(target_rows, start=1):
        row = tk.Frame(target_inner, bg=_PANEL, height=39)
        row.pack(fill="x")
        row.pack_propagate(False)
        if idx > 1:
            tk.Frame(row, bg="#E7ECF2", height=1).pack(fill="x", side="top")
        tk.Label(row, text=str(idx), width=5, bg=_PANEL, fg=_TEXT, font=("Segoe UI", 9)).pack(side="left", padx=(8, 2))
        tk.Label(
            row,
            text=str(row_info.get("label") or row_info.get("key") or "-"),
            bg=_PANEL,
            fg=_TEXT,
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(side="left", fill="x", expand=True, padx=(8, 8))
        chip = _status_chip(row, str(row_info.get("status") or "-"), str(row_info.get("tone") or "neutral"))
        chip.pack(side="right", padx=(8, 18), pady=6)

    detail_panel = tk.Frame(content, bg=_CARD_STYLES["attention"]["border"], padx=1, pady=1)
    detail_panel.pack(fill="both", expand=True, pady=(18, 0))
    detail_inner = tk.Frame(detail_panel, bg=_PANEL)
    detail_inner.pack(fill="both", expand=True)

    detail_head = tk.Frame(detail_inner, bg="#FFF8E7", padx=16, pady=10)
    detail_head.pack(fill="x")
    tk.Label(detail_head, text="⚠", bg="#FFF8E7", fg="#C45A00", font=("Segoe UI Symbol", 14, "bold")).pack(side="left", padx=(0, 8))
    tk.Label(
        detail_head,
        text=str(model.get("details_title") or f"확인 필요 항목 ({len(details)}개)"),
        bg="#FFF8E7",
        fg=_TEXT,
        font=("Segoe UI", 11, "bold"),
    ).pack(side="left")
    note = str(model.get("details_note") or "")
    if note:
        tk.Label(
            detail_head,
            text=note,
            bg="#FFF8E7",
            fg="#5E5A4B",
            font=("Segoe UI", 9),
            anchor="e",
        ).pack(side="right")

    _scrollable_details(detail_inner, details)

    footer = tk.Frame(dialog, bg=_BG, pady=16)
    footer.pack(fill="x")
    ok = tk.Button(
        footer,
        text="확인",
        command=dialog.destroy,
        width=16,
        bg=_BLUE,
        fg="white",
        activebackground="#075FAF",
        activeforeground="white",
        relief="flat",
        bd=0,
        font=("Segoe UI", 10, "bold"),
        pady=8,
        cursor="hand2",
    )
    ok.pack()

    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    dialog.bind("<Escape>", lambda _e: dialog.destroy())
    dialog.bind("<Return>", lambda _e: dialog.destroy())
    dialog.grab_set()
    dialog.focus_force()


def _display_label(target: dict[str, Any], key: str) -> str:
    import re
    label = str(target.get("ui_label") or target.get("display_name") or key)
    return re.sub(r"^\s*\d+\.\s*", "", label).strip() or key


def build_upload_result_model(
    targets: dict[str, dict[str, Any]],
    selected: list[str],
    successes: list[Any],
    duplicates: list[Any],
    attention_results: list[Any],
    local_issues: list[Any],
    failures: list[tuple[Any, str]],
    *,
    common_stop: bool = False,
    common_detail: str | None = None,
) -> dict[str, Any]:
    selected_set = set(selected)
    by_key: dict[str, dict[str, int]] = {
        key: {"success": 0, "duplicate": 0, "attention": 0, "error": 0}
        for key in targets
    }

    for item in successes:
        if item.target_key in by_key:
            by_key[item.target_key]["success"] += 1
    for result in duplicates:
        key = result.item.target_key
        if key in by_key:
            by_key[key]["duplicate"] += 1
    for result in attention_results:
        key = result.item.target_key
        if key in by_key:
            by_key[key]["attention"] += 1
    for issue in local_issues:
        if issue.target_key in by_key:
            by_key[issue.target_key]["attention"] += 1
    for item, _message in failures:
        if item.target_key in by_key:
            by_key[item.target_key]["error"] += 1

    if common_stop:
        for key in selected_set:
            if key in by_key:
                by_key[key]["error"] = max(1, by_key[key]["error"])

    target_rows = []
    for key, target in targets.items():
        if key not in selected_set:
            status, tone = "미선택", "neutral"
        else:
            c = by_key[key]
            if c["error"]:
                parts = [f"오류 ({c['error']})"]
                if c["attention"]:
                    parts.append(f"확인 {c['attention']}")
                if c["success"]:
                    parts.append(f"완료 {c['success']}")
                status, tone = " / ".join(parts), "error"
            elif c["attention"]:
                parts = [f"⚠ 확인 필요 ({c['attention']})"]
                if c["success"]:
                    parts.append(f"완료 {c['success']}")
                status, tone = " / ".join(parts), "attention"
            elif c["success"]:
                status, tone = f"실행 완료 ({c['success']})", "success"
            elif c["duplicate"]:
                status, tone = f"중복 Skip ({c['duplicate']})", "info"
            else:
                status, tone = "처리할 파일 없음", "neutral"
        target_rows.append({
            "key": key,
            "label": _display_label(target, key),
            "status": status,
            "tone": tone,
        })

    details: list[dict[str, str]] = []
    for result in attention_results:
        details.append({
            "filename": result.item.file_path.name,
            "reason": result.evidence,
        })
    for issue in local_issues:
        details.append({
            "filename": issue.file_name or "대상 전체",
            "reason": issue.message,
        })
    for item, message in failures:
        details.append({
            "filename": item.file_path.name,
            "reason": f"업로드 오류: {message}",
        })
    if common_detail:
        details.append({"filename": "공통 세션", "reason": common_detail})

    if details:
        details_title = f"확인 필요 항목 ({len(details)}개)"
        details_note = "아래 항목은 자동 처리되지 않았거나 추가 확인이 필요합니다."
    elif duplicates:
        for result in duplicates:
            details.append({
                "filename": result.item.file_path.name,
                "reason": result.evidence,
            })
        details_title = f"중복 Skip 항목 ({len(details)}개)"
        details_note = "이미 게시판에 존재하여 안전하게 업로드하지 않은 항목입니다."
    else:
        for item in successes:
            details.append({"filename": item.file_path.name, "reason": "업로드 완료"})
        details_title = f"처리 완료 항목 ({len(details)}개)"
        details_note = "BoardRepo 업로드 처리가 완료되었습니다."

    return {
        "title": "업로드 결과 확인",
        "operation_label": "업로드",
        "counts": {
            "unselected": sum(1 for key in targets if key not in selected_set),
            "attention": len(attention_results) + len(local_issues),
            "success": len(successes),
            "error": len(failures) + (1 if common_stop and not failures else 0),
        },
        "target_rows": target_rows,
        "details_title": details_title,
        "details_note": details_note,
        "details": details,
    }


def build_download_result_model(
    targets: dict[str, dict[str, Any]],
    selected: list[str],
    results: list[Any],
    local_issues: list[Any],
) -> dict[str, Any]:
    selected_set = set(selected)
    by_key: dict[str, list[Any]] = {key: [] for key in targets}
    for result in results:
        by_key.setdefault(result.target_key, []).append(result)

    issue_count: dict[str, int] = {}
    for issue in local_issues:
        issue_count[issue.target_key] = issue_count.get(issue.target_key, 0) + 1

    labels = {
        "DOWNLOADED": "다운로드",
        "UP_TO_DATE": "이미 최신",
        "LOCAL_NEWER": "로컬이 더 최신",
        "REMOTE_NONE": "원격 없음",
        "CONFLICT": "확인 필요",
        "ERROR": "오류",
    }

    target_rows = []
    for key, target in targets.items():
        if key not in selected_set:
            status, tone = "미선택", "neutral"
        else:
            counts: dict[str, int] = {}
            for result in by_key.get(key, []):
                counts[result.status] = counts.get(result.status, 0) + 1
            if issue_count.get(key):
                counts["CONFLICT"] = counts.get("CONFLICT", 0) + issue_count[key]

            if counts.get("ERROR"):
                status, tone = f"오류 ({counts['ERROR']})", "error"
            elif counts.get("CONFLICT"):
                status, tone = f"⚠ 확인 필요 ({counts['CONFLICT']})", "attention"
            elif counts.get("DOWNLOADED"):
                status, tone = f"다운로드 ({counts['DOWNLOADED']})", "success"
            elif counts.get("UP_TO_DATE"):
                status, tone = f"이미 최신 ({counts['UP_TO_DATE']})", "success"
            elif counts.get("LOCAL_NEWER"):
                status, tone = f"로컬이 더 최신 ({counts['LOCAL_NEWER']})", "info"
            elif counts.get("REMOTE_NONE"):
                status, tone = "원격 없음", "neutral"
            else:
                status, tone = "처리 결과 없음", "neutral"

            # Preserve mixed target information without making the chip unreadable.
            nonzero = [(labels.get(k, k), v) for k, v in counts.items() if v]
            if len(nonzero) > 1 and tone not in {"error", "attention"}:
                status = " / ".join(f"{name} {count}" for name, count in nonzero[:3])

        target_rows.append({
            "key": key,
            "label": _display_label(target, key),
            "status": status,
            "tone": tone,
        })

    conflicts = [r for r in results if r.status == "CONFLICT"]
    errors = [r for r in results if r.status == "ERROR"]
    downloaded = [r for r in results if r.status == "DOWNLOADED"]
    up_to_date = [r for r in results if r.status == "UP_TO_DATE"]

    details: list[dict[str, str]] = []
    for result in conflicts:
        details.append({"filename": result.filename or "대상 전체", "reason": result.reason})
    for issue in local_issues:
        details.append({"filename": issue.file_name or "대상 전체", "reason": issue.message})
    for result in errors:
        details.append({"filename": result.filename or "대상 전체", "reason": f"다운로드 오류: {result.reason}"})

    if details:
        details_title = f"확인 필요 항목 ({len(details)}개)"
        details_note = "아래 항목은 자동 처리되지 않았거나 추가 확인이 필요합니다."
    else:
        show_results = [r for r in results if r.filename]
        for result in show_results:
            reason = result.reason or labels.get(result.status, result.status)
            details.append({"filename": result.filename, "reason": reason})
        details_title = f"처리 결과 상세 ({len(details)}개)"
        details_note = "BoardRepo 다운로드 동기화 결과입니다."

    return {
        "title": "다운로드 결과 확인",
        "operation_label": "다운로드",
        "counts": {
            "unselected": sum(1 for key in targets if key not in selected_set),
            "attention": len(conflicts) + len(local_issues),
            "success": len(downloaded) + len(up_to_date),
            "error": len(errors),
        },
        "target_rows": target_rows,
        "details_title": details_title,
        "details_note": details_note,
        "details": details,
    }
