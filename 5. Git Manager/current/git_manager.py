from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from catalog import load_catalog, target_map
from release_rules import latest_release, parse_release_name

APP_NAME = "Git Manager"
APP_VERSION = "260819_2"
VERSION_RE = re.compile(r"^(?P<date>\d{6})_(?P<num>\d+)$")
CONFIG_DIR = Path.home() / ".pdc_git_manager"
CONFIG_FILE = CONFIG_DIR / "projects.json"


@dataclass
class Project:
    name: str
    path: str


class GitError(RuntimeError):
    pass


def run_git(repo: Path | None, *args: str, timeout: int = 120) -> str:
    cmd = ["git"]
    if repo is not None:
        cmd += ["-C", str(repo)]
    cmd += list(args)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=flags,
        )
    except FileNotFoundError as exc:
        raise GitError("Git을 찾을 수 없습니다. Git for Windows 설치/허용 상태를 확인해주세요.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError("Git 명령 실행 시간이 초과되었습니다.") from exc
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "Git 명령 실패").strip()
        raise GitError(msg)
    return (proc.stdout or "").strip()


def is_git_repo(path: Path) -> bool:
    try:
        return run_git(path, "rev-parse", "--is-inside-work-tree") == "true"
    except Exception:
        return False


def current_branch(repo: Path) -> str:
    return run_git(repo, "branch", "--show-current") or "(detached)"


def origin_url(repo: Path) -> str:
    try:
        return run_git(repo, "remote", "get-url", "origin")
    except Exception:
        return ""


def run_git_bytes(repo: Path | None, *args: str, timeout: int = 120) -> bytes:
    cmd = ["git"]
    if repo is not None:
        cmd += ["-C", str(repo)]
    cmd += list(args)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            creationflags=flags,
        )
    except FileNotFoundError as exc:
        raise GitError("Git을 찾을 수 없습니다. Git for Windows 설치/허용 상태를 확인해주세요.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError("Git 명령 실행 시간이 초과되었습니다.") from exc
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or b"Git command failed").decode("utf-8", errors="replace").strip()
        raise GitError(msg)
    return proc.stdout or b""


def git_toplevel(path: Path) -> Path | None:
    try:
        text = run_git(path, "rev-parse", "--show-toplevel")
        return Path(text).resolve() if text else None
    except Exception:
        return None


_APP_RELEASE_RE = re.compile(r"APP_RELEASE\s*=\s*[\"'](?P<release>\d{6}_\d+)[\"']")


def _app_release_from_text(text: str) -> str | None:
    match = _APP_RELEASE_RE.search(text or "")
    return match.group("release") if match else None


def _local_automation_release(repo: Path) -> str | None:
    launcher = repo / "Automation_Manager.pyw"
    try:
        return _app_release_from_text(launcher.read_text(encoding="utf-8"))
    except Exception:
        return None


def _remote_automation_release(repo: Path, ref: str) -> str | None:
    try:
        return _app_release_from_text(run_git(repo, "show", f"{ref}:Automation_Manager.pyw"))
    except Exception:
        return None


def _release_cmp(left: str | None, right: str | None) -> int | None:
    if not left or not right:
        return None
    l = parse_release_name(left)
    r = parse_release_name(right)
    if not l or not r:
        return None
    lk = (l.date, l.counter)
    rk = (r.date, r.counter)
    return (lk > rk) - (lk < rk)


def _release_relation_text(local_release: str | None, remote_release: str | None) -> str:
    cmp = _release_cmp(local_release, remote_release)
    local_text = local_release or "확인 불가"
    remote_text = remote_release or "확인 불가"
    if cmp is None:
        relation = "자동 비교 불가"
    elif cmp > 0:
        relation = "현재 압축본/로컬이 더 최신"
    elif cmp < 0:
        relation = "원격 Git이 더 최신"
    else:
        relation = "동일 Release"
    return f"Local {local_text} / Git {remote_text} / {relation}"


def _guard_not_older_than_remote(repo: Path, branch: str) -> None:
    remote_ref = f"origin/{branch}"
    local_release = _local_automation_release(repo)
    remote_release = _remote_automation_release(repo, remote_ref)
    cmp = _release_cmp(local_release, remote_release)
    if cmp is not None and cmp < 0:
        raise GitError(
            "현재 Automation Manager Release가 원격 Git보다 오래되어 Push를 차단합니다.\n\n"
            f"현재 폴더: {local_release}\n"
            f"원격 Git: {remote_release}\n\n"
            "과거 압축본으로 최신 원격 파일을 덮어쓰는 것을 방지하기 위한 안전장치입니다. "
            "더 최신 Automation Manager 패키지를 사용하거나 원격 최신본을 기준으로 복구해주세요."
        )


def _safe_relative_parts(path_text: str) -> tuple[str, ...]:
    normalized = str(path_text).replace("\\", "/").strip("/")
    parts = tuple(p for p in normalized.split("/") if p and p not in {"."})
    if not parts or any(p == ".." for p in parts):
        raise GitError(f"안전하지 않은 Git 경로를 감지했습니다: {path_text}")
    return parts


def _restore_remote_blob_if_missing(repo: Path, ref: str, git_path: str, destination: Path) -> bool:
    if destination.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    blob = run_git_bytes(repo, "show", f"{ref}:{git_path}", timeout=180)
    destination.write_bytes(blob)
    return True


