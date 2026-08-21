from __future__ import annotations

from dataclasses import dataclass
import json
import queue
import threading
import traceback
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from archive_selector import (
    ArchiveSelectionError,
    select_latest_archive,
    version_label_from_archive,
)
from browser_automation import upload_snapshot
from browser_download import (
    DownloadResult,
    DownloadTarget,
    STATUS_CONFLICT as DOWNLOAD_CONFLICT,
    STATUS_DOWNLOADED,
    STATUS_ERROR as DOWNLOAD_ERROR,
    STATUS_LOCAL_NEWER,
    STATUS_REMOTE_NONE,
    STATUS_UP_TO_DATE,
    sync_selected_downloads,
)
from credential_store import CredentialStoreError, save_credentials
from duplicate_checker import (
    RemoteCheckItem,
    STATUS_CONFLICT,
    STATUS_DUPLICATE,
    STATUS_ERROR,
    STATUS_NEW,
    check_remote_items,
)
from environment_manager import check_environment, format_status, install_or_repair, prepare_offline_packages
from ext_file_manager import ExtFileError, list_ext_files
from folder_resolver import FolderResolutionError, app_root, resolve_target_folder
from site_profile import load_site_profile
from catalog import load_catalog, boardrepo_targets_from_catalog


APP_ROOT = app_root()
CONFIG_PATH = APP_ROOT / "config.json"
SITE_PROFILE_PATH = APP_ROOT / "site_profile.json"
BROWSER_PROFILE_DIR = APP_ROOT / "browser_profile"


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@dataclass(frozen=True)
class UploadPlanItem:
    target_key: str
    display_name: str
    board_url: str
    folder: Path
    file_path: Path
    kind: str  # "versioned" | "ext"
    title: str
    body: str
    sha256: str | None = None
    local_summary: str = ""


@dataclass(frozen=True)
class PreflightIssue:
    target_key: str
    display_name: str
    phase: str
    message: str
    file_name: str | None = None


