from pathlib import Path
import subprocess
import sys

script = Path(__file__).with_name("alira_vision_probe.py")
subprocess.Popen([sys.executable, str(script), "--inspect", "--make-fixture"])
