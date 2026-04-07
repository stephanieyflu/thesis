"""Compatibility re-export: canonical definitions live in ``experiment_grid`` at the repository root."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from experiment_grid import *  # noqa: F403
