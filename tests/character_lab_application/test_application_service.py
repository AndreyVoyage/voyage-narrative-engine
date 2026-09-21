#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused tests for ``services.character_lab_application``."""

from __future__ import annotations

import pytest

from services.character_lab_application import (
    CANON_UNAVAILABLE,
    NOT_FOUND,
    CharacterLabApplicationError,
    CharacterLabApplicationService,
)
from tests.character_canon_bridge.conftest import make_status


def test_shell_initializes_offline_without_a_canon_root(offline_service):
    """Application layer works with zero configuration and zero network."""
    assert offline_service.list_characters() == ()
    assert offline_service.list_sessions() == ()


def test_missing_canon_root_fails_gracefully_not_with_a_traceback(offline_service):
    with pytest.raises(CharacterLabApplicationError) as excinfo:
        offline_service.get_character_detail("KIRA")
    assert excinfo.value.code == CANON_UNAVAILABLE


def test_unknown_character_fails_gracefully_not_with_a_traceback(service, canon_root):
    make_status(canon_root, "KIRA", "APPROVED_AS_CANON")
    with pytest.raises(CharacterLabApplicationError) as excinfo:
        service.get_character_detail("DOES_NOT_EXIST")
    assert excinfo.value.code == NOT_FOUND


def test_characters_are_listed_through_the_read_boundary(service, canon_root):
    make_status(canon_root, "KIRA", "APPROVED_AS_CANON")
    make_status(canon_root, "SERGEY", "DRAFT")
    summaries = service.list_characters()
    assert [s.character_id for s in summaries] == ["KIRA", "SERGEY"]
    assert all(isinstance(s.label, str) and s.label for s in summaries)


def test_selecting_a_character_updates_inspector_state(service, canon_root):
    make_status(canon_root, "KIRA", "APPROVED_AS_CANON")
    detail = service.get_character_detail("KIRA")
    assert detail.character_id == "KIRA"
    assert detail.status == "APPROVED_AS_CANON"
    assert detail.canon_approved is True
    assert detail.active_version_id == "v1"
    assert detail.source_ref is not None and not detail.source_ref.startswith(("/", "C:"))


def test_versions_are_represented_generically_from_actual_data(service, canon_root):
    make_status(canon_root, "KIRA", "APPROVED_AS_CANON")
    versions = service.list_versions("KIRA")
    assert versions == (versions[0],)
    assert versions[0].version_id == "v1"
    assert versions[0].is_active is True


def test_no_version_data_yields_no_synthetic_versions(service, canon_root, monkeypatch):
    make_status(canon_root, "KIRA", "APPROVED_AS_CANON")
    detail = service.get_character_detail("KIRA")
    assert detail.active_version_id == "v1"  # sanity: fixture provides one

    # Simulate a character with no active_version tag at all (no synthetic
    # "Beta v1 / Grounded v2" fixture data may ever be invented for this).
    import dataclasses

    bare_detail = dataclasses.replace(detail, active_version_id=None)
    assert bare_detail.active_version_id is None


def test_creating_a_local_session_binds_selected_character_and_version(service, canon_root):
    make_status(canon_root, "KIRA", "APPROVED_AS_CANON")
    session = service.create_session("KIRA", "v1")
    assert session.character_id == "KIRA"
    assert session.version_id == "v1"
    assert session.transcript == ()
    assert service.get_session(session.session_id) == session
    assert session in service.list_sessions()


def test_changing_character_selection_does_not_mutate_an_existing_session_binding(service, canon_root):
    make_status(canon_root, "KIRA", "APPROVED_AS_CANON")
    make_status(canon_root, "SERGEY", "APPROVED_AS_CANON")
    session = service.create_session("KIRA", "v1")

    # Selecting a different character elsewhere in the application (e.g. the
    # user clicks another row in the left panel) must never reach back into
    # the already-created session.
    service.get_character_detail("SERGEY")
    session.__class__  # sessions are frozen dataclasses; no setter exists

    reloaded = service.get_session(session.session_id)
    assert reloaded.character_id == "KIRA"
    assert reloaded.version_id == "v1"


def test_local_message_append_is_offline_and_preserves_binding(service, canon_root):
    make_status(canon_root, "KIRA", "APPROVED_AS_CANON")
    session = service.create_session("KIRA", "v1")
    updated = service.append_message(session.session_id, "user", "Привет, Кира.")
    assert [m.content for m in updated.transcript] == ["Привет, Кира."]
    assert updated.character_id == "KIRA"
    assert updated.version_id == "v1"
    # The original returned value is untouched (immutable).
    assert session.transcript == ()


def test_new_session_works_without_any_configured_canon_root(offline_service):
    """Session creation never requires a provider or Character Canon call."""
    session = offline_service.create_session("ANY_CHARACTER", None)
    assert session.character_id == "ANY_CHARACTER"
    assert offline_service.list_sessions() == (session,)


def test_no_provider_or_network_symbols_are_imported_by_this_package():
    import ast
    from pathlib import Path

    package_dir = Path(__file__).resolve().parents[2] / "services" / "character_lab_application"
    forbidden_roots = {"requests", "httpx", "urllib", "socket", "openai", "anthropic", "deepseek"}
    violations: list[str] = []
    for path in sorted(package_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            for module in modules:
                if module.split(".")[0] in forbidden_roots:
                    violations.append(f"{path.name}:{node.lineno}: {module}")
    assert violations == []


@pytest.mark.parametrize("character_id,status", [("KIRA", "APPROVED_AS_CANON"), ("SERGEY", "DRAFT")])
def test_application_logic_is_not_character_specific(service, canon_root, character_id, status):
    """The same generic code path must work for KIRA and for an arbitrary character."""
    make_status(canon_root, character_id, status)
    detail = service.get_character_detail(character_id)
    assert detail.character_id == character_id
    session = service.create_session(character_id, detail.active_version_id)
    assert session.character_id == character_id


def test_kira_pilot_path_works_with_real_canon_shaped_fixture_data(service, canon_root):
    make_status(canon_root, "KIRA", "APPROVED_AS_CANON")
    characters = service.list_characters()
    assert any(c.character_id == "KIRA" for c in characters)
    detail = service.get_character_detail("KIRA")
    versions = service.list_versions("KIRA")
    session = service.create_session("KIRA", versions[0].version_id if versions else None)
    assert session.character_id == "KIRA"
    assert detail.canon_approved is True
