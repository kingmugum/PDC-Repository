# -*- coding: utf-8 -*-
"""
PDC Version Manager
- 표준 라이브러리만 사용 (Tkinter)
- Git CLI를 백엔드로 사용
- 프로젝트 여러 개 등록
- 최신 버전 받기 (git pull --ff-only)
- 새 버전 업로드 (git add/commit/tag/push)
- 버전명 자동 생성: YYMMDD_N
- 커밋/태그 이력 보기
- 원격 저장소 Clone
- Version Manager Release ZIP 자동 적용(직접 압축 해제 불필요)
- Pull로 자기 자신이 갱신되면 재실행 안내

주의:
1) PC에 Git이 설치되어 있어야 합니다.
2) GitHub/GitLab 등 원격 저장소 인증은 Git Credential Manager/SSH 등 기존 Git 인증을 사용합니다.
3) 샘플은 충돌을 임의로 해결하지 않습니다. 로컬 변경 또는 원격 선행 상태가 있으면 안전하게 중단합니다.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import zipfile
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog


APP_NAME = "PDC Version Manager"
APP_VERSION = "260809_3"
ROOT_MANAGER_FILENAME = "PDC_Version_Manager.py"
REQUIREMENTS_FILENAME = "PDC_Version_Manager_Requirements.xlsx"
CONFIG_DIR = Path.home() / ".pdc_version_manager"
CONFIG_FILE = CONFIG_DIR / "projects.json"
VERSION_RE = re.compile(r"^(?P<date>\d{6})_(?P<num>\d+)$")


@dataclass
class Project:
    name: str
    path: str


class GitError(RuntimeError):
    pass


def file_sha256(path: Path) -> str:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def run_git(repo: Path | None, *args: str, timeout: int = 120) -> str:
    cmd = ["git"]
    if repo is not None:
        cmd += ["-C", str(repo)]
    cmd += list(args)

    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW

    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=flags,
        )
    except FileNotFoundError as e:
        raise GitError("Git을 찾을 수 없습니다. 먼저 Git for Windows를 설치해 주세요.") from e
    except subprocess.TimeoutExpired as e:
        raise GitError("Git 명령 실행 시간이 초과되었습니다.") from e

    if p.returncode != 0:
        msg = (p.stderr or p.stdout or "Git 명령 실패").strip()
        raise GitError(msg)
    return (p.stdout or "").strip()


def is_git_repo(path: Path) -> bool:
    try:
        return run_git(path, "rev-parse", "--is-inside-work-tree") == "true"
    except Exception:
        return False


def current_branch(repo: Path) -> str:
    return run_git(repo, "branch", "--show-current") or "(detached)"


def local_changes(repo: Path) -> bool:
    return bool(run_git(repo, "status", "--porcelain"))


def origin_url(repo: Path) -> str:
    try:
        return run_git(repo, "remote", "get-url", "origin")
    except GitError:
        return ""


def latest_version_tag(tags: list[str]) -> str:
    parsed = []
    for tag in tags:
        m = VERSION_RE.match(tag)
        if m:
            parsed.append((m.group("date"), int(m.group("num")), tag))
    if not parsed:
        return "-"
    parsed.sort()
    return parsed[-1][2]


def local_tags(repo: Path) -> list[str]:
    out = run_git(repo, "tag", "--list")
    return [x.strip() for x in out.splitlines() if x.strip()]


def remote_tags(repo: Path) -> list[str]:
    if not origin_url(repo):
        return []
    out = run_git(repo, "ls-remote", "--tags", "--refs", "origin")
    tags = []
    for line in out.splitlines():
        if "refs/tags/" in line:
            tags.append(line.split("refs/tags/", 1)[1].strip())
    return tags


def next_version_tag(repo: Path) -> str:
    today = datetime.now().strftime("%y%m%d")
    nums = []
    for tag in set(local_tags(repo) + remote_tags(repo)):
        m = VERSION_RE.match(tag)
        if m and m.group("date") == today:
            nums.append(int(m.group("num")))
    return f"{today}_{max(nums, default=0) + 1}"


def tracking_divergence(repo: Path) -> tuple[int, int] | None:
    """
    return (ahead, behind)
    upstream이 없으면 None.
    """
    try:
        out = run_git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
        left, right = out.split()
        return int(left), int(right)
    except Exception:
        return None


def git_identity_ok(repo: Path) -> bool:
    try:
        name = run_git(repo, "config", "user.name")
        email = run_git(repo, "config", "user.email")
        return bool(name and email)
    except Exception:
        try:
            name = run_git(None, "config", "--global", "user.name")
            email = run_git(None, "config", "--global", "user.email")
            return bool(name and email)
        except Exception:
            return False


class HistoryWindow(tk.Toplevel):
    def __init__(self, master, repo: Path, project_name: str):
        super().__init__(master)
        self.title(f"{project_name} - 이력")
        self.geometry("900x520")
        self.repo = repo

        top = ttk.Frame(self, padding=10)
        top.pack(fill="both", expand=True)

        ttk.Label(top, text=f"프로젝트: {project_name}", font=("맑은 고딕", 12, "bold")).pack(anchor="w")

        cols = ("hash", "date", "tag", "message")
        self.tree = ttk.Treeview(top, columns=cols, show="headings")
        self.tree.heading("hash", text="Commit")
        self.tree.heading("date", text="날짜")
        self.tree.heading("tag", text="Tag")
        self.tree.heading("message", text="변경 내용")
        self.tree.column("hash", width=90, anchor="center")
        self.tree.column("date", width=150, anchor="center")
        self.tree.column("tag", width=130, anchor="center")
        self.tree.column("message", width=470)

        y = ttk.Scrollbar(top, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=y.set)
        self.tree.pack(side="left", fill="both", expand=True, pady=(10, 0))
        y.pack(side="right", fill="y", pady=(10, 0))

        self.load()

    def load(self):
        try:
            fmt = "%h%x09%ad%x09%D%x09%s"
            out = run_git(
                self.repo,
                "log",
                "--date=format:%Y-%m-%d %H:%M",
                f"--pretty=format:{fmt}",
                "-100",
            )
            for line in out.splitlines():
                parts = line.split("\t", 3)
                if len(parts) != 4:
                    continue
                h, date, decorations, msg = parts
                tags = re.findall(r"tag: ([^,\)]+)", decorations)
                tag = ", ".join(tags)
                self.tree.insert("", "end", values=(h, date, tag, msg))
        except Exception as e:
            messagebox.showerror(APP_NAME, str(e), parent=self)


class UploadDialog(tk.Toplevel):
    def __init__(self, master, project_name: str, next_tag: str):
        super().__init__(master)
        self.title("새 버전 업로드")
        self.geometry("560x360")
        self.resizable(False, False)
        self.result = None
        self.transient(master)
        self.grab_set()

        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text=project_name, font=("맑은 고딕", 13, "bold")).pack(anchor="w")
        ttk.Label(frm, text=f"새 버전: {next_tag}", font=("맑은 고딕", 11)).pack(anchor="w", pady=(8, 16))

        ttk.Label(frm, text="이번 변경 내용을 입력하세요.").pack(anchor="w")
        self.text = tk.Text(frm, height=9, wrap="word")
        self.text.pack(fill="both", expand=True, pady=(6, 12))
        self.text.focus_set()

        btn = ttk.Frame(frm)
        btn.pack(fill="x")
        ttk.Button(btn, text="취소", command=self.destroy).pack(side="right")
        ttk.Button(btn, text="업로드", command=lambda: self.ok(next_tag)).pack(side="right", padx=(0, 8))

    def ok(self, tag):
        msg = self.text.get("1.0", "end").strip()
        if not msg:
            messagebox.showwarning(APP_NAME, "변경 내용을 입력해 주세요.", parent=self)
            return
        self.result = (tag, msg)
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1180x650")
        self.minsize(980, 560)
        self.projects: list[Project] = []
        self.busy = False

        self.create_ui()
        self.load_projects()
        self.auto_register_self_repo()
        self.after(250, self.refresh_all)

    def create_ui(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x")
        ttk.Label(header, text=APP_NAME, font=("맑은 고딕", 17, "bold")).pack(side="left")
        ttk.Label(
            header,
            text=f"v{APP_VERSION} · Git 기반 개인 프로그램 버전/동기화 관리자",
        ).pack(side="left", padx=(12, 0), pady=(5, 0))

        actions = ttk.Frame(root)
        actions.pack(fill="x", pady=(12, 8))

        ttk.Button(actions, text="로컬 프로젝트 등록", command=self.add_local).pack(side="left")
        ttk.Button(actions, text="원격 저장소 Clone", command=self.clone_repo).pack(side="left", padx=6)
        ttk.Button(actions, text="원격 연결 설정", command=self.configure_remote).pack(side="left")
        ttk.Button(actions, text="Git 사용자 설정", command=self.configure_identity).pack(side="left", padx=6)
        ttk.Button(actions, text="등록 제거", command=self.remove_project).pack(side="left")
        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(actions, text="새로고침", command=self.refresh_all).pack(side="left")
        ttk.Button(actions, text="최신 버전 받기 (Pull)", command=self.pull_selected).pack(side="left", padx=6)
        ttk.Button(actions, text="새 버전 업로드 (Commit + Push)", command=self.upload_selected).pack(side="left")
        ttk.Button(actions, text="Version Manager 업데이트 적용", command=self.apply_manager_update).pack(side="left", padx=6)
        ttk.Button(actions, text="이력 보기", command=self.history_selected).pack(side="left")
        ttk.Button(actions, text="폴더 열기", command=self.open_folder).pack(side="left", padx=6)

        cols = ("name", "path", "branch", "local", "remote", "state")
        self.tree = ttk.Treeview(root, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("name", text="프로젝트")
        self.tree.heading("path", text="로컬 폴더")
        self.tree.heading("branch", text="Branch")
        self.tree.heading("local", text="내 버전")
        self.tree.heading("remote", text="Cloud 버전")
        self.tree.heading("state", text="상태")
        self.tree.column("name", width=170)
        self.tree.column("path", width=380)
        self.tree.column("branch", width=110, anchor="center")
        self.tree.column("local", width=110, anchor="center")
        self.tree.column("remote", width=110, anchor="center")
        self.tree.column("state", width=190, anchor="center")

        scroll = ttk.Scrollbar(root, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True, pady=(4, 0))
        scroll.pack(side="left", fill="y", pady=(4, 0))

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", side="bottom")
        self.status = tk.StringVar(value="준비")
        ttk.Label(bottom, textvariable=self.status, relief="sunken", anchor="w", padding=(8, 4)).pack(fill="x")

    def set_status(self, text):
        self.status.set(text)
        self.update_idletasks()

    def set_busy(self, value: bool):
        self.busy = value

    def run_bg(self, work, done=None):
        if self.busy:
            messagebox.showinfo(APP_NAME, "다른 작업이 진행 중입니다.")
            return
        self.set_busy(True)

        def job():
            try:
                result = work()
                self.after(0, lambda: self._bg_done(result, done))
            except Exception as e:
                self.after(0, lambda: self._bg_error(e))

        threading.Thread(target=job, daemon=True).start()

    def _bg_done(self, result, done):
        self.set_busy(False)
        if done:
            done(result)

    def _bg_error(self, err):
        self.set_busy(False)
        self.set_status("오류")
        messagebox.showerror(APP_NAME, str(err))

    def load_projects(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                self.projects = [Project(**x) for x in data]
            except Exception:
                self.projects = []

    def auto_register_self_repo(self):
        """
        PDC_Version_Manager.py가 Git 저장소 루트 안에 놓여 있으면
        해당 저장소를 최초 1회 자동 등록합니다.
        """
        try:
            here = Path(__file__).resolve().parent
            if not is_git_repo(here):
                return

            repo_root = Path(run_git(here, "rev-parse", "--show-toplevel")).resolve()
            normalized = {str(Path(p.path).resolve()).lower() for p in self.projects}
            if str(repo_root).lower() in normalized:
                return

            self.projects.insert(0, Project(name=repo_root.name, path=str(repo_root)))
            self.save_projects()
        except Exception:
            # 자동 등록 실패가 프로그램 실행을 막지는 않음
            pass

    def save_projects(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps([asdict(p) for p in self.projects], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def selected_project(self) -> Project | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(APP_NAME, "프로젝트를 선택해 주세요.")
            return None
        idx = int(sel[0])
        return self.projects[idx]

    def add_local(self):
        folder = filedialog.askdirectory(title="Git 프로젝트 폴더 선택")
        if not folder:
            return
        path = Path(folder)
        if not is_git_repo(path):
            if not messagebox.askyesno(
                APP_NAME,
                "선택한 폴더는 아직 Git 저장소가 아닙니다.\n이 폴더를 Git 저장소로 초기화할까요?",
            ):
                return
            try:
                run_git(path, "init")
            except Exception as e:
                messagebox.showerror(APP_NAME, str(e))
                return

        default_name = path.name
        name = simpledialog.askstring("프로젝트 이름", "표시할 프로젝트 이름:", initialvalue=default_name)
        if not name:
            return
        self.projects.append(Project(name=name.strip(), path=str(path)))
        self.save_projects()
        self.refresh_all()

    def clone_repo(self):
        url = simpledialog.askstring("원격 저장소 Clone", "Git 저장소 URL을 입력하세요:")
        if not url:
            return
        parent = filedialog.askdirectory(title="Clone할 상위 폴더 선택")
        if not parent:
            return

        guess = url.rstrip("/").split("/")[-1]
        if guess.endswith(".git"):
            guess = guess[:-4]
        name = simpledialog.askstring("프로젝트 이름", "표시할 프로젝트 이름:", initialvalue=guess)
        if not name:
            return

        dest = Path(parent) / guess
        if dest.exists():
            messagebox.showerror(APP_NAME, f"이미 폴더가 존재합니다:\n{dest}")
            return

        self.set_status("Clone 중...")

        def work():
            run_git(None, "clone", url, str(dest), timeout=300)
            return Project(name=name.strip(), path=str(dest))

        def done(project):
            self.projects.append(project)
            self.save_projects()
            self.set_status("Clone 완료")
            self.refresh_all()

        self.run_bg(work, done)

    def configure_remote(self):
        p = self.selected_project()
        if not p:
            return
        repo = Path(p.path)
        if not is_git_repo(repo):
            messagebox.showerror(APP_NAME, "Git 저장소가 아닙니다.")
            return

        current = origin_url(repo)
        url = simpledialog.askstring(
            "원격 연결 설정",
            "origin 저장소 URL을 입력하세요:",
            initialvalue=current,
        )
        if not url:
            return

        try:
            if current:
                run_git(repo, "remote", "set-url", "origin", url.strip())
            else:
                run_git(repo, "remote", "add", "origin", url.strip())
            messagebox.showinfo(APP_NAME, "원격 저장소 연결이 설정되었습니다.")
            self.refresh_all()
        except Exception as e:
            messagebox.showerror(APP_NAME, str(e))

    def configure_identity(self):
        try:
            try:
                current_name = run_git(None, "config", "--global", "user.name")
            except Exception:
                current_name = ""
            try:
                current_email = run_git(None, "config", "--global", "user.email")
            except Exception:
                current_email = ""

            name = simpledialog.askstring(
                "Git 사용자 설정",
                "Git 사용자 이름:",
                initialvalue=current_name,
            )
            if not name:
                return
            email = simpledialog.askstring(
                "Git 사용자 설정",
                "Git 이메일:",
                initialvalue=current_email,
            )
            if not email:
                return

            run_git(None, "config", "--global", "user.name", name.strip())
            run_git(None, "config", "--global", "user.email", email.strip())
            messagebox.showinfo(APP_NAME, "Git 사용자 이름/이메일을 저장했습니다.")
        except Exception as e:
            messagebox.showerror(APP_NAME, str(e))

    def remove_project(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        p = self.projects[idx]
        if messagebox.askyesno(APP_NAME, f"목록에서 '{p.name}'을 제거할까요?\n실제 파일은 삭제되지 않습니다."):
            self.projects.pop(idx)
            self.save_projects()
            self.refresh_all()

    def refresh_all(self):
        if self.busy:
            return
        self.set_status("상태 확인 중...")

        def work():
            rows = []
            for p in self.projects:
                repo = Path(p.path)
                if not repo.exists():
                    rows.append((p.name, p.path, "-", "-", "-", "폴더 없음"))
                    continue
                if not is_git_repo(repo):
                    rows.append((p.name, p.path, "-", "-", "-", "Git 저장소 아님"))
                    continue
                try:
                    branch = current_branch(repo)
                    ltag = latest_version_tag(local_tags(repo))
                    rtag = latest_version_tag(remote_tags(repo)) if origin_url(repo) else "-"
                    dirty = local_changes(repo)
                    div = tracking_divergence(repo)

                    if not origin_url(repo):
                        state = "원격 저장소 미설정"
                    elif dirty:
                        state = "● 로컬 변경 있음"
                    elif div is None:
                        state = "업스트림 미설정"
                    else:
                        ahead, behind = div
                        if ahead == 0 and behind == 0:
                            state = "✓ 최신"
                        elif ahead > 0 and behind == 0:
                            state = f"↑ 업로드 필요 ({ahead})"
                        elif ahead == 0 and behind > 0:
                            state = f"↓ 새 버전 있음 ({behind})"
                        else:
                            state = f"⚠ 분기됨 ↑{ahead} ↓{behind}"

                    rows.append((p.name, p.path, branch, ltag, rtag, state))
                except Exception as e:
                    rows.append((p.name, p.path, "-", "-", "-", f"오류: {str(e)[:35]}"))
            return rows

        def done(rows):
            for item in self.tree.get_children():
                self.tree.delete(item)
            for i, row in enumerate(rows):
                self.tree.insert("", "end", iid=str(i), values=row)
            self.set_status("준비")

        self.run_bg(work, done)

    def pull_selected(self):
        p = self.selected_project()
        if not p:
            return
        repo = Path(p.path)

        if local_changes(repo):
            messagebox.showwarning(
                APP_NAME,
                "로컬에 아직 업로드하지 않은 변경사항이 있습니다.\n먼저 '새 버전 업로드 (Commit + Push)'를 하거나 변경사항을 정리해 주세요.",
            )
            return
        if not origin_url(repo):
            messagebox.showwarning(APP_NAME, "origin 원격 저장소가 설정되어 있지 않습니다.")
            return

        self.set_status(f"{p.name}: 최신 버전 받는 중...")

        def work():
            run_git(repo, "fetch", "origin", "--tags", timeout=180)
            # 분기된 상태에서는 자동 merge하지 않음
            div = tracking_divergence(repo)
            if div is not None and div[0] > 0 and div[1] > 0:
                raise GitError("로컬과 원격이 서로 다른 변경을 가지고 있습니다.\n자동 병합하지 않았습니다.")
            return run_git(repo, "pull", "--ff-only", timeout=180)

        manager_path = Path(__file__).resolve()
        before_manager_hash = file_sha256(manager_path)

        def done(result):
            self.set_status(f"{p.name}: 최신 버전 받기 완료")
            after_manager_hash = file_sha256(manager_path)
            manager_updated = bool(
                before_manager_hash
                and after_manager_hash
                and before_manager_hash != after_manager_hash
                and manager_path.parent.resolve() == repo.resolve()
            )

            self.refresh_all()

            if manager_updated:
                restart = messagebox.askyesno(
                    APP_NAME,
                    "최신 버전을 받았습니다.\n\n"
                    "PDC Version Manager 자체도 새 버전으로 갱신되었습니다.\n"
                    "지금 프로그램을 재실행할까요?",
                )
                if restart:
                    self.restart_manager()
                return

            messagebox.showinfo(APP_NAME, result or "최신 버전을 받았습니다.")

        self.run_bg(work, done)

    def upload_selected(self):
        p = self.selected_project()
        if not p:
            return
        repo = Path(p.path)

        if not is_git_repo(repo):
            messagebox.showerror(APP_NAME, "Git 저장소가 아닙니다.")
            return
        if not origin_url(repo):
            messagebox.showwarning(
                APP_NAME,
                "origin 원격 저장소가 없습니다.\n\n"
                "'원격 연결 설정' 버튼에서 GitHub/GitLab 저장소 URL을 등록해 주세요.",
            )
            return
        if not local_changes(repo):
            messagebox.showinfo(APP_NAME, "현재 변경된 파일이 없습니다.")
            return
        if not git_identity_ok(repo):
            messagebox.showwarning(
                APP_NAME,
                "Git 사용자 이름/이메일이 설정되지 않았습니다.\n\n"
                "'Git 사용자 설정' 버튼에서 한 번만 등록해 주세요.",
            )
            return

        self.set_status(f"{p.name}: 원격 상태 확인 중...")

        def prepare():
            run_git(repo, "fetch", "origin", "--tags", timeout=180)
            div = tracking_divergence(repo)
            if div is not None and div[1] > 0:
                raise GitError("원격 저장소에 더 최신 변경이 있습니다.\n먼저 '최신 버전 받기 (Pull)'를 실행해 주세요.")
            return next_version_tag(repo)

        def prepared(tag):
            self.set_status("준비")
            dlg = UploadDialog(self, p.name, tag)
            self.wait_window(dlg)
            if not dlg.result:
                return
            tag, msg = dlg.result
            self._do_upload(p, repo, tag, msg)

        self.run_bg(prepare, prepared)

    def _do_upload(self, p: Project, repo: Path, tag: str, msg: str):
        self.set_status(f"{p.name}: {tag} 업로드 중...")

        def work():
            branch = current_branch(repo)
            if branch == "(detached)":
                raise GitError("detached HEAD 상태에서는 업로드할 수 없습니다.")

            run_git(repo, "add", "-A")
            commit_message = f"[{tag}] {msg}"
            run_git(repo, "commit", "-m", commit_message, timeout=180)
            run_git(repo, "tag", "-a", tag, "-m", msg)

            # 브랜치 push. upstream이 없으면 -u 자동 설정.
            div = tracking_divergence(repo)
            if div is None:
                run_git(repo, "push", "-u", "origin", branch, timeout=300)
            else:
                run_git(repo, "push", "origin", branch, timeout=300)

            run_git(repo, "push", "origin", tag, timeout=180)
            return tag

        def done(tag_done):
            self.set_status(f"{p.name}: {tag_done} 업로드 완료")
            messagebox.showinfo(
                APP_NAME,
                f"업로드 완료\n\n버전: {tag_done}\n\n다른 PC에서는 '최신 버전 받기 (Pull)'를 누르면 됩니다.",
            )
            self.refresh_all()

        self.run_bg(work, done)

    def apply_manager_update(self):
        """
        새 PDC_Version_Manager_YYMMDD_N.zip 하나를 선택하면:
        1) 저장소/5. version_manager/ 에 ZIP 원본 보관
        2) ZIP 내부 PDC_Version_Manager.py를 저장소 루트에 적용
        3) ZIP 내부 요구사항 Excel이 있으면 5. version_manager의 최신 명세로 갱신
        4) Git 변경사항으로 남겨 이후 Commit + Push 가능하게 함

        이 기능 덕분에 다음 버전부터는 사용자가 ZIP을 직접 풀 필요가 없습니다.
        """
        p = self.selected_project()
        if not p:
            return

        repo = Path(p.path).resolve()
        if not is_git_repo(repo):
            messagebox.showerror(APP_NAME, "Git 저장소가 아닙니다.")
            return

        zip_file = filedialog.askopenfilename(
            title="PDC Version Manager 업데이트 ZIP 선택",
            filetypes=[
                ("PDC Version Manager ZIP", "PDC_Version_Manager_*.zip"),
                ("ZIP files", "*.zip"),
                ("All files", "*.*"),
            ],
        )
        if not zip_file:
            return

        source_zip = Path(zip_file).resolve()
        if not source_zip.exists():
            messagebox.showerror(APP_NAME, "선택한 ZIP 파일을 찾을 수 없습니다.")
            return

        try:
            with zipfile.ZipFile(source_zip, "r") as zf:
                names = zf.namelist()
                candidates = [
                    name for name in names
                    if Path(name).name.lower() == ROOT_MANAGER_FILENAME.lower()
                ]
                if not candidates:
                    raise GitError(
                        f"ZIP 안에 {ROOT_MANAGER_FILENAME} 파일이 없습니다.\n"
                        "PDC Version Manager 공식 Release ZIP인지 확인해 주세요."
                    )

                member = candidates[0]
                new_bytes = zf.read(member)

                req_candidates = [
                    name for name in names
                    if Path(name).name.lower() == REQUIREMENTS_FILENAME.lower()
                ]
                requirements_bytes = zf.read(req_candidates[0]) if req_candidates else None

            # 최소 문법 검증을 위해 임시 파일 작성 후 compile
            temp_path = repo / f".{ROOT_MANAGER_FILENAME}.update_tmp"
            temp_path.write_bytes(new_bytes)
            try:
                import py_compile
                py_compile.compile(str(temp_path), doraise=True)
            finally:
                try:
                    temp_path.unlink()
                except Exception:
                    pass

            release_dir = repo / "5. version_manager"
            release_dir.mkdir(parents=True, exist_ok=True)

            target_zip = release_dir / source_zip.name
            if source_zip != target_zip.resolve():
                shutil.copy2(source_zip, target_zip)

            root_manager = repo / ROOT_MANAGER_FILENAME
            temp_new = repo / f".{ROOT_MANAGER_FILENAME}.new"
            temp_new.write_bytes(new_bytes)
            os.replace(temp_new, root_manager)

            requirements_target = release_dir / REQUIREMENTS_FILENAME
            if requirements_bytes is not None:
                temp_req = release_dir / f".{REQUIREMENTS_FILENAME}.new"
                temp_req.write_bytes(requirements_bytes)
                os.replace(temp_req, requirements_target)

            self.refresh_all()

            restart = messagebox.askyesno(
                APP_NAME,
                "Version Manager 업데이트 파일을 적용했습니다.\n\n"
                f"보관 ZIP:\n{target_zip}\n\n"
                f"최신 실행본:\n{root_manager}\n\n"
                + (f"최신 요구사항 명세:\n{requirements_target}\n\n" if requirements_bytes is not None else "")
                + "이 변경사항은 아직 로컬에만 있습니다.\n"
                "'새 버전 업로드 (Commit + Push)'로 GitHub에 올리면 다른 PC도 받을 수 있습니다.\n\n"
                "지금 새 Version Manager로 재실행할까요?",
            )
            if restart:
                self.restart_manager()

        except Exception as e:
            messagebox.showerror(APP_NAME, f"Version Manager 업데이트 적용 실패\n\n{e}")

    def restart_manager(self):
        """현재 Python 인터프리터로 최신 PDC_Version_Manager.py를 재실행합니다."""
        try:
            manager_path = Path(__file__).resolve()
            self.destroy()
            os.execl(sys.executable, sys.executable, str(manager_path))
        except Exception as e:
            messagebox.showerror(
                APP_NAME,
                "자동 재실행에 실패했습니다.\\n"
                "프로그램을 종료한 뒤 PDC_Version_Manager.py를 다시 실행해 주세요.\\n\\n"
                + str(e),
            )

    def history_selected(self):
        p = self.selected_project()
        if not p:
            return
        repo = Path(p.path)
        if not is_git_repo(repo):
            return
        HistoryWindow(self, repo, p.name)

    def open_folder(self):
        p = self.selected_project()
        if not p:
            return
        path = Path(p.path)
        if not path.exists():
            return
        if os.name == "nt":
            os.startfile(str(path))
        elif os.uname().sysname == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])


if __name__ == "__main__":
    App().mainloop()
