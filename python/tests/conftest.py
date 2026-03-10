"""Pytest fixtures and configuration."""

import sys
from pathlib import Path

# Ensure python/ is on the path when running tests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