def _hydrate_remote_managed_files(
    repo: Path,
    ref: str,
    catalog: dict,
    log=None,
    created_files: list[Path] | None = None,
    created_dirs: list[Path] | None = None,
) -> list[str]:
    """
    Preserve remote-only managed data while keeping the extracted package files authoritative.

    Targets 1~4 are restored recursively because they are user data/inboxes.
    Targets 5~6 restore only direct files so old current/ runtime code is not resurrected.
    Existing local files are never overwritten.
    """
    recovery = (catalog.get("git_repository") or {}).get("recovery") or {}
    modes = recovery.get("target_preserve_mode") or {}
    restored: list[str] = []
    created_files = created_files if created_files is not None else []
    created_dirs = created_dirs if created_dirs is not None else []

    def remember_missing_dirs(destination: Path) -> list[Path]:
        pending = []
        parent = destination.parent
        while parent != repo and not parent.exists():
            pending.append(parent)
            parent = parent.parent
        return pending

    for target in catalog.get("targets") or []:
        key = str(target["key"])
        mode = str(modes.get(key, "recursive"))
        local_folder, local_issue = _resolve_local_target_folder(repo, target)
        remote_folder, remote_issue = _resolve_remote_folder_name(repo, ref, target)
        if local_issue:
            raise GitError(f"Git 복구 중 로컬 대상 폴더 별칭 충돌: {local_issue}")
        if remote_issue:
            raise GitError(f"Git 복구 중 원격 대상 폴더 별칭 충돌: {remote_issue}")

        raw = run_git_bytes(repo, "ls-tree", "-r", "-z", "--name-only", ref, "--", remote_folder)
        prefix = remote_folder.replace("\\", "/").strip("/") + "/"
        for entry in raw.split(b"\0"):
            if not entry:
                continue
            git_path = entry.decode("utf-8", errors="replace").replace("\\", "/")
            if not git_path.startswith(prefix):
                continue
            inner = git_path[len(prefix):]
            parts = _safe_relative_parts(inner)
            if mode == "root_only" and len(parts) != 1:
                continue
            destination = local_folder.joinpath(*parts)
            pending_dirs = remember_missing_dirs(destination)
            if _restore_remote_blob_if_missing(repo, ref, git_path, destination):
                created_files.append(destination)
                created_dirs.extend(pending_dirs)
                rel = str(destination.relative_to(repo)).replace("\\", "/")
                restored.append(rel)
                if log:
                    log(f"원격 보존 파일 복원: {rel}")

    for root_name in recovery.get("preserve_root_files") or []:
        root_name = str(root_name).strip()
        if not root_name:
            continue
        parts = _safe_relative_parts(root_name)
        if len(parts) != 1:
            continue
        destination = repo / parts[0]
        try:
            pending_dirs = remember_missing_dirs(destination)
            if _restore_remote_blob_if_missing(repo, ref, parts[0], destination):
                created_files.append(destination)
                created_dirs.extend(pending_dirs)
                restored.append(parts[0])
                if log:
                    log(f"원격 Root 보존 파일 복원: {parts[0]}")
        except GitError:
            pass

    return restored


def adopt_existing_remote_history(repo: Path, url: str, branch: str, catalog: dict) -> dict:
    """Attach an extracted Automation Manager folder to existing remote Git history.

    Safety properties:
    - never overwrites an existing local file;
    - never commits or pushes;
    - restores remote-only managed data according to catalog recovery policy;
    - removes only the .git directory created by this function when setup fails.
    """
    repo = Path(repo).resolve()
    existing_root = git_toplevel(repo)
    if existing_root == repo:
        raise GitError("현재 폴더는 이미 Git Repository입니다.")
    if existing_root is not None:
        raise GitError(
            "현재 폴더가 상위 Git Repository 안에 있어 중첩 Git 복구를 수행하지 않습니다: "
            f"{existing_root}"
        )
    if (repo / ".git").exists():
        raise GitError(".git 항목이 이미 존재하지만 정상 Repository로 확인되지 않습니다.")

    created_git = False
    created_files: list[Path] = []
    created_dirs: list[Path] = []
    try:
        local_release = _local_automation_release(repo)
        run_git(repo, "init")
        created_git = True
        run_git(repo, "remote", "add", "origin", url)
        run_git(repo, "fetch", "origin", "--tags", timeout=300)
        remote_ref = f"origin/{branch}"
        run_git(repo, "rev-parse", "--verify", remote_ref)
        remote_release = _remote_automation_release(repo, remote_ref)

        # Mixed reset connects HEAD/index to remote history but does not touch working files.
        run_git(repo, "reset", "--mixed", remote_ref, timeout=180)
        run_git(repo, "branch", "-M", branch)
        run_git(repo, "branch", "--set-upstream-to", remote_ref, branch)

        restored = _hydrate_remote_managed_files(
            repo, remote_ref, catalog, log=None,
            created_files=created_files, created_dirs=created_dirs,
        )
        status_text = run_git(repo, "status", "--short")
        changed_count = len([line for line in status_text.splitlines() if line.strip()])
        return {
            "local_release": local_release,
            "remote_release": remote_release,
            "restored": restored,
            "changed_count": changed_count,
            "branch": branch,
            "url": url,
        }
    except Exception:
        for created in reversed(created_files):
            try:
                if created.is_file():
                    created.unlink()
            except Exception:
                pass
        for created_dir in sorted(set(created_dirs), key=lambda x: len(x.parts), reverse=True):
            try:
                created_dir.rmdir()
            except Exception:
                pass
        if created_git and (repo / ".git").exists():
            shutil.rmtree(repo / ".git", ignore_errors=True)
        raise


