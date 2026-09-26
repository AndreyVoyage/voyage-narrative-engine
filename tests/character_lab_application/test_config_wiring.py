"""Character Lab config wiring: authoring/release store root resolution."""

from __future__ import annotations

from pathlib import Path

from services.character_lab_application import (
    CharacterLabApplicationConfig,
    resolve_character_lab_roots,
)


def test_default_roots_resolve_to_repo_local_runs(tmp_path):
    authoring, release = resolve_character_lab_roots(tmp_path)
    assert authoring == tmp_path / "local_runs" / "character_authoring"
    assert release == tmp_path / "local_runs" / "character_releases"


def test_explicit_authoring_root_shifts_release_default():
    authoring = Path("/custom-authoring")
    resolved_authoring, resolved_release = resolve_character_lab_roots(
        Path("/unused/repo"), character_authoring_root=authoring
    )
    assert resolved_authoring == authoring
    assert resolved_release == authoring.parent / "character_releases"


def test_explicit_release_root_overrides_default():
    authoring = Path("/custom-authoring")
    release = Path("/custom-releases")
    resolved_authoring, resolved_release = resolve_character_lab_roots(
        Path("/unused/repo"),
        character_authoring_root=authoring,
        character_release_store_root=release,
    )
    assert resolved_authoring == authoring
    assert resolved_release == release


def test_config_carries_release_store_root():
    config = CharacterLabApplicationConfig(
        character_authoring_root=Path("/a"),
        character_release_store_root=Path("/r"),
    )
    assert config.character_release_store_root == Path("/r")
