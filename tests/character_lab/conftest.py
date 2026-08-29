#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Lab Slice 1 test bootstrap: make repo root + tools importable."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