def local_changes(repo: Path) -> bool:
    return bool(run_git(repo, "status", "--porcelain"))


def git_identity_ok(repo: Path) -> bool:
    try:
        return bool(run_git(repo, "config", "user.name") and run_git(repo, "config", "user.email"))
    except Exception:
        try:
            return bool(run_git(None, "config", "--global", "user.name") and run_git(None, "config", "--global", "user.email"))
        except Exception:
            return False


def tracking_divergence(repo: Path) -> tuple[int, int] | None:
    try:
        out = run_git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
        left, right = out.split()
        return int(left), int(right)
    except Exception:
        return None


def local_tags(repo: Path) -> list[str]:
    try:
        return [x for x in run_git(repo, "tag", "--list").splitlines() if x.strip()]
    except Exception:
        return []


def remote_tags(repo: Path) -> list[str]:
    if not origin_url(repo):
        return []
    try:
        out = run_git(repo, "ls-remote", "--tags", "--refs", "origin")
    except Exception:
        return []
    result = []
    for line in out.splitlines():
        if "refs/tags/" in line:
            result.append(line.split("refs/tags/", 1)[1].strip())
    return result


def next_version_tag(repo: Path) -> str:
    today = datetime.now().strftime("%y%m%d")
    nums = []
    for tag in set(local_tags(repo) + remote_tags(repo)):
        m = VERSION_RE.match(tag)
        if m and m.group("date") == today:
            nums.append(int(m.group("num")))
    return f"{today}_{max(nums, default=0) + 1}"


def _tree_sha(repo: Path, ref: str, folder: str) -> str | None:
    try:
        return run_git(repo, "rev-parse", f"{ref}:{folder}")
    except Exception:
        return None


def _tree_names(repo: Path, ref: str, folder: str) -> list[str]:
    try:
        out = run_git(repo, "ls-tree", "--name-only", f"{ref}:{folder}")
        return [x.strip() for x in out.splitlines() if x.strip()]
    except Exception:
        return []


def _working_changed(repo: Path, folder: str) -> bool:
    try:
        return bool(run_git(repo, "status", "--porcelain", "--", folder))
    except Exception:
        return False


