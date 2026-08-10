from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
FUNCTION_DIR = ROOT / "function"

# Keep implementation modules out of the root while allowing normal imports.
sys.path.insert(0, str(FUNCTION_DIR))

from boardrepo import BoardRepoApp

if __name__ == "__main__":
    BoardRepoApp().mainloop()
