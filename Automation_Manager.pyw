from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk

ROOT = Path(__file__).resolve().parent
COMMON_DIR = ROOT / "function" / "common"
GIT_DIR = ROOT / "5. Git Manager" / "current"
BOARD_FUNCTION_DIR = ROOT / "6. BoardRepo" / "current" / "function"

for path in [COMMON_DIR, GIT_DIR, BOARD_FUNCTION_DIR]:
    sys.path.insert(0, str(path))

from catalog import load_catalog
from work_lock import OperationLock
from git_manager import GitManagerFrame
from boardrepo_tab import BoardRepoFrame

APP_RELEASE = "260821_1"


class AutomationManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Automation Manager {APP_RELEASE}")
        self.geometry("1220x860")
        self.minsize(1040, 720)
        self.catalog = load_catalog(ROOT / "program_catalog.json")
        self.operation_lock = OperationLock()
        self.target_vars = {
            t["key"]: tk.BooleanVar(value=False)
            for t in self.catalog["targets"]
        }
        self._build_ui()

    def _build_ui(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x")
        ttk.Label(header, text="Automation Manager", font=("Segoe UI", 20, "bold")).pack(side="left")
        ttk.Label(
            header,
            text=f"Release {APP_RELEASE} · Git Manager + BoardRepo 통합 실행기",
        ).pack(side="left", padx=(12, 0), pady=(7, 0))

        ttk.Label(
            root,
            text=(
                "통합 GUI만 공유하며 Git Manager와 BoardRepo 엔진은 분리되어 있습니다. "
                "Automation Manager 자체는 7번째 관리 대상이 아닙니다."
            ),
        ).pack(anchor="w", pady=(4, 8))

        select = ttk.LabelFrame(root, text="공통 관리 대상 (Git Manager / BoardRepo 탭 공용)", padding=10)
        select.pack(fill="x")

        checks = ttk.Frame(select)
        checks.pack(fill="x")
        for t in self.catalog["targets"]:
            ttk.Checkbutton(
                checks,
                text=t["ui_label"],
                variable=self.target_vars[t["key"]],
            ).pack(side="left", padx=(0, 15))

        buttons = ttk.Frame(select)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="전체 선택", command=self.select_all).pack(side="left")
        ttk.Button(buttons, text="전체 해제", command=self.clear_all).pack(side="left", padx=(6, 0))
        ttk.Label(
            buttons,
            text="3. WeeklyReport → board/377 · 4. Ext → board/376 · 5. Git Manager → board/392 · 6. BoardRepo → board/393",
        ).pack(side="left", padx=(18, 0))

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, pady=(10, 0))

        git_tab = GitManagerFrame(
            notebook,
            workspace_root=ROOT,
            target_vars=self.target_vars,
            operation_lock=self.operation_lock,
        )
        board_tab = BoardRepoFrame(
            notebook,
            workspace_root=ROOT,
            target_vars=self.target_vars,
            operation_lock=self.operation_lock,
        )
        notebook.add(git_tab, text="Git Manager")
        notebook.add(board_tab, text="BoardRepo")

    def select_all(self):
        for var in self.target_vars.values():
            var.set(True)

    def clear_all(self):
        for var in self.target_vars.values():
            var.set(False)


if __name__ == "__main__":
    AutomationManager().mainloop()