def _working_changed_aliases(repo: Path, *folders: str) -> bool:
    """Return True when any canonical/legacy alias path has working-tree changes."""
    unique = []
    seen = set()
    for folder in folders:
        text = str(folder or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(text)
    if not unique:
        return False
    try:
        return bool(run_git(repo, "status", "--porcelain", "--", *unique))
    except Exception:
        return False


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        return "-"
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return "!"


def _runtime_fingerprint(workspace_root: Path) -> tuple[tuple[str, str], ...]:
    """Fingerprint the integrated runtime that requires restart after Git Pull."""
    roots = [
        workspace_root / "Automation_Manager.pyw",
        workspace_root / "program_catalog.json",
    ]
    files = list(roots)
    for rel in [
        Path("function/common"),
        Path("5. Git Manager/current"),
        Path("6. BoardRepo/current/function"),
    ]:
        base = workspace_root / rel
        if base.is_dir():
            files.extend(sorted(x for x in base.rglob("*") if x.is_file() and "__pycache__" not in x.parts))
    br_current = workspace_root / "6. BoardRepo/current"
    for name in ["BoardRepo.pyw", "config.json", "site_profile.json", "requirements.txt"]:
        files.append(br_current / name)
    unique = {}
    for path in files:
        if path.is_file():
            unique[str(path.relative_to(workspace_root)).replace("\\", "/")] = _file_sha256(path)
    return tuple(sorted(unique.items()))


def _local_names(folder: Path) -> list[str]:
    if not folder.exists():
        return []
    return [p.name for p in folder.iterdir() if p.is_file()]


def _resolve_local_target_folder(repo: Path, target: dict) -> tuple[Path, str | None]:
    aliases = target.get("aliases") or [target["folder"]]
    matches = []
    seen = set()
    for alias in aliases:
        candidate = repo / str(alias)
        key = str(candidate).casefold()
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_dir():
            matches.append(candidate)
    if len(matches) > 1:
        names = ", ".join(p.name for p in matches)
        return repo / target["folder"], f"폴더 별칭 중복: {names}"
    if matches:
        return matches[0], None
    return repo / target["folder"], None


def _root_tree_names(repo: Path, ref: str | None) -> list[str]:
    if not ref:
        return []
    try:
        out = run_git(repo, "ls-tree", "--name-only", ref)
        return [x.strip() for x in out.splitlines() if x.strip()]
    except Exception:
        return []


def _resolve_git_tree_folder_name(
    repo: Path, ref: str | None, target: dict, *, label: str = "Git"
) -> tuple[str, str | None]:
    """Resolve a target folder as it is actually recorded in a Git tree.

    Git tree paths are case-sensitive even on Windows while the working filesystem may
    treat `6. BoardRepo` and legacy `6. boardrepo` as the same directory.  Resolve the
    real tree entry case-insensitively against all catalog aliases so status comparison
    never reports a false 'remote only' solely because of legacy casing.
    """
    canonical = str(target["folder"])
    if not ref:
        return canonical, None

    aliases = [str(x) for x in (target.get("aliases") or [canonical])]
    alias_keys = {x.casefold() for x in aliases}
    root_names = _root_tree_names(repo, ref)
    matches = [name for name in root_names if name.casefold() in alias_keys]

    # A Git tree cannot normally contain two case-only variants on Windows, but it can
    # on case-sensitive systems. Treat that as a real ambiguity rather than guessing.
    unique = list(dict.fromkeys(matches))
    if len(unique) > 1:
        return canonical, f"{label} 폴더 별칭 중복: {', '.join(unique)}"
    if unique:
        return unique[0], None

    # Backward-compatible fallback for unusual trees where root enumeration is blocked.
    exact = []
    for alias in aliases:
        if _tree_sha(repo, ref, alias):
            exact.append(alias)
    exact = list(dict.fromkeys(exact))
    if len(exact) > 1:
        return canonical, f"{label} 폴더 별칭 중복: {', '.join(exact)}"
    return (exact[0] if exact else canonical), None


def _resolve_remote_folder_name(repo: Path, ref: str | None, target: dict) -> tuple[str, str | None]:
    return _resolve_git_tree_folder_name(repo, ref, target, label="원격")


def _release_summary(names: list[str], target: dict) -> str:
    mode = target.get("mode")
    if mode == "versioned_archive":
        rel = latest_release(names, target.get("package_prefixes") or [])
        return rel.label if rel else "-"
    if mode == "file_hash":
        return f"files:{len(names)}"
    if mode == "archive_family":
        count = sum(1 for n in names if Path(n).suffix.casefold() in {".zip", ".7z", ".rar"})
        return f"archives:{count}"
    return "-"


class GitManagerFrame(ttk.Frame):
    def __init__(self, master, workspace_root: Path, target_vars: dict[str, tk.BooleanVar], operation_lock=None):
        super().__init__(master, padding=12)
        self.workspace_root = Path(workspace_root).resolve()
        self.catalog = load_catalog(self.workspace_root / "program_catalog.json")
        self.targets = target_map(self.catalog)
        self.target_vars = target_vars
        self.operation_lock = operation_lock
        self.busy = False
        self.projects: list[Project] = []
        self.repo_var = tk.StringVar()
        self.status_var = tk.StringVar(value="대기")
        self.repo_info_var = tk.StringVar(value="Repository를 선택해주세요.")
        self.recovery_info_var = tk.StringVar(value="현재 Automation Manager Root의 Git 상태를 확인합니다.")
        self._build_ui()
        self._load_projects()
        self._auto_register_workspace()
        self._update_recovery_ui()
        self.after(250, self.refresh_status)

    def _build_ui(self):
        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text="Git Manager", font=("Segoe UI", 18, "bold")).pack(side="left")
        ttk.Label(header, text="Git 기반 Repository 동기화 · 1~6 대상 상태 확인", font=("Segoe UI", 10)).pack(side="left", padx=(12, 0), pady=(6, 0))

        repo_line = ttk.Frame(self)
        repo_line.pack(fill="x", pady=(10, 6))
        ttk.Label(repo_line, text="Repository").pack(side="left")
        self.repo_combo = ttk.Combobox(repo_line, textvariable=self.repo_var, state="readonly", width=42)
        self.repo_combo.pack(side="left", padx=(8, 6))
        self.repo_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_status())
        ttk.Button(repo_line, text="로컬 등록", command=self.add_local).pack(side="left")
        ttk.Button(repo_line, text="Clone", command=self.clone_repo).pack(side="left", padx=4)
        ttk.Button(repo_line, text="현재 폴더 Git 연결/복구", command=self.adopt_workspace_git).pack(side="left", padx=(0, 4))
        ttk.Button(repo_line, text="원격 설정", command=self.configure_remote).pack(side="left")
        ttk.Button(repo_line, text="Git 사용자 설정", command=self.configure_identity).pack(side="left", padx=4)
        ttk.Button(repo_line, text="폴더 열기", command=self.open_folder).pack(side="left")

        ttk.Label(self, textvariable=self.repo_info_var).pack(anchor="w", pady=(0, 6))

        recovery = ttk.LabelFrame(self, text="현재 Automation Manager Root Git 복구", padding=8)
        recovery.pack(fill="x", pady=(0, 8))
        ttk.Label(recovery, textvariable=self.recovery_info_var).pack(side="left", fill="x", expand=True)
        self.recovery_button = ttk.Button(recovery, text="현재 폴더 Git 연결/복구", command=self.adopt_workspace_git)
        self.recovery_button.pack(side="right", padx=(8, 0))

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(0, 8))
        ttk.Button(actions, text="선택 항목 상태 확인", command=self.refresh_status).pack(side="left")
        ttk.Button(actions, text="최신 버전 받기 (Pull)", command=self.pull_repo).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="새 버전 업로드 (Commit + Push)", command=self.push_repo).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="이력 보기", command=self.show_history).pack(side="left", padx=(8, 0))
        ttk.Label(actions, text="※ Git Pull/Push는 선택 항목만이 아니라 Repository 전체에 적용됩니다.").pack(side="left", padx=(16, 0))

        cols = ("target", "local", "remote", "state", "tree")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=8)
        self.tree.heading("target", text="대상")
        self.tree.heading("local", text="Local 요약")
        self.tree.heading("remote", text="Git(origin) 요약")
        self.tree.heading("state", text="상태")
        self.tree.heading("tree", text="Tree 비교")
        self.tree.column("target", width=180)
        self.tree.column("local", width=130, anchor="center")
        self.tree.column("remote", width=130, anchor="center")
        self.tree.column("state", width=180, anchor="center")
        self.tree.column("tree", width=250)
        self.tree.pack(fill="x", pady=(4, 8))

        log_frame = ttk.LabelFrame(self, text="Git Manager 로그", padding=6)
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_frame, height=15, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True)
        ttk.Label(self, textvariable=self.status_var).pack(anchor="w", pady=(5, 0))

    def log(self, text: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{stamp}] {text}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _load_projects(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8")) if CONFIG_FILE.exists() else []
            self.projects = [Project(**x) for x in data]
        except Exception:
            self.projects = []
        self._sync_combo()

    def _save_projects(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps([asdict(p) for p in self.projects], ensure_ascii=False, indent=2), encoding="utf-8")
        self._sync_combo()

    def _sync_combo(self):
        values = [f"{p.name} | {p.path}" for p in self.projects]
        self.repo_combo["values"] = values
        if values and self.repo_var.get() not in values:
            self.repo_var.set(values[0])

    def _auto_register_workspace(self):
        root = git_toplevel(self.workspace_root)
        if root is None or root != self.workspace_root:
            return
        if any(Path(p.path).resolve() == root for p in self.projects):
            self.repo_var.set(next(
                (f"{p.name} | {p.path}" for p in self.projects if Path(p.path).resolve() == root),
                self.repo_var.get(),
            ))
            return
        self.projects.insert(0, Project(root.name, str(root)))
        self._save_projects()
        self.repo_var.set(f"{root.name} | {root}")

    def _update_recovery_ui(self):
        root = git_toplevel(self.workspace_root)
        if root == self.workspace_root:
            self.recovery_info_var.set(
                f"현재 폴더 자체가 Git Repository입니다: {self.workspace_root}"
            )
            try:
                self.recovery_button.configure(state="disabled")
            except Exception:
                pass
            return
        if root is not None:
            self.recovery_info_var.set(
                "현재 Automation Manager 폴더가 다른 상위 Git Repository 안에 있습니다. "
                f"중첩 Git 복구는 자동 수행하지 않습니다: {root}"
            )
            try:
                self.recovery_button.configure(state="disabled")
            except Exception:
                pass
            return
        self.recovery_info_var.set(
            "현재 Automation Manager Root에 .git이 없습니다. "
            "ZIP/BoardRepo 복구본이라면 이 폴더 자체에 기존 원격 Git 이력을 안전하게 연결할 수 있습니다. 기본 origin/main은 catalog에서 자동 사용됩니다."
        )
        try:
            self.recovery_button.configure(state="normal")
        except Exception:
            pass

    def _register_project_path(self, path: Path, name: str | None = None):
        path = Path(path).resolve()
        display = (name or path.name).strip() or path.name
        self.projects = [p for p in self.projects if Path(p.path).resolve() != path]
        self.projects.insert(0, Project(display, str(path)))
        self._save_projects()
        self.repo_var.set(f"{display} | {path}")

    def adopt_workspace_git(self):
        repo = self.workspace_root
        existing_root = git_toplevel(repo)
        if existing_root == repo:
            self._register_project_path(repo)
            self._update_recovery_ui()
            self.refresh_status()
            messagebox.showinfo(APP_NAME, "현재 Automation Manager 폴더는 이미 정상 Git Repository입니다.")
            return
        if existing_root is not None:
            messagebox.showwarning(
                APP_NAME,
                "현재 Automation Manager 폴더가 상위 Git Repository 안에 있습니다.\n\n"
                f"상위 Repository: {existing_root}\n\n"
                "중첩 .git 생성을 피하기 위해 자동 복구를 중단합니다. "
                "이 Automation Manager 폴더를 상위 Repository 밖으로 이동한 뒤 다시 실행해주세요.",
            )
            return
        if (repo / ".git").exists():
            messagebox.showwarning(
                APP_NAME,
                ".git 항목이 존재하지만 정상 Git Repository로 확인되지 않습니다. "
                "기존 Git 메타데이터를 임의 삭제하지 않으므로 수동 확인이 필요합니다.",
            )
            return

        git_cfg = self.catalog.get("git_repository") or {}
        default_url = str(git_cfg.get("url") or "https://github.com/kingmugum/PDC-Repository.git")
        branch = str(git_cfg.get("default_branch") or "main")
        # Self-bootstrap recovery uses the catalog URL directly.  The user no longer
        # needs to remember/type the Clone address on every PC or after a desktop loss.
        # A different remote can still be configured explicitly through [원격 설정].
        url = default_url.strip()
        if not url:
            messagebox.showerror(APP_NAME, "program_catalog.json에 기본 Git Repository URL이 없습니다.")
            return
        if not messagebox.askyesno(
            APP_NAME,
            "현재 폴더를 기존 Git 이력에 연결하시겠습니까?\n\n"
            f"현재 폴더: {repo}\n"
            f"원격(자동): {url}\n"
            f"Branch: {branch}\n\n"
            "안전 정책\n"
            "- 현재 로컬 파일은 덮어쓰지 않습니다.\n"
            "- 원격에만 있는 1~6 보존 자료는 필요한 범위에서 복원합니다.\n"
            "- 5/6 current 런타임은 현재 압축본을 우선합니다.\n"
            "- 자동 Commit/Push는 하지 않습니다.\n"
            "- 연결 실패 시 이번 작업이 만든 .git을 제거하여 원상복구합니다.",
        ):
            return

        def work():
            return adopt_existing_remote_history(repo, url, branch, self.catalog)

        def done(result):
            self._register_project_path(repo)
            self._update_recovery_ui()
            self.refresh_status()
            relation = _release_relation_text(result["local_release"], result["remote_release"])
            restored_count = len(result["restored"])
            self.log(f"복구 대상 Root: {repo}")
            self.log(f"원격 Git: {result['url']}")
            self.log(f"기준 Branch: {result['branch']}")
            self.log(f"Release 비교: {relation}")
            self.log(f"원격 보존 파일 복원: {restored_count}개")
            for rel in result["restored"][:30]:
                self.log(f"보존 파일: {rel}")
            if restored_count > 30:
                self.log(f"보존 파일 추가 {restored_count - 30}개는 로그에서 생략")
            message = (
                "현재 Automation Manager 폴더 자체에 기존 Git 이력을 연결했습니다.\n\n"
                f"폴더: {repo}\n"
                f"origin: {result['url']}\n"
                f"branch: {result['branch']}\n"
                f"Release 비교: {relation}\n"
                f"원격 보존 파일 복원: {restored_count}개\n"
                f"현재 Git 변경 항목: {result['changed_count']}개\n\n"
                "현재 로컬 파일은 덮어쓰지 않았고 자동 Push도 수행하지 않았습니다. "
                "상태를 확인한 뒤 Commit + Push를 진행해주세요."
            )
            cmp = _release_cmp(result["local_release"], result["remote_release"])
            if cmp is not None and cmp < 0:
                message += (
                    "\n\n주의: 원격 Git Release가 현재 압축본보다 더 최신입니다. "
                    "과거 버전 덮어쓰기를 막기 위해 Commit + Push가 자동 차단됩니다."
                )
                messagebox.showwarning(APP_NAME, message)
            else:
                messagebox.showinfo(APP_NAME, message)

        self._run_locked("현재 폴더 Git 연결/복구", work, done)

    def selected_project(self) -> Project | None:
        value = self.repo_var.get()
        for p in self.projects:
            if value == f"{p.name} | {p.path}":
                return p
        return None

    def selected_repo(self) -> Path | None:
        p = self.selected_project()
        return Path(p.path).resolve() if p else None

    def selected_target_keys(self) -> list[str]:
        return [key for key, var in self.target_vars.items() if var.get()]

    def add_local(self):
        folder = filedialog.askdirectory(title="Git Repository 폴더 선택")
        if not folder:
            return
        path = Path(folder).resolve()
        if path == self.workspace_root and git_toplevel(path) is None:
            messagebox.showinfo(
                APP_NAME,
                "현재 Automation Manager Root는 일반 git init보다 '현재 폴더 Git 연결/복구'를 사용해야 "
                "기존 원격 Git 이력을 안전하게 이어갈 수 있습니다.",
            )
            self.adopt_workspace_git()
            return
        if not is_git_repo(path):
            if not messagebox.askyesno(APP_NAME, "Git 저장소가 아닙니다. 새 독립 저장소로 git init을 실행할까요?"):
                return
            try:
                run_git(path, "init")
            except Exception as exc:
                messagebox.showerror(APP_NAME, str(exc))
                return
        name = simpledialog.askstring("Repository 이름", "표시 이름:", initialvalue=path.name)
        if not name:
            return
        self.projects.append(Project(name.strip(), str(path)))
        self._save_projects()
        self.repo_var.set(f"{name.strip()} | {path}")
        self.refresh_status()

    def clone_repo(self):
        url = simpledialog.askstring("원격 저장소 Clone", "Git Repository URL:")
        if not url:
            return
        parent = filedialog.askdirectory(title="Clone할 상위 폴더")
        if not parent:
            return
        guess = url.rstrip("/").split("/")[-1].removesuffix(".git")
        dest = Path(parent) / guess
        if dest.exists():
            messagebox.showerror(APP_NAME, f"대상 폴더가 이미 존재합니다:\n{dest}")
            return
        self._run_locked("Git Clone", lambda: run_git(None, "clone", url, str(dest), timeout=300), lambda _: self._after_clone(dest))

    def _after_clone(self, dest: Path):
        self.projects.append(Project(dest.name, str(dest)))
        self._save_projects()
        self.repo_var.set(f"{dest.name} | {dest}")
        self.refresh_status()

    def configure_remote(self):
        repo = self.selected_repo()
        if not repo or not is_git_repo(repo):
            messagebox.showinfo(APP_NAME, "Git Repository를 먼저 선택해주세요.")
            return
        current = origin_url(repo)
        url = simpledialog.askstring("원격 연결 설정", "origin URL:", initialvalue=current)
        if not url:
            return
        try:
            if current:
                run_git(repo, "remote", "set-url", "origin", url)
            else:
                run_git(repo, "remote", "add", "origin", url)
            self.refresh_status()
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def configure_identity(self):
        name = simpledialog.askstring("Git 사용자 설정", "user.name:")
        if not name:
            return
        email = simpledialog.askstring("Git 사용자 설정", "user.email:")
        if not email:
            return
        try:
            run_git(None, "config", "--global", "user.name", name.strip())
            run_git(None, "config", "--global", "user.email", email.strip())
            messagebox.showinfo(APP_NAME, "Git 사용자 설정을 저장했습니다.")
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def open_folder(self):
        repo = self.selected_repo()
        if not repo:
            return
        if os.name == "nt":
            os.startfile(repo)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(repo)])

    def _run_locked(self, label: str, work, done=None):
        if self.busy:
            messagebox.showinfo(APP_NAME, "Git Manager 작업이 이미 진행 중입니다.")
            return
        if self.operation_lock and not self.operation_lock.acquire("Git Manager"):
            messagebox.showwarning(APP_NAME, f"현재 {self.operation_lock.owner} 작업이 진행 중입니다. 완료 후 다시 실행해주세요.")
            return
        self.busy = True
        self.status_var.set(label)
        self.log(f"===== {label} 시작 =====")

        def job():
            try:
                result = work()
                self.after(0, lambda: finish(result, None))
            except Exception as exc:
                self.after(0, lambda: finish(None, exc))

        def finish(result, error):
            self.busy = False
            if self.operation_lock:
                self.operation_lock.release("Git Manager")
            if error:
                self.status_var.set("오류")
                self.log(f"실패: {error}")
                messagebox.showerror(APP_NAME, str(error))
            else:
                self.status_var.set("완료")
                self.log(f"===== {label} 완료 =====")
                if done:
                    done(result)

        threading.Thread(target=job, daemon=True).start()

    def refresh_status(self):
        repo = self.selected_repo()
        if not repo:
            self.repo_info_var.set("Repository를 선택해주세요.")
            return
        if not is_git_repo(repo):
            self.repo_info_var.set(f"Git Repository 아님: {repo}")
            return
        selected = self.selected_target_keys()
        if not selected:
            selected = list(self.targets.keys())

        def work():
            origin = origin_url(repo)
            branch = current_branch(repo)
            if origin:
                run_git(repo, "fetch", "origin", "--tags", timeout=180)
            remote_ref = f"origin/{branch}" if origin and branch != "(detached)" else None
            rows = []
            for key in selected:
                t = self.targets[key]
                local_folder, local_alias_issue = _resolve_local_target_folder(repo, t)
                head_folder_name, head_alias_issue = _resolve_git_tree_folder_name(repo, "HEAD", t, label="HEAD")
                remote_folder_name, remote_alias_issue = _resolve_remote_folder_name(repo, remote_ref, t)
                physical_folder_name = local_folder.name
                local_names = _local_names(local_folder)
                remote_names = _tree_names(repo, remote_ref, remote_folder_name) if remote_ref else []
                local_summary = _release_summary(local_names, t)
                remote_summary = _release_summary(remote_names, t) if remote_ref else "-"
                local_sha = _tree_sha(repo, "HEAD", head_folder_name)
                remote_sha = _tree_sha(repo, remote_ref, remote_folder_name) if remote_ref else None
                changed = _working_changed_aliases(
                    repo, physical_folder_name, head_folder_name, remote_folder_name, t["folder"]
                )
                alias_issue = local_alias_issue or head_alias_issue or remote_alias_issue
                if alias_issue:
                    state = "확인 필요"
                elif changed:
                    state = "로컬 변경 있음"
                elif remote_ref is None:
                    state = "원격 없음"
                elif local_sha and remote_sha and local_sha == remote_sha:
                    state = "동일"
                elif local_sha and remote_sha:
                    state = "차이 있음"
                elif local_sha and not remote_sha:
                    state = "로컬만 있음"
                elif remote_sha and not local_sha:
                    state = "원격만 있음"
                else:
                    state = "대상 없음"
                tree_note = f"{(local_sha or '-')[:10]} / {(remote_sha or '-')[:10]}"
                if alias_issue:
                    tree_note = alias_issue
                else:
                    alias_parts = []
                    canonical = str(t["folder"])
                    if head_folder_name != canonical:
                        alias_parts.append(f"HEAD:{head_folder_name}")
                    if remote_ref and remote_folder_name != canonical:
                        alias_parts.append(f"origin:{remote_folder_name}")
                    if physical_folder_name.casefold() != canonical.casefold():
                        alias_parts.append(f"FS:{physical_folder_name}")
                    if alias_parts:
                        tree_note += " | 별칭 호환: " + " / ".join(alias_parts)
                rows.append((t["ui_label"], local_summary, remote_summary, state, tree_note))
            div = tracking_divergence(repo)
            local_release = _local_automation_release(repo)
            remote_release = _remote_automation_release(repo, remote_ref) if remote_ref else None
            return branch, origin, div, rows, local_release, remote_release

        def done(result):
            branch, origin, div, rows, local_release, remote_release = result
            for item in self.tree.get_children():
                self.tree.delete(item)
            for row in rows:
                self.tree.insert("", "end", values=row)
            div_text = "upstream 없음" if div is None else f"ahead {div[0]} / behind {div[1]}"
            release_text = _release_relation_text(local_release, remote_release)
            self.repo_info_var.set(
                f"{repo} | branch={branch} | {div_text} | origin={origin or '-'} | AM {release_text}"
            )
            self.log(f"1~6 상태 확인 완료: {len(rows)}개 대상")
            self.log(f"Automation Manager Release 비교: {release_text}")

        self._run_locked("Git 상태 확인", work, done)

    def pull_repo(self):
        repo = self.selected_repo()
        if not repo or not is_git_repo(repo):
            messagebox.showinfo(APP_NAME, "Git Repository를 선택해주세요.")
            return
        if local_changes(repo):
            messagebox.showwarning(APP_NAME, "미Commit 로컬 변경이 있어 Pull을 중단합니다. 먼저 Commit/정리해주세요.")
            return
        if not origin_url(repo):
            messagebox.showwarning(APP_NAME, "origin 원격 저장소가 없습니다.")
            return

        def work():
            before_runtime = _runtime_fingerprint(self.workspace_root) if repo == self.workspace_root else ()
            branch = current_branch(repo)
            if branch == "(detached)":
                raise GitError("detached HEAD에서는 자동 Pull하지 않습니다.")
            run_git(repo, "fetch", "origin", "--tags", timeout=180)
            div = tracking_divergence(repo)
            if div and div[0] > 0 and div[1] > 0:
                raise GitError("Local/Remote 이력이 분기되어 자동 Merge하지 않습니다.")
            result = run_git(repo, "pull", "--ff-only", timeout=300)
            after_runtime = _runtime_fingerprint(self.workspace_root) if repo == self.workspace_root else ()
            return result, bool(before_runtime and before_runtime != after_runtime)

        def done(payload):
            result, runtime_changed = payload
            self.refresh_status()
            if runtime_changed:
                restart = messagebox.askyesno(
                    APP_NAME,
                    "최신 버전을 받았습니다.\n\nAutomation Manager / Git Manager / BoardRepo 실행 코드가 갱신되었습니다.\n현재 프로세스는 이전 코드를 메모리에 유지하고 있으므로 재실행이 권장됩니다.\n\n지금 Automation Manager를 재실행할까요?",
                )
                if restart:
                    self.restart_automation_manager()
                return
            messagebox.showinfo(APP_NAME, result or "최신 버전을 받았습니다.")

        self._run_locked("Repository Pull", work, done)

    def push_repo(self):
        repo = self.selected_repo()
        if not repo or not is_git_repo(repo):
            messagebox.showinfo(APP_NAME, "Git Repository를 선택해주세요.")
            return
        if not origin_url(repo):
            messagebox.showwarning(APP_NAME, "origin 원격 저장소가 없습니다.")
            return
        if not local_changes(repo):
            messagebox.showinfo(APP_NAME, "현재 변경된 파일이 없습니다.")
            return
        if not git_identity_ok(repo):
            messagebox.showwarning(APP_NAME, "Git user.name/user.email이 설정되지 않았습니다.")
            return
        msg = simpledialog.askstring("새 버전 업로드", "변경 내용을 입력하세요:")
        if not msg:
            return

        def work():
            branch = current_branch(repo)
            if branch == "(detached)":
                raise GitError("detached HEAD에서는 업로드할 수 없습니다.")
            run_git(repo, "fetch", "origin", "--tags", timeout=180)
            div = tracking_divergence(repo)
            if div is not None and div[1] > 0:
                raise GitError("원격 저장소에 더 최신 변경이 있습니다. 먼저 Pull해주세요.")
            _guard_not_older_than_remote(repo, branch)
            tag = next_version_tag(repo)
            run_git(repo, "add", "-A")
            run_git(repo, "commit", "-m", f"[{tag}] {msg.strip()}", timeout=180)
            run_git(repo, "tag", "-a", tag, "-m", msg.strip())
            if div is None:
                run_git(repo, "push", "-u", "origin", branch, timeout=300)
            else:
                run_git(repo, "push", "origin", branch, timeout=300)
            run_git(repo, "push", "origin", tag, timeout=180)
            return tag

        self._run_locked("Repository Commit + Push", work, lambda tag: (messagebox.showinfo(APP_NAME, f"업로드 완료\nTag: {tag}"), self.refresh_status()))

    def restart_automation_manager(self):
        launcher = self.workspace_root / "Automation_Manager.pyw"
        if not launcher.is_file():
            messagebox.showwarning(APP_NAME, f"Automation Manager 실행기를 찾지 못했습니다:\n{launcher}")
            return
        try:
            top = self.winfo_toplevel()
            top.destroy()
        except Exception:
            pass
        os.execl(sys.executable, sys.executable, str(launcher))

    def show_history(self):
        repo = self.selected_repo()
        if not repo or not is_git_repo(repo):
            return
        try:
            fmt = "%h%x09%ad%x09%D%x09%s"
            out = run_git(repo, "log", "--date=format:%Y-%m-%d %H:%M", f"--pretty=format:{fmt}", "-100")
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return
        win = tk.Toplevel(self)
        win.title("Git 이력")
        win.geometry("900x520")
        text = tk.Text(win, wrap="none")
        text.pack(fill="both", expand=True)
        text.insert("1.0", out)
        text.configure(state="disabled")
