#!/usr/bin/env python3
"""Convenience launcher for MediGraph AI.

Usage:
    python run.py ui              # Streamlit clinical workspace
    python run.py api             # FastAPI REST/FHIR API
    python run.py generate-data   # (re)build the bundled synthetic dataset
    python run.py export-web      # refresh the website demo data
"""
from __future__ import annotations

import subprocess
import sys


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ui"
    if cmd == "ui":
        return subprocess.call([sys.executable, "-m", "streamlit", "run", "ui/streamlit_app.py"])
    if cmd == "api":
        return subprocess.call([sys.executable, "-m", "uvicorn", "medigraph.api.main:app", "--reload"])
    if cmd == "generate-data":
        from medigraph.data.generator import main as gen
        gen()
        return 0
    if cmd == "export-web":
        from scripts.export_web_demo import main as exp
        exp()
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
