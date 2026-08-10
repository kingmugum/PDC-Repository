from pathlib import Path
import os
import runpy
import sys
import tkinter as tk
from tkinter import messagebox

ROOT = Path(__file__).resolve().parent
CURRENT = ROOT / "6. boardrepo" / "current"
ENTRY = CURRENT / "BoardRepo.pyw"

if not ENTRY.exists():
    app = tk.Tk()
    app.withdraw()
    messagebox.showerror(
        "BoardRepo",
        "BoardRepo 실행 파일을 찾을 수 없습니다.\n\n"
        f"예상 위치:\n{ENTRY}",
    )
    app.destroy()
    raise SystemExit(1)

os.chdir(CURRENT)
sys.path.insert(0, str(CURRENT))
runpy.run_path(str(ENTRY), run_name="__main__")
