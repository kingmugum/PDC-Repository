from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
COMMON = ROOT / "function" / "common"
FUNCTION = HERE / "function"
sys.path.insert(0, str(COMMON))
sys.path.insert(0, str(FUNCTION))

from catalog import load_catalog
from work_lock import OperationLock
from boardrepo_tab import BoardRepoFrame

if __name__ == "__main__":
    app = tk.Tk()
    app.title("BoardRepo")
    app.geometry("1120x800")
    catalog = load_catalog(ROOT / "program_catalog.json")
    vars_ = {t["key"]: tk.BooleanVar(value=True) for t in catalog["targets"]}
    select = ttk.Frame(app, padding=8)
    select.pack(fill="x")
    for index, t in enumerate(catalog["targets"]):
        ttk.Checkbutton(
            select, text=t["ui_label"], variable=vars_[t["key"]]
        ).grid(row=index // 4, column=index % 4, sticky="w", padx=5, pady=2)
    BoardRepoFrame(app, ROOT, vars_, OperationLock()).pack(fill="both", expand=True)
    app.mainloop()