class BoardRepoFrame(ttk.Frame):
    def __init__(self, master, workspace_root: Path, target_vars=None, operation_lock=None):
        super().__init__(master)
        self.workspace_root = Path(workspace_root).resolve()
        self.operation_lock = operation_lock
        self.config_data = load_config()
        catalog = load_catalog(self.workspace_root / "program_catalog.json")
        self.config_data["targets"] = boardrepo_targets_from_catalog(catalog)
        self.site_profile = load_site_profile(SITE_PROFILE_PATH)
        self._event_queue = queue.Queue()
        self._running = False
        self._environment_ready = False
        self._action_widgets = []
        self.target_vars = target_vars or {
            key: tk.BooleanVar(value=False)
            for key in self.config_data["targets"].keys()
        }
        self._build_ui()
        self.after(100, self._poll_events)
        self.after(250, self.check_environment_async)

    def _build_ui(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x")
        ttk.Label(header, text="BoardRepo", font=("Segoe UI", 18, "bold")).pack(side="left")
        ttk.Label(
            header,
            text="그룹웨어 게시판 ↔ 1~6 공용 폴더 업로드/다운로드",
        ).pack(side="left", padx=(12, 0), pady=(6, 0))

        env_area = ttk.Frame(header)
        env_area.pack(side="right")
        self.env_status_var = tk.StringVar(value="환경 확인 중...")
        ttk.Label(env_area, textvariable=self.env_status_var).pack(side="left", padx=(0, 8))
        self.check_env_btn = ttk.Button(env_area, text="환경 확인", command=self.check_environment_async)
        self.check_env_btn.pack(side="left")
        self.install_env_btn = ttk.Button(env_area, text="필수 모듈 설치/복구", command=self.install_environment_async)
        self.install_env_btn.pack(side="left", padx=(6, 0))
        self.prepare_offline_btn = ttk.Button(env_area, text="회사용 오프라인 준비", command=self.prepare_offline_async)
        self.prepare_offline_btn.pack(side="left", padx=(6, 0))
        self.site_profile_btn = ttk.Button(env_area, text="사이트 설정", command=self.show_site_profile_summary)
        self.site_profile_btn.pack(side="left", padx=(6, 0))

        ttk.Separator(root).pack(fill="x", pady=10)
        ttk.Label(
            root,
            text="대상 선택은 창 상단의 공통 1~6 체크박스를 사용합니다. 5=Git 게시판(board/392), 6=보드관리(board/393).",
        ).pack(anchor="w")

        actions = ttk.Frame(root)
        actions.pack(fill="x", pady=(10, 8))
        self.check_file_btn = ttk.Button(actions, text="업로드 파일 확인", command=self.check_selected_files)
        self.check_file_btn.pack(side="left")
        self.credential_btn = ttk.Button(actions, text="자격증명 저장", command=self.save_credential_dialog)
        self.credential_btn.pack(side="left", padx=(6, 0))
        self.upload_btn = tk.Button(
            actions, text="선택 항목 업로드", command=self.run_selected_uploads, width=18,
            bg="#DFF3E4", activebackground="#CDEBD6", fg="#1F4D2E", relief="raised", bd=1, font=("Segoe UI", 9, "bold")
        )
        self.upload_btn.pack(side="left", padx=(18, 0))
        self.download_btn = tk.Button(
            actions, text="선택 항목 다운로드", command=self.run_selected_downloads, width=18,
            bg="#DCEBFA", activebackground="#C9E0F7", fg="#234A6D", relief="raised", bd=1, font=("Segoe UI", 9, "bold")
        )
        self.download_btn.pack(side="left", padx=(6, 0))

        status_frame = ttk.LabelFrame(root, text="BoardRepo 로그", padding=8)
        status_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.log_text = tk.Text(status_frame, height=20, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True)
        self.status_var = tk.StringVar(value="대기")
        ttk.Label(root, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))

        self._action_widgets = [
            self.check_env_btn, self.install_env_btn, self.prepare_offline_btn, self.site_profile_btn,
            self.check_file_btn, self.credential_btn, self.upload_btn, self.download_btn,
        ]

    def log(self, message: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        self._event_queue.put(("log", f"[{stamp}] {message}"))

    def _set_controls_state(self, state: str):
        for widget in self._action_widgets:
            try:
                widget.configure(state=state)
            except tk.TclError:
                pass

    def _poll_events(self):
        try:
            while True:
                kind, payload = self._event_queue.get_nowait()

                if kind == "log":
                    self.log_text.configure(state="normal")
                    self.log_text.insert("end", payload + "\n")
                    self.log_text.see("end")
                    self.log_text.configure(state="disabled")

                elif kind == "done":
                    self._running = False
                    if self.operation_lock:
                        self.operation_lock.release("BoardRepo")
                    self._set_controls_state("normal")
                    self.status_var.set(payload)

                elif kind == "status":
                    self.status_var.set(payload)

                elif kind == "warning":
                    title, message = payload
                    messagebox.showwarning(title, message)

                elif kind == "info":
                    title, message = payload
                    messagebox.showinfo(title, message)

                elif kind == "env":
                    ready, short_text = payload
                    self._environment_ready = ready
                    self.env_status_var.set(short_text)

        except queue.Empty:
            pass

        self.after(100, self._poll_events)

    def _set_running(self, status_text="작업 중..."):
        if self._running:
            messagebox.showinfo("BoardRepo", "이미 작업을 수행 중입니다.")
            return False
        if self.operation_lock and not self.operation_lock.acquire("BoardRepo"):
            messagebox.showwarning(
                "BoardRepo",
                f"현재 {self.operation_lock.owner} 작업이 진행 중입니다. 완료 후 다시 실행해주세요.",
            )
            return False
        self._running = True
        self._set_controls_state("disabled")
        self.status_var.set(status_text)
        return True

    # -----------------------
    # Environment management
    # -----------------------
    def check_environment_async(self):
        if self._running:
            return
        if not self._set_running("환경 확인 중..."):
            return
        threading.Thread(target=self._check_environment_worker, daemon=True).start()

    def _check_environment_worker(self):
        try:
            status = check_environment(self.config_data, probe_browser=True)
            self.log("실행 환경 확인 결과")
            for line in format_status(status).splitlines():
                self.log(line)
            self._event_queue.put(
                ("env", (status.ready, "환경: 사용 가능" if status.ready else "환경: 설치 필요"))
            )
            self._event_queue.put(("done", "환경 확인 완료"))
        except Exception as exc:
            self.log(f"환경 확인 실패: {exc}")
            self.log(traceback.format_exc())
            self._event_queue.put(("env", (False, "환경: 확인 실패")))
            self._event_queue.put(("done", "환경 확인 실패"))

    def install_environment_async(self):
        if not self._set_running("필수 모듈 설치/복구 중..."):
            return
        self.log("BoardRepo 내부에서 필수 모듈 설치/복구를 시작합니다.")
        threading.Thread(target=self._install_environment_worker, daemon=True).start()

    def _install_environment_worker(self):
        try:
            status = install_or_repair(self.log, self.config_data)
            self.log("필수 모듈 설치/복구가 완료되었습니다.")
            for line in format_status(status).splitlines():
                self.log(line)
            self._event_queue.put(("env", (True, "환경: 사용 가능")))
            self._event_queue.put(("done", "설치/복구 완료"))
        except Exception as exc:
            self.log(f"설치/복구 실패: {exc}")
            self.log(traceback.format_exc())
            self._event_queue.put(("env", (False, "환경: 설치 실패")))
            self._event_queue.put(("done", "설치/복구 실패"))

    def prepare_offline_async(self):
        if not self._set_running("회사 PC용 오프라인 패키지 준비 중..."):
            return
        self.log("인터넷이 가능한 Windows PC 기준으로 회사 PC용 Offline Wheelhouse/Portable Vendor를 준비합니다.")
        threading.Thread(target=self._prepare_offline_worker, daemon=True).start()

    def _prepare_offline_worker(self):
        try:
            path = prepare_offline_packages(self.log, self.config_data)
            self.log(f"회사용 오프라인 패키지 준비가 완료되었습니다: {path}")
            status = check_environment(self.config_data, probe_browser=True)
            for line in format_status(status).splitlines():
                self.log(line)
            self._event_queue.put(("info", ("오프라인 준비 완료", "회사 PC용 Offline Wheelhouse와 현재 Python용 Portable Vendor를 준비했습니다.\n\nAutomation Manager 폴더 전체를 회사 PC로 가져가면 됩니다.")))
            self._event_queue.put(("done", "회사용 오프라인 준비 완료"))
        except Exception as exc:
            self.log(f"회사용 오프라인 준비 실패: {exc}")
            self.log(traceback.format_exc())
            self._event_queue.put(("warning", ("오프라인 준비 실패", str(exc))))
            self._event_queue.put(("done", "회사용 오프라인 준비 실패"))

    def _ensure_environment_before_upload(self) -> bool:
        status = check_environment(self.config_data, probe_browser=False)
        self._environment_ready = status.ready
        self._event_queue.put(
            ("env", (status.ready, "환경: 사용 가능" if status.ready else "환경: 설치 필요"))
        )
        if status.ready:
            return True

        messagebox.showwarning(
            "필수 모듈 설치 필요",
            "BoardRepo의 그룹웨어 자동화 환경이 아직 준비되지 않았습니다.\n\n"
            + format_status(status)
            + "\n\n오른쪽 위의 [필수 모듈 설치/복구] 버튼을 먼저 눌러주세요.",
        )
        return False

    def show_site_profile_summary(self):
        routing = self.site_profile["routing"]
        login_cfg = self.site_profile["login"]
        editor = self.site_profile["editor"]
        readiness = self.site_profile.get("readiness", {})
        duplicate = self.config_data.get("remote_duplicate_check", {})
        download_cfg = self.config_data.get("download", {})

        message = (
            f"프로필: {self.site_profile.get('profile_name', '-')}\n"
            f"버전: {self.site_profile.get('profile_version', '-')}\n\n"
            f"작성 버튼 우선: {routing.get('prefer_write_button', True)}\n"
            f"직접 작성 URL Fallback: {routing.get('fallback_to_direct_write_url', True)}\n"
            f"CAPTCHA 처리: {login_cfg.get('captcha_policy', 'manual')}\n"
            f"기본 안정화: {readiness.get('default_stabilize_ms', '-')}ms\n"
            f"중복검사 최대 게시판 페이지: {duplicate.get('max_board_pages', '-')}\n"
            f"다운로드 탐색 최대 게시판 페이지: {download_cfg.get('max_board_pages', '-')}\n\n"
            f"새글쓰기 후보: {len(self.site_profile['board'].get('write_button_candidates', []))}개\n"
            f"제목 입력 후보: {len(editor.get('title_input_candidates', []))}개\n"
            f"파일 첨부 후보: {len(editor.get('file_input_candidates', []))}개\n"
            f"등록 버튼 후보: {len(editor.get('submit_button_candidates', []))}개\n\n"
            "상세 규칙은 config.json / site_profile.json에서 수정할 수 있습니다."
        )
        messagebox.showinfo("사이트 설정 확인", message)

    # -----------------------
    # Selection / local preflight
    # -----------------------
    def select_all_targets(self):
        for var in self.target_vars.values():
            var.set(True)

    def clear_all_targets(self):
        for var in self.target_vars.values():
            var.set(False)

    def _selected_target_keys(self):
        return [
            key
            for key in self.config_data["targets"].keys()
            if self.target_vars[key].get()
        ]

    def _archive_extensions(self):
        return self.config_data.get("archive_selection", {}).get(
            "extensions",
            [".zip", ".7z", ".rar"],
        )

    def _build_target_plan(self, key: str) -> list[UploadPlanItem]:
        """
        Build a local upload plan for exactly one checkbox target.

        Keeping target planning isolated is important: one bad target must not
        invalidate unrelated checked targets.
        """
        target = self.config_data["targets"][key]
        display_name = target["display_name"]
        folder = resolve_target_folder(self.workspace_root, target["folder_aliases"])
        plan: list[UploadPlanItem] = []

        if key == "Ext":
            ext_cfg = self.config_data.get("ext_upload") or {}
            ext_files = list_ext_files(folder, ext_cfg)

            if not ext_files:
                self.log(
                    "Ext 폴더에 업로드할 일반파일이 없습니다. "
                    "Ext는 빈 항목으로 처리합니다."
                )

            for info in ext_files:
                created = datetime.now().isoformat(timespec="seconds")
                title = ext_cfg["title_template"].format(filename=info.path.name)
                body = ext_cfg["body_template"].format(
                    filename=info.path.name,
                    size_bytes=info.size_bytes,
                    sha256=info.sha256,
                    created=created,
                    source_folder=folder.name,
                )
                plan.append(
                    UploadPlanItem(
                        target_key=key,
                        display_name=display_name,
                        board_url=target["board_url"],
                        folder=folder,
                        file_path=info.path,
                        kind="ext",
                        title=title,
                        body=body,
                        sha256=info.sha256,
                        local_summary=(
                            f"파일={info.path.name}, size={info.size_bytes}, "
                            f"sha256={info.sha256[:12]}..."
                        ),
                    )
                )
            return plan

        strategy = target.get("archive_strategy", "date_rev_counter")
        selection = select_latest_archive(
            folder=folder,
            target_name=display_name,
            aliases=target.get("package_aliases") or target["folder_aliases"],
            extensions=self._archive_extensions(),
            strategy=strategy,
        )
        archive = selection.selected
        version = version_label_from_archive(archive.path, display_name)
        created = datetime.now().isoformat(timespec="seconds")
        title = self.config_data["upload"]["title_template"].format(
            display_name=display_name,
            version=version,
        )
        body = self.config_data["upload"]["body_template"].format(
            display_name=display_name,
            version=version,
            created=created,
            source_folder=selection.folder.name,
            zip_name=archive.path.name,
        )
        plan.append(
            UploadPlanItem(
                target_key=key,
                display_name=display_name,
                board_url=target["board_url"],
                folder=selection.folder,
                file_path=archive.path,
                kind="versioned",
                title=title,
                body=body,
                local_summary=(
                    f"파일={archive.path.name}, date={archive.date_token or '없음'}, "
                    f"rev={archive.rev if archive.rev is not None else '미사용'}, "
                    f"counter={archive.counter}, 전략={selection.strategy}, "
                    f"규칙={selection.rule_summary}"
                ),
            )
        )
        return plan

    def _build_local_plan(self, selected: list[str]) -> list[UploadPlanItem]:
        """Strict helper retained for simple callers/tests."""
        plan: list[UploadPlanItem] = []
        for key in selected:
            plan.extend(self._build_target_plan(key))
        return plan

    def _build_local_plan_tolerant(
        self,
        selected: list[str],
    ) -> tuple[list[UploadPlanItem], list[PreflightIssue]]:
        """
        Build each target independently.

        A broken selected target is recorded and skipped;
        unrelated checked targets continue to the remote duplicate phase.
        """
        plan: list[UploadPlanItem] = []
        issues: list[PreflightIssue] = []

        for key in selected:
            target = self.config_data["targets"][key]
            try:
                items = self._build_target_plan(key)
                plan.extend(items)
            except (ArchiveSelectionError, FolderResolutionError, ExtFileError) as exc:
                issue = PreflightIssue(
                    target_key=key,
                    display_name=target["display_name"],
                    phase="LOCAL",
                    message=str(exc),
                )
                issues.append(issue)
                self.log(
                    f"로컬 확인 필요 Skip [{issue.display_name}]: {issue.message}"
                )
            except Exception as exc:
                issue = PreflightIssue(
                    target_key=key,
                    display_name=target["display_name"],
                    phase="LOCAL",
                    message=f"{type(exc).__name__}: {exc}",
                )
                issues.append(issue)
                self.log(
                    f"로컬 처리 오류 Skip [{issue.display_name}]: {issue.message}"
                )

        return plan, issues

    def _remote_check_items(self, plan: list[UploadPlanItem]) -> list[RemoteCheckItem]:
        return [
            RemoteCheckItem(
                target_key=item.target_key,
                display_name=item.display_name,
                board_url=item.board_url,
                file_path=item.file_path,
                exact_title=item.title,
                kind=item.kind,
                sha256=item.sha256,
            )
            for item in plan
        ]

    def _target_result_summary(
        self,
        selected: list[str],
        successes,
        duplicates,
        attention_results,
        local_issues,
        failures,
        *,
        common_stop: bool = False,
    ) -> str:
        """
        Build the compact four-checkbox summary shown at the top of problem popups.

        All four canonical targets are listed. Unchecked targets are shown as
        '미선택' so the popup mirrors the GUI checkbox area.
        """
        lines = ["[체크박스 실행 결과 요약]"]

        success_counts = {}
        duplicate_counts = {}
        attention_counts = {}
        failure_counts = {}

        for item in successes:
            success_counts[item.target_key] = success_counts.get(item.target_key, 0) + 1

        for result in duplicates:
            key = result.item.target_key
            duplicate_counts[key] = duplicate_counts.get(key, 0) + 1

        for result in attention_results:
            key = result.item.target_key
            attention_counts[key] = attention_counts.get(key, 0) + 1

        for issue in local_issues:
            key = issue.target_key
            attention_counts[key] = attention_counts.get(key, 0) + 1

        for item, _message in failures:
            failure_counts[item.target_key] = failure_counts.get(item.target_key, 0) + 1

        selected_set = set(selected)

        for key, target in self.config_data["targets"].items():
            display = target.get("ui_label", target["display_name"])

            if key not in selected_set:
                status = "미선택"
            elif common_stop:
                status = "중단 - 공통 오류"
            else:
                s = success_counts.get(key, 0)
                d = duplicate_counts.get(key, 0)
                a = attention_counts.get(key, 0)
                f = failure_counts.get(key, 0)

                if s and not (d or a or f):
                    status = "정상 실행"
                elif d and not (s or a or f):
                    status = "중복 - 업로드 안 함"
                elif a and not (s or d or f):
                    status = "확인 필요 - 업로드 안 함"
                elif f and not (s or d or a):
                    status = "업로드 실패"
                elif not (s or d or a or f):
                    status = "업로드할 파일 없음"
                else:
                    parts = []
                    if s:
                        parts.append(f"정상 {s}")
                    if d:
                        parts.append(f"중복 {d}")
                    if a:
                        parts.append(f"확인필요 {a}")
                    if f:
                        parts.append(f"실패 {f}")
                    status = " / ".join(parts)

            lines.append(f"{display:<12}: {status}")

        return "\\n".join(lines)

    def _problem_popup_message(
        self,
        selected: list[str],
        successes,
        duplicates,
        attention_results,
        local_issues,
        failures,
        *,
        common_stop: bool = False,
        common_detail: str | None = None,
    ) -> str:
        summary = self._target_result_summary(
            selected,
            successes,
            duplicates,
            attention_results,
            local_issues,
            failures,
            common_stop=common_stop,
        )

        details = []

        for result in duplicates:
            details.append(
                f"[중복] [{result.item.display_name}] "
                f"{result.item.file_path.name}\\n{result.evidence}"
            )

        for result in attention_results:
            details.append(
                f"[확인 필요] [{result.item.display_name}] "
                f"{result.item.file_path.name}\\n{result.evidence}"
            )

        for issue in local_issues:
            details.append(
                f"[확인 필요] [{issue.display_name}] "
                f"{issue.file_name or '대상 전체'}\\n{issue.message}"
            )

        for item, message in failures:
            details.append(
                f"[업로드 실패] [{item.display_name}] "
                f"{item.file_path.name}\\n{message}"
            )

        if common_detail:
            details.append(f"[공통 오류]\\n{common_detail}")

        if details:
            return (
                summary
                + "\\n\\n------------------------------\\n"
                + "[상세]\\n"
                + "\\n\\n".join(details)
            )

        return summary

    def run_selected_uploads(self):
        selected = self._selected_target_keys()
        if not selected:
            messagebox.showinfo(
                "업로드 대상 선택",
                "업로드할 항목을 하나 이상 체크해주세요.",
            )
            return

        plan, local_issues = self._build_local_plan_tolerant(selected)

        for item in plan:
            self.log(
                f"로컬 사전 선택 [{item.display_name}]: {item.local_summary}"
            )

        if not plan:
            if local_issues:
                lines = [
                    f"[{issue.display_name}] {issue.message}"
                    for issue in local_issues
                ]
                messagebox.showwarning(
                    "확인 필요 항목",
                    self._problem_popup_message(
                        selected,
                        [],
                        [],
                        [],
                        local_issues,
                        [],
                    )
                    + "\n\n선택한 항목에서 업로드 가능한 파일을 확정하지 못했습니다.",
                )
                self.status_var.set(
                    f"완료 - 업로드 0 / 확인 필요 Skip {len(local_issues)}"
                )
            else:
                messagebox.showinfo(
                    "업로드할 파일 없음",
                    "선택된 대상에서 업로드할 파일을 찾지 못했습니다.",
                )
            return

        if not self._ensure_environment_before_upload():
            return

        if not self._set_running("게시판 중복검사 중..."):
            return

        threading.Thread(
            target=self._remote_preflight_and_upload_worker,
            args=(selected, plan, local_issues),
            daemon=True,
        ).start()

    # -----------------------
    # Remote duplicate preflight + upload
    # -----------------------
    def _remote_preflight_and_upload_worker(
        self,
        selected: list[str],
        plan: list[UploadPlanItem],
        local_issues: list[PreflightIssue],
    ):
        try:
            self.log("실제 업로드 전에 게시판 원격 중복검사를 시작합니다.")
            remote_results = check_remote_items(
                self._remote_check_items(plan),
                BROWSER_PROFILE_DIR,
                self.config_data,
                self.site_profile,
                self.log,
            )
        except Exception as exc:
            # A fatal/common session failure (e.g. browser cannot start or login
            # cannot be established) still stops the batch because no item's
            # duplicate status can be trusted.
            self.log(f"공통 원격 중복검사 세션 실패: {exc}")
            self.log(traceback.format_exc())
            self._event_queue.put((
                "warning",
                (
                    "게시판 중복검사 실패",
                    self._problem_popup_message(
                        selected,
                        [],
                        [],
                        [],
                        local_issues,
                        [],
                        common_stop=True,
                        common_detail=(
                            "그룹웨어 중복검사 세션 자체를 시작/유지하지 못해 "
                            "남은 항목의 안전한 중복 판정이 불가능합니다.\n"
                            f"{exc}"
                        ),
                    ),
                ),
            ))
            self._event_queue.put(("done", "중지 - 공통 중복검사 세션 실패"))
            return

        duplicates = [r for r in remote_results if r.status == STATUS_DUPLICATE]
        attention_results = [
            r for r in remote_results
            if r.status in {STATUS_CONFLICT, STATUS_ERROR}
        ]

        skipped_keys = {
            (
                r.item.target_key,
                str(r.item.file_path.resolve()),
                r.item.exact_title,
            )
            for r in [*duplicates, *attention_results]
        }

        new_plan = [
            item
            for item in plan
            if (
                item.target_key,
                str(item.file_path.resolve()),
                item.title,
            )
            not in skipped_keys
        ]

        for result in duplicates:
            self.log(
                f"중복 Skip [{result.item.display_name}] "
                f"{result.item.file_path.name}: {result.evidence}"
            )

        for result in attention_results:
            label = "충돌" if result.status == STATUS_CONFLICT else "검사 오류"
            self.log(
                f"확인 필요 Skip [{result.item.display_name}] "
                f"{result.item.file_path.name} ({label}): {result.evidence}"
            )

        self._event_queue.put((
            "status",
            f"신규 파일 업로드 중... 0/{len(new_plan)}",
        ))
        self._batch_upload_worker(
            new_plan,
            duplicates,
            attention_results,
            local_issues,
            selected,
        )

    def _batch_upload_worker(
        self,
        plan: list[UploadPlanItem],
        duplicates,
        attention_results,
        local_issues: list[PreflightIssue],
        selected: list[str],
    ):
        successes: list[UploadPlanItem] = []
        failures: list[tuple[UploadPlanItem, str]] = []

        self.log("")
        self.log("===== BoardRepo 실제 업로드 시작 =====")
        if plan:
            self.log(
                "신규 업로드 대상: "
                + ", ".join(
                    f"{item.display_name}:{item.file_path.name}"
                    for item in plan
                )
            )
        else:
            self.log("신규 업로드 대상이 없습니다. Skip 결과만 정리합니다.")

        total = len(plan)

        for index, item in enumerate(plan, start=1):
            self._event_queue.put((
                "status",
                f"업로드 중... {index}/{total} - "
                f"{item.display_name} / {item.file_path.name}",
            ))
            self.log("")
            self.log(
                f"===== [{index}/{total}] {item.display_name} / "
                f"{item.file_path.name} 업로드 시작 ====="
            )

            try:
                self._upload_plan_item(item)
                successes.append(item)
                self.log(
                    f"===== [{index}/{total}] {item.display_name} / "
                    f"{item.file_path.name} 업로드 완료 ====="
                )
            except Exception as exc:
                failures.append((item, str(exc)))
                self.log(
                    f"{item.display_name} / {item.file_path.name} 업로드 실패: {exc}"
                )
                self.log(traceback.format_exc())
                self.log(
                    "이 파일만 실패로 기록하고 나머지 신규 파일 업로드를 계속 진행합니다."
                )

        attention_count = len(attention_results) + len(local_issues)

        self.log("")
        self.log("===== BoardRepo 선택 업로드 결과 =====")
        self.log(
            f"업로드 완료: {len(successes)}개"
            + (
                " (" + ", ".join(item.file_path.name for item in successes) + ")"
                if successes else ""
            )
        )
        self.log(
            f"중복 Skip: {len(duplicates)}개"
            + (
                " (" + ", ".join(
                    result.item.file_path.name for result in duplicates
                ) + ")"
                if duplicates else ""
            )
        )

        attention_names = [
            f"{result.item.display_name}:{result.item.file_path.name}"
            for result in attention_results
        ] + [
            f"{issue.display_name}:{issue.file_name or '대상 전체'}"
            for issue in local_issues
        ]
        self.log(
            f"확인 필요 Skip: {attention_count}개"
            + (
                " (" + ", ".join(attention_names) + ")"
                if attention_names else ""
            )
        )
        self.log(
            f"업로드 실패: {len(failures)}개"
            + (
                " (" + ", ".join(item.file_path.name for item, _ in failures) + ")"
                if failures else ""
            )
        )

        if duplicates or attention_count or failures:
            self._event_queue.put((
                "warning",
                (
                    "업로드 결과 확인",
                    self._problem_popup_message(
                        selected,
                        successes,
                        duplicates,
                        attention_results,
                        local_issues,
                        failures,
                    ),
                ),
            ))

        if failures or attention_count:
            final_status = (
                f"부분 완료 - 업로드 {len(successes)} / "
                f"중복 {len(duplicates)} / 확인 필요 {attention_count} / "
                f"실패 {len(failures)}"
            )
        else:
            final_status = (
                f"완료 - 업로드 {len(successes)} / "
                f"중복 Skip {len(duplicates)}"
            )

        self._event_queue.put(("done", final_status))

    def _upload_plan_item(self, item: UploadPlanItem):
        self.log(f"대상: {item.display_name} ({item.target_key})")
        self.log(f"원본 폴더: {item.folder.name}")
        self.log(f"첨부 파일: {item.file_path.name}")
        if item.kind == "ext":
            self.log(
                f"Ext 파일 정보: size={item.file_path.stat().st_size} bytes, "
                f"sha256={item.sha256}"
            )

        # The proven v0.12/v0.14 write pipeline is reused unchanged.
        upload_snapshot(
            board_url=item.board_url,
            zip_path=item.file_path,
            title=item.title,
            body=item.body,
            browser_profile=BROWSER_PROFILE_DIR,
            config=self.config_data,
            site_profile=self.site_profile,
            log=self.log,
        )

        self.log("게시판 업로드 절차가 완료되었습니다.")

    # -----------------------
    # Board -> local download sync
    # -----------------------
    def _build_download_targets(
        self,
        selected: list[str],
    ) -> tuple[list[DownloadTarget], list[PreflightIssue]]:
        targets: list[DownloadTarget] = []
        issues: list[PreflightIssue] = []

        for key in selected:
            target = self.config_data["targets"][key]
            try:
                folder = resolve_target_folder(
                    self.workspace_root,
                    target["folder_aliases"],
                )
                targets.append(
                    DownloadTarget(
                        target_key=key,
                        display_name=target["display_name"],
                        board_url=target["board_url"],
                        folder=folder,
                        aliases=tuple(target.get("package_aliases") or target["folder_aliases"]),
                        mode=str(target.get("mode") or "versioned_archive"),
                    )
                )
            except FolderResolutionError as exc:
                issues.append(
                    PreflightIssue(
                        target_key=key,
                        display_name=target["display_name"],
                        phase="DOWNLOAD_LOCAL",
                        message=str(exc),
                    )
                )

        return targets, issues

    def run_selected_downloads(self):
        selected = self._selected_target_keys()
        if not selected:
            messagebox.showinfo(
                "다운로드 대상 선택",
                "다운로드할 항목을 하나 이상 체크해주세요.",
            )
            return

        targets, local_issues = self._build_download_targets(selected)

        if not targets:
            messagebox.showwarning(
                "다운로드 폴더 확인 필요",
                self._download_result_message(
                    selected,
                    [],
                    local_issues,
                ),
            )
            return

        if not self._ensure_environment_before_upload():
            return

        if not self._set_running("원격 최신파일 확인 중..."):
            return

        threading.Thread(
            target=self._download_worker,
            args=(selected, targets, local_issues),
            daemon=True,
        ).start()

    def _download_worker(
        self,
        selected: list[str],
        targets: list[DownloadTarget],
        local_issues: list[PreflightIssue],
    ):
        try:
            self.log("===== BoardRepo 다운로드 동기화 시작 =====")
            results = sync_selected_downloads(
                targets,
                BROWSER_PROFILE_DIR,
                self.config_data,
                self.site_profile,
                self.log,
            )
        except Exception as exc:
            self.log(f"공통 다운로드 세션 실패: {exc}")
            self.log(traceback.format_exc())
            common_results = [
                DownloadResult(
                    target_key=target.target_key,
                    display_name=target.display_name,
                    status=DOWNLOAD_ERROR,
                    filename=None,
                    reason=f"공통 다운로드 세션 실패: {exc}",
                )
                for target in targets
            ]
            self._event_queue.put((
                "warning",
                (
                    "다운로드 실패",
                    self._download_result_message(
                        selected,
                        common_results,
                        local_issues,
                    ),
                ),
            ))
            self._event_queue.put(("done", "중지 - 공통 다운로드 세션 실패"))
            return

        downloaded = [r for r in results if r.status == STATUS_DOWNLOADED]
        up_to_date = [r for r in results if r.status == STATUS_UP_TO_DATE]
        local_newer = [r for r in results if r.status == STATUS_LOCAL_NEWER]
        remote_none = [r for r in results if r.status == STATUS_REMOTE_NONE]
        conflicts = [r for r in results if r.status == DOWNLOAD_CONFLICT]
        errors = [r for r in results if r.status == DOWNLOAD_ERROR]

        self.log("")
        self.log("===== BoardRepo 다운로드 결과 =====")
        self.log(f"다운로드 완료: {len(downloaded)}개")
        self.log(f"이미 최신: {len(up_to_date)}개")
        self.log(f"로컬이 더 최신: {len(local_newer)}개")
        self.log(f"원격 파일 없음: {len(remote_none)}개")
        self.log(
            f"확인 필요: {len(conflicts) + len(local_issues)}개"
        )
        self.log(f"다운로드 실패: {len(errors)}개")

        message = self._download_result_message(
            selected,
            results,
            local_issues,
        )

        if conflicts or errors or local_issues:
            self._event_queue.put((
                "warning",
                ("다운로드 결과 확인", message),
            ))
        else:
            self._event_queue.put((
                "info",
                ("다운로드 결과", message),
            ))

        self._event_queue.put((
            "done",
            (
                f"다운로드 완료 {len(downloaded)} / "
                f"이미 최신 {len(up_to_date)} / "
                f"로컬 최신 {len(local_newer)} / "
                f"확인 필요 {len(conflicts) + len(local_issues)} / "
                f"실패 {len(errors)}"
            ),
        ))

    def _download_target_summary(
        self,
        selected: list[str],
        results: list[DownloadResult],
        local_issues: list[PreflightIssue],
    ) -> str:
        selected_set = set(selected)
        lines = ["[체크박스 다운로드 결과 요약]"]

        by_target: dict[str, list[DownloadResult]] = {}
        for result in results:
            by_target.setdefault(result.target_key, []).append(result)

        issue_counts: dict[str, int] = {}
        for issue in local_issues:
            issue_counts[issue.target_key] = issue_counts.get(issue.target_key, 0) + 1

        label_map = {
            STATUS_DOWNLOADED: "다운로드",
            STATUS_UP_TO_DATE: "이미 최신",
            STATUS_LOCAL_NEWER: "로컬이 더 최신",
            STATUS_REMOTE_NONE: "원격 없음",
            DOWNLOAD_CONFLICT: "확인필요",
            DOWNLOAD_ERROR: "실패",
        }

        for key, target in self.config_data["targets"].items():
            display = target.get("ui_label", target["display_name"])

            if key not in selected_set:
                status = "미선택"
            else:
                target_results = by_target.get(key, [])
                counts: dict[str, int] = {}
                for result in target_results:
                    counts[result.status] = counts.get(result.status, 0) + 1

                if issue_counts.get(key):
                    counts[DOWNLOAD_CONFLICT] = (
                        counts.get(DOWNLOAD_CONFLICT, 0)
                        + issue_counts[key]
                    )

                nonzero = [
                    (status_key, count)
                    for status_key, count in counts.items()
                    if count
                ]

                if not nonzero:
                    status = "처리 결과 없음"
                elif len(nonzero) == 1:
                    status_key, count = nonzero[0]
                    label = label_map.get(status_key, status_key)
                    status = label if count == 1 else f"{label} {count}"
                else:
                    ordered = [
                        STATUS_DOWNLOADED,
                        STATUS_UP_TO_DATE,
                        STATUS_LOCAL_NEWER,
                        STATUS_REMOTE_NONE,
                        DOWNLOAD_CONFLICT,
                        DOWNLOAD_ERROR,
                    ]
                    parts = []
                    for status_key in ordered:
                        count = counts.get(status_key, 0)
                        if count:
                            parts.append(
                                f"{label_map.get(status_key, status_key)} {count}"
                            )
                    status = " / ".join(parts)

            lines.append(f"{display:<12}: {status}")

        return "\n".join(lines)

    def _download_result_message(
        self,
        selected: list[str],
        results: list[DownloadResult],
        local_issues: list[PreflightIssue],
    ) -> str:
        summary = self._download_target_summary(
            selected,
            results,
            local_issues,
        )

        details = []

        for result in results:
            file_text = result.filename or "대상 전체"
            version_lines = []
            if result.local_version is not None:
                version_lines.append(f"로컬 : {result.local_version}")
            if result.remote_version is not None:
                version_lines.append(f"원격 : {result.remote_version}")

            version_text = (
                "\n" + "\n".join(version_lines)
                if version_lines else ""
            )
            details.append(
                f"[{result.display_name}] {file_text}\n"
                f"{result.reason}{version_text}"
            )

        for issue in local_issues:
            details.append(
                f"[{issue.display_name}] 대상 전체\n{issue.message}"
            )

        if details:
            return (
                summary
                + "\n\n------------------------------\n"
                + "[상세]\n"
                + "\n\n".join(details)
            )

        return summary

    # -----------------------
    # Local preview
    # -----------------------
    def check_selected_files(self):
        selected = self._selected_target_keys()
        if not selected:
            messagebox.showinfo(
                "업로드 파일 확인",
                "확인할 항목을 하나 이상 체크해주세요.",
            )
            return

        plan, issues = self._build_local_plan_tolerant(selected)

        grouped: dict[str, list[UploadPlanItem]] = {}
        for item in plan:
            grouped.setdefault(item.target_key, []).append(item)

        blocks = []
        for key in selected:
            display_name = self.config_data["targets"][key].get(
                "ui_label", self.config_data["targets"][key]["display_name"]
            )
            target_issues = [
                issue for issue in issues if issue.target_key == key
            ]
            if target_issues:
                blocks.append(
                    f"[{display_name}] 확인 필요 Skip\n"
                    + "\n".join(issue.message for issue in target_issues)
                )
                continue

            items = grouped.get(key, [])
            if not items:
                blocks.append(f"[{display_name}]\n업로드할 파일 없음")
                continue

            if key == "Ext":
                lines = [f"[{display_name}] 일반파일 후보 {len(items)}개"]
                for item in items[:20]:
                    lines.append(
                        f"- {item.file_path.name} "
                        f"({item.file_path.stat().st_size} bytes, "
                        f"SHA={item.sha256[:12]}...)"
                    )
                if len(items) > 20:
                    lines.append(f"... 외 {len(items) - 20}개")
                blocks.append("\n".join(lines))
            else:
                item = items[0]
                blocks.append(
                    f"[{display_name}]\n"
                    f"폴더: {item.folder}\n"
                    f"선택: {item.file_path.name}\n"
                    f"{item.local_summary}"
                )

        messagebox.showinfo(
            "업로드 파일 확인",
            "\n\n".join(blocks)
            + "\n\n※ 실제 업로드 전 게시판 중복검사를 수행하며, "
              "문제가 있는 항목만 Skip하고 나머지는 계속 진행합니다.",
        )

    def save_credential_dialog(self):
        status = check_environment(self.config_data, probe_browser=False)
        if not status.keyring_ok:
            messagebox.showwarning(
                "keyring 설치 필요",
                "자격증명 저장 기능을 사용하려면 오른쪽 위의 "
                "[필수 모듈 설치/복구]를 먼저 실행해주세요.",
            )
            return

        username = simpledialog.askstring(
            "그룹웨어 ID",
            "그룹웨어 ID를 입력하세요.",
            parent=self,
        )
        if username is None:
            return

        password = simpledialog.askstring(
            "그룹웨어 비밀번호",
            "그룹웨어 비밀번호를 입력하세요.",
            parent=self,
            show="*",
        )
        if password is None:
            return

        try:
            save_credentials(username, password)
            messagebox.showinfo(
                "저장 완료",
                "운영체제 자격 증명 저장소를 통해 계정정보를 저장했습니다.\n"
                "소스코드/config.json에는 비밀번호를 기록하지 않습니다.",
            )
        except CredentialStoreError as exc:
            messagebox.showerror("저장 실패", str(exc))


if __name__ == "__main__":
    app = BoardRepoApp()
    app.mainloop()
