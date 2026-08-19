from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
COMMON = ROOT / "function" / "common"
sys.path.insert(0, str(COMMON))
sys.path.insert(0, str(HERE))

from catalog import load_catalog
from git_manager import GitManagerFrame
from work_lock import OperationLock

if __name__ == "__main__":
    app = tk.Tk()
    app.title("Git Manager")
    app.geometry("1180x780")
    catalog = load_catalog(ROOT / "program_catalog.json")
    vars_ = {t["key"]: tk.BooleanVar(value=True) for t in catalog["targets"]}
    select = ttk.Frame(app, padding=8)
    select.pack(fill="x")
    for t in catalog["targets"]:
        ttk.Checkbutton(select, text=t["ui_label"], variable=vars_[t["key"]]).pack(side="left", padx=5)
    GitManagerFrame(app, ROOT, vars_, OperationLock()).pack(fill="both", expand=True)
    app.mainloop()
