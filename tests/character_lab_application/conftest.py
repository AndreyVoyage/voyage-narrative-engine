#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared fixtures for Character Lab Application Service v1 tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.character_lab_application import CharacterLabApplicationConfig, CharacterLabApplicationService
from tests.character_canon_bridge.conftest import make_pending, make_status  # noqa: F401


def build_config(tmp_path: Path, *, with_canon: bool = True) -> CharacterLabApplicationConfig:
    canon_root = tmp_path / "character_canon" if with_canon else None
    return CharacterLabApplicationConfig(character_canon_root=canon_root)


@pytest.fixture
def canon_root(tmp_path: Path) -> Path:
    return tmp_path / "character_canon"


@pytest.fixture
def service(tmp_path: Path) -> CharacterLabApplicationService:
    return CharacterLabApplicationService(build_config(tmp_path))


@pytest.fixture
def offline_service() -> CharacterLabApplicationService:
    """A service with no Character Canon root configured at all."""
    return CharacterLabApplicationService(CharacterLabApplicationConfig(character_canon_root=None))
