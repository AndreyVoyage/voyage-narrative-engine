"""Bootstrap configuration constructs the real facade; no network required."""

from __future__ import annotations

from services.character_lab_application import CharacterLabApplicationService
from ui.character_lab.app import create_character_lab_config, create_character_lab_service


def test_default_config_has_no_canon_root_without_env_var(monkeypatch):
    monkeypatch.delenv("NARRATIVE_CHARACTER_CANON_ROOT", raising=False)
    config = create_character_lab_config()
    assert config.character_canon_root is None


def test_explicit_character_canon_root_is_supported(tmp_path):
    canon = tmp_path / "external-canon"
    config = create_character_lab_config(character_canon_root=canon)
    assert config.character_canon_root == canon.resolve()


def test_env_var_supplies_canon_root_when_not_explicit(tmp_path, monkeypatch):
    canon = tmp_path / "external-canon"
    monkeypatch.setenv("NARRATIVE_CHARACTER_CANON_ROOT", str(canon))
    config = create_character_lab_config()
    assert config.character_canon_root == canon.resolve()


def test_explicit_argument_wins_over_env_var(tmp_path, monkeypatch):
    env_canon = tmp_path / "env-canon"
    explicit_canon = tmp_path / "explicit-canon"
    monkeypatch.setenv("NARRATIVE_CHARACTER_CANON_ROOT", str(env_canon))
    config = create_character_lab_config(character_canon_root=explicit_canon)
    assert config.character_canon_root == explicit_canon.resolve()


def test_same_process_service_construction(monkeypatch):
    monkeypatch.delenv("NARRATIVE_CHARACTER_CANON_ROOT", raising=False)
    assert isinstance(create_character_lab_service(), CharacterLabApplicationService)
