"""Ensure the repo root is importable as `custom_components.venus300...`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
