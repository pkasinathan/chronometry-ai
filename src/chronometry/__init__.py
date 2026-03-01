"""Chronometry — privacy-first activity tracker with local AI-powered annotation."""

from __future__ import annotations

import os
from pathlib import Path

__version__ = "1.0.6"

CHRONOMETRY_HOME = Path(os.environ.get("CHRONOMETRY_HOME", "~/.chronometry")).expanduser()
