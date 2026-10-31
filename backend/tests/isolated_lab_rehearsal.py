"""Compatibility entry point for the guarded laboratory demo rehearsal."""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
from app.lab_demo import main


if __name__ == "__main__":
    raise SystemExit(main(["rehearse", *sys.argv[1:]]))
