"""Pytest configuration for the tool_use test suite.

``test_memory_tool.py`` imports the module under test with ``from memory_tool
import MemoryToolHandler``. That module lives in ``tool_use/`` (the parent of
this directory), which isn't on ``sys.path`` during normal pytest collection
because ``tool_use`` has no top-level ``__init__.py``. Add it explicitly so the
tests import cleanly no matter what directory pytest is invoked from.
"""

from __future__ import annotations

import sys
from pathlib import Path

TOOL_USE_DIR = Path(__file__).parent.parent
if str(TOOL_USE_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_USE_DIR))
