#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared fixtures for Location Canon v0 tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.location_canon import load_location

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def yoga_hall(repo_root: Path):
    """The committed yoga_hall pilot LocationCanon."""
    return load_location(repo_root, "yoga_hall")


@pytest.fixture
def gym(repo_root: Path):
    """The committed gym LocationCanon."""
    return load_location(repo_root, "gym")
