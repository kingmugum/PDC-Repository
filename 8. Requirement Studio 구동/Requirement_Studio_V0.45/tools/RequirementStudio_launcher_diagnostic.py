from pathlib import Path
import subprocess, sys

ROOT = Path(__file__).resolve().parent.parent

print("Requirement Studio launcher diagnostic")
print("ROOT:", ROOT)
print("Current Python:", sys.executable)
print("Python version:", sys.version)
print("main.py:", (ROOT / "main.py").is_file())
print("requirements.txt:", (ROOT / "requirements.txt").is_file())
print(".venv python:", (ROOT / ".venv" / "Scripts" / "python.exe").is_file())
print(".venv pythonw:", (ROOT / ".venv" / "Scripts" / "pythonw.exe").is_file())

venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
if venv_python.is_file():
    result = subprocess.run(
        [str(venv_python), "-c", "import PySide6; print('PySide6', PySide6.__version__)"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print("PySide6 check rc:", result.returncode)
    print((result.stdout or result.stderr).strip())

input("Enter를 누르면 종료합니다...")
