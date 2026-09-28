# -*- coding: utf-8 -*-
"""Requirement Studio source launcher (no custom EXE)."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parent / "app" / "ALIRA.pyw"), run_name="__main__")
