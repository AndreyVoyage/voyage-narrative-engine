#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character-runtime test bootstrap: make the repo root importable."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
