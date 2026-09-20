# -*- coding: utf-8 -*-
"""
Requirement Studio - Python-first bootstrap launcher

Double-click this file.
- If .venv + required packages are ready: launch main.py immediately with pythonw.
- Otherwise: show a small Tkinter setup window, create .venv, install
  requirements.txt, then launch main.py.

This bootstrap intentionally uses Python standard-library modules only
before the real PySide6 application starts.
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, ttk


APP_NAME = "Requirement Studio"
ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = ROOT / "main.py"
REQUIREMENTS = ROOT / "requirements.txt"
VENV_DIR = ROOT / ".venv"
VENV_PY = VENV_DIR / "Scripts" / "python.exe"
VENV_PYW = VENV_DIR / "Scripts" / "pythonw.exe"
ICON_ICO = ROOT / "assets" / "RequirementStudio.ico"

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run_capture(command: list[str], *, cwd: Path | None = None, timeout: int | None = None):
    return subprocess.run(
        command,
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def _required_files_ok() -> tuple[bool, str]:
    missing = []
    if not MAIN_PY.is_file():
        missing.append("main.py")
    if not REQUIREMENTS.is_file():
        missing.append("requirements.txt")
    if missing:
        return False, "필수 파일이 없습니다: " + ", ".join(missing)
    return True, ""


def _venv_ready() -> bool:
    if not VENV_PY.is_file() or not VENV_PYW.is_file():
        return False
    try:
        result = _run_capture(
            [str(VENV_PY), "-c", "import PySide6, docx, pptx, pypdf, requests, openai; print(PySide6.__version__)"],
            timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def _launch_main() -> None:
    if not VENV_PYW.is_file():
        raise RuntimeError("가상환경의 pythonw.exe를 찾을 수 없습니다.")

    subprocess.Popen(
        [str(VENV_PYW), str(MAIN_PY)],
        cwd=str(ROOT),
        creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        close_fds=True,
    )


def _show_fatal(message: str) -> None:
    root = tk.Tk()
    root.withdraw()
    try:
        if ICON_ICO.is_file():
            root.iconbitmap(str(ICON_ICO))
    except Exception:
        pass
    messagebox.showerror(APP_NAME, message, parent=root)
    root.destroy()


class SetupWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Requirement Studio 초기 설정")
        self.geometry("620x380")
        self.minsize(540, 320)

        try:
            if ICON_ICO.is_file():
                self.iconbitmap(str(ICON_ICO))
        except Exception:
            pass

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._closing_allowed = False
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()

        self._build_ui()
        self.after(100, self._poll_events)
        threading.Thread(target=self._setup_worker, daemon=True).start()

    def _build_ui(self):
        frame = ttk.Frame(self, padding=22)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Requirement Studio",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            frame,
            text="최초 실행에 필요한 Python 환경을 자동으로 준비합니다.",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(5, 18))

        self.status_var = tk.StringVar(value="환경 확인 중...")
        ttk.Label(
            frame,
            textvariable=self.status_var,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")

        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill="x", pady=(8, 14))
        self.progress.start(12)

        self.log = tk.Text(
            frame,
            height=11,
            wrap="word",
            font=("Consolas", 9),
            bg="#FBFCFE",
            relief="solid",
            borderwidth=1,
        )
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

        self.close_button = ttk.Button(
            frame,
            text="닫기",
            command=self.destroy,
            state="disabled",
        )
        self.close_button.pack(anchor="e", pady=(12, 0))

    def _emit(self, kind: str, text: str):
        self.events.put((kind, text))

    def _append_log(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _poll_events(self):
        try:
            while True:
                kind, text = self.events.get_nowait()
                if kind == "log":
                    self._append_log(text)
                elif kind == "status":
                    self.status_var.set(text)
                elif kind == "done":
                    self.progress.stop()
                    self.status_var.set("설정 완료 · Requirement Studio를 시작합니다.")
                    self._append_log("설정이 완료되었습니다. Requirement Studio를 실행합니다.")
                    self.after(450, self._finish_and_launch)
                elif kind == "error":
                    self.progress.stop()
                    self.status_var.set("설정 실패")
                    self._append_log(text)
                    self._closing_allowed = True
                    self.close_button.configure(state="normal")
                    messagebox.showerror(
                        "Requirement Studio 초기 설정 실패",
                        text + "\n\n위 로그를 확인해주세요.",
                        parent=self,
                    )
        except queue.Empty:
            pass

        if self.winfo_exists():
            self.after(100, self._poll_events)

    def _stream_process(self, command: list[str], description: str):
        self._emit("status", description)
        self._emit("log", f"> {' '.join(command)}")

        proc = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        assert proc.stdout is not None

        for line in proc.stdout:
            self._emit("log", line.rstrip())

        rc = proc.wait()
        if rc != 0:
            raise RuntimeError(f"{description} 실패 (exit code {rc})")

    def _setup_worker(self):
        try:
            ok, error = _required_files_ok()
            if not ok:
                raise RuntimeError(error)

            self._emit("log", f"프로젝트 위치: {ROOT}")
            self._emit("log", f"현재 Python: {sys.executable}")

            if not VENV_PY.is_file():
                self._stream_process(
                    [sys.executable, "-m", "venv", str(VENV_DIR)],
                    "Python 가상환경 생성 중...",
                )
            else:
                self._emit("log", ".venv가 이미 존재합니다.")

            self._stream_process(
                [str(VENV_PY), "-m", "pip", "install", "-r", str(REQUIREMENTS)],
                "필수 Python 패키지 확인/설치 중...",
            )

            verify = _run_capture(
                [str(VENV_PY), "-c", "import PySide6, docx, pptx, pypdf, requests, openai; print('Required packages OK')"],
                timeout=60,
            )
            if verify.returncode != 0:
                raise RuntimeError(
                    "PySide6 확인에 실패했습니다.\n"
                    + (verify.stderr or verify.stdout or "상세 메시지 없음")
                )

            self._emit("log", "필수 Python 패키지 확인 완료")
            self._emit("done", "")

        except Exception as exc:
            detail = f"{exc}\n\n{traceback.format_exc()}"
            self._emit("error", detail)

    def _finish_and_launch(self):
        try:
            _launch_main()
        except Exception as exc:
            self.progress.stop()
            self._closing_allowed = True
            self.close_button.configure(state="normal")
            messagebox.showerror("Requirement Studio 실행 실패", str(exc), parent=self)
            return
        self.destroy()

    def _on_close(self):
        if self._closing_allowed:
            self.destroy()
        else:
            messagebox.showinfo(
                "Requirement Studio 초기 설정",
                "현재 환경을 준비하고 있습니다. 완료 또는 실패 후 창을 닫을 수 있습니다.",
                parent=self,
            )


def main():
    ok, error = _required_files_ok()
    if not ok:
        _show_fatal(error)
        return

    if _venv_ready():
        try:
            _launch_main()
        except Exception as exc:
            _show_fatal(f"Requirement Studio 실행에 실패했습니다.\n\n{exc}")
        return

    app = SetupWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
