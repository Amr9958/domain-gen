"""Backend test configuration."""

from __future__ import annotations

import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = BACKEND_ROOT / "src"

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
