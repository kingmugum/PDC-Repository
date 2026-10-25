from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from credential_store import CredentialStoreError, get_saved_username, save_credentials


def prompt_password_refresh(parent, username: str | None = None, reason: str = "") -> bool:
    """Ask for a replacement password while keeping the saved ID visible/read-only.

    Returns True only after the new password is safely stored in the OS keyring.
    """
    try:
        username = (username or get_saved_username() or "").strip()
    except CredentialStoreError as exc:
        messagebox.showerror("로그인 정보 확인", str(exc), parent=parent)
        return False

    if not username:
        messagebox.showwarning(
            "로그인 정보 확인",
            "저장된 그룹웨어 ID를 찾지 못했습니다. 먼저 [로그인 정보 저장/갱신]에서 ID와 비밀번호를 저장해주세요.",
            parent=parent,
        )
        return False

    dialog = tk.Toplevel(parent)
    dialog.title("그룹웨어 로그인 정보 갱신")
    dialog.transient(parent.winfo_toplevel())
    dialog.grab_set()
    dialog.resizable(False, False)

    result = {"saved": False}
    frame = ttk.Frame(dialog, padding=18)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text="그룹웨어 로그인 정보 확인 필요", font=("Segoe UI", 12, "bold")).grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
    )
    ttk.Label(
        frame,
        text=(
            "저장된 로그인 정보로 접속하지 못했습니다.\n"
            "비밀번호가 변경되었다면 새 비밀번호만 입력하면 됩니다.\n"
            "※ MFA/CAPTCHA, 계정 잠금, 네트워크 문제도 원인일 수 있습니다."
        ),
        justify="left",
        wraplength=470,
    ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

    if reason:
        ttk.Label(frame, text=f"확인 내용: {reason}", foreground="#666666", wraplength=470).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )

    ttk.Label(frame, text="ID").grid(row=3, column=0, sticky="w", padx=(0, 12), pady=4)
    id_var = tk.StringVar(value=username)
    id_entry = ttk.Entry(frame, textvariable=id_var, width=38, state="readonly")
    id_entry.grid(row=3, column=1, sticky="ew", pady=4)

    ttk.Label(frame, text="새 비밀번호").grid(row=4, column=0, sticky="w", padx=(0, 12), pady=4)
    pw_var = tk.StringVar()
    pw_entry = ttk.Entry(frame, textvariable=pw_var, width=38, show="*")
    pw_entry.grid(row=4, column=1, sticky="ew", pady=4)

    hint = ttk.Label(
        frame,
        text="비밀번호는 config.json/로그/ZIP에 기록하지 않고 운영체제 자격 증명 저장소에만 저장합니다.",
        foreground="#666666",
        wraplength=470,
    )
    hint.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 14))

    buttons = ttk.Frame(frame)
    buttons.grid(row=6, column=0, columnspan=2, sticky="e")

    def save_and_close():
        password = pw_var.get()
        if not password:
            messagebox.showwarning("비밀번호 입력", "새 비밀번호를 입력해주세요.", parent=dialog)
            pw_entry.focus_set()
            return
        try:
            save_credentials(username, password)
        except CredentialStoreError as exc:
            messagebox.showerror("저장 실패", str(exc), parent=dialog)
            return
        result["saved"] = True
        dialog.destroy()

    ttk.Button(buttons, text="취소", command=dialog.destroy, width=10).pack(side="right")
    ttk.Button(
        buttons, text="저장 후 다시 로그인", command=save_and_close, width=18
    ).pack(side="right", padx=(0, 8))

    dialog.bind("<Return>", lambda _e: save_and_close())
    dialog.bind("<Escape>", lambda _e: dialog.destroy())
    frame.columnconfigure(1, weight=1)
    dialog.update_idletasks()

    # Center over the application window.
    try:
        owner = parent.winfo_toplevel()
        x = owner.winfo_rootx() + max(0, (owner.winfo_width() - dialog.winfo_width()) // 2)
        y = owner.winfo_rooty() + max(0, (owner.winfo_height() - dialog.winfo_height()) // 2)
        dialog.geometry(f"+{x}+{y}")
    except Exception:
        pass

    pw_entry.focus_set()
    parent.wait_window(dialog)
    return bool(result["saved"])
