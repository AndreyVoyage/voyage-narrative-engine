"""FIRST UI-native Character Lab authoring E2E: real backend, no mocks.

Through actual Qt/controller interaction in the Character Lab desktop shell:

    Create -> edit semantic data -> Save Revision -> Submit -> Approve ->
    Publish -> prove NOT current -> Set Current -> Export -> VCP extraction.

The backend underneath is the real chain: Character Authoring (S1),
LAB-L1 approval evidence, LAB-L2 compile, LAB-L3 VCP build, LAB-L4 release
store, and LAB-L5 facade. Nothing in the principal happy path is mocked.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

# VCP operational dependency wiring is deferred (OD-LAB-VCP-DEPENDENCY-WIRING-01);
# without the distribution the module is skipped instead of failing collection.
pytest.importorskip("voyage_character_platform")

from services.character_authoring import CharacterAuthoringStore, LifecycleState
from services.character_lab_application import (
    CharacterLabApplicationConfig,
    CharacterLabApplicationService,
)
from services.character_publication.release_store import CharacterReleaseStore
from ui.character_lab.main_window import CharacterLabMainWindow
from voyage_character_platform.vchar import extract_vchar_v1

CHARACTER_ID = "ui-native-control"
VERSION_ID = "ui-native-v1"
REV1 = "ui-native-r1"
REV2 = "ui-native-r2"
RELEASE_ID = "ui-native-release-1"
DISPLAY_NAME = "UI Native Control"
DECIDED_BY = "test-owner"


def _make_lab(tmp_path: Path):
    authoring_root = tmp_path / "authoring"
    release_root = tmp_path / "releases"
    config = CharacterLabApplicationConfig(
        character_authoring_root=authoring_root,
        character_release_store_root=release_root,
    )
    service = CharacterLabApplicationService(config)
    authoring = CharacterAuthoringStore(authoring_root)
    releases = CharacterReleaseStore(release_root)
    return service, authoring, releases, config


def _fill_create_form(window: CharacterLabMainWindow) -> None:
    window.authoring_character_id_edit.setText(CHARACTER_ID)
    window.authoring_version_id_edit.setText(VERSION_ID)
    window.authoring_revision_id_edit.setText(REV1)
    window.authoring_version_label_edit.setText("UI Native v1")
    window.authoring_display_name_edit.setText(DISPLAY_NAME)
    window.authoring_biography_edit.setPlainText("Synthetic control biography.")
    window.authoring_personality_edit.setText("steady")
    window.authoring_behavioral_edit.setText("methodical")
    window.authoring_emotional_edit.setText("calm")
    window.authoring_goals_edit.setText("prove the UI pipeline")
    window.authoring_speech_style_edit.setText("plain")
    window.authoring_register_edit.setText("")
    window.authoring_relational_edit.setText("cooperative")
    window.authoring_attachment_edit.setText("secure")
    window.authoring_appearance_edit.setText("plain test figure")
    window.authoring_boundaries_edit.setText("respects refusal")


def _top_level_texts(window: CharacterLabMainWindow) -> list[str]:
    return [
        window.authoring_tree.topLevelItem(i).text(0)
        for i in range(window.authoring_tree.topLevelItemCount())
    ]


def _drive_through_publish(window: CharacterLabMainWindow, tmp_path: Path):
    _fill_create_form(window)
    window.create_character_button.click()
    assert window._authoring_character_id == CHARACTER_ID

    window.authoring_revision_id_edit.setText(REV2)
    window.authoring_biography_edit.setPlainText("Synthetic control biography, edited.")
    window.save_revision_button.click()
    assert window._authoring_revision_id == REV2

    window.submit_button.click()
    window.authoring_decided_by_edit.setText(DECIDED_BY)
    window.approve_button.click()

    window.authoring_release_id_edit.setText(RELEASE_ID)
    window.authoring_display_name_publish_edit.setText(DISPLAY_NAME)
    window.publish_button.click()
    assert window._authoring_release_id == RELEASE_ID


def test_first_ui_native_character_end_to_end(qapp, tmp_path):
    service, authoring, releases, config = _make_lab(tmp_path)
    # Proof M: everything is written under the pytest temp root, never the repo.
    assert str(tmp_path) in str(authoring.root)
    assert str(tmp_path) in str(releases.root)

    window = CharacterLabMainWindow(service)
    window.show()
    _drive_through_publish(window, tmp_path)

    # A. character appears in the UI authoring tree.
    assert CHARACTER_ID in _top_level_texts(window)

    # B. actual revisions exist in the real Authoring store.
    first = authoring.load_revision(CHARACTER_ID, VERSION_ID, REV1)
    second = authoring.load_revision(CHARACTER_ID, VERSION_ID, REV2)

    # C. immutable previous revision unchanged after Save.
    assert first.snapshot_hash != second.snapshot_hash
    assert (
        authoring.load_revision(CHARACTER_ID, VERSION_ID, REV1).snapshot_hash
        == first.snapshot_hash
    )

    # D/E. real LAB-L1 approval evidence persisted; APPROVED_AS_CANON reached.
    pointer = authoring.read_version_pointer(CHARACTER_ID, VERSION_ID)
    assert pointer.lifecycle_state is LifecycleState.APPROVED_AS_CANON
    assert pointer.selected_revision_id == REV2
    evidence = authoring.load_approval_evidence(CHARACTER_ID, VERSION_ID, REV2)
    assert evidence.decision == "HUMAN_APPROVED"
    assert evidence.decided_by == DECIDED_BY
    assert evidence.snapshot_hash == second.snapshot_hash

    # F. real LAB-L5 publication created a durable release.
    assert RELEASE_ID in releases.list_release_ids(CHARACTER_ID)

    # G. immediately after Publish: canonical current is absent.
    assert releases.get_canonical_current(CHARACTER_ID) is None

    # H. explicit Set Current creates the current designation.
    window.set_current_button.click()
    current = releases.get_canonical_current(CHARACTER_ID)
    assert current is not None
    assert current.release_id == RELEASE_ID

    # I. Set Current caused NO package rebuild (still exactly one artifact).
    artifacts = list((releases.root / "artifacts").iterdir())
    assert len(artifacts) == 1

    # J/K. export comes from the durable store; SHA/length match the release.
    export_path = tmp_path / "exported" / "control.vchar"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    window.authoring_export_path_edit.setText(str(export_path))
    window.export_button.click()
    assert export_path.exists()
    record = releases.load_release_record(CHARACTER_ID, RELEASE_ID)
    assert export_path.stat().st_size == record.byte_length
    exported_sha = hashlib.sha256(export_path.read_bytes()).hexdigest()
    assert exported_sha == record.artifact_sha256

    # L. VCP extraction returns exact characterId/releaseId/packageHash.
    verified = extract_vchar_v1(export_path, tmp_path / "vcp-extract")
    assert verified.metadata.character_id == CHARACTER_ID
    assert verified.metadata.release_id == RELEASE_ID
    assert verified.package_hash == record.package_hash


def test_reopen_persistence_shows_character_release_and_current(qapp, tmp_path):
    service, authoring, releases, config = _make_lab(tmp_path)
    window = CharacterLabMainWindow(service)
    window.show()
    _drive_through_publish(window, tmp_path)
    window.set_current_button.click()
    assert releases.get_canonical_current(CHARACTER_ID) is not None

    # Recreate the application window with the same temp roots (same config).
    window2 = CharacterLabMainWindow(CharacterLabApplicationService(config))
    window2.show()

    # Character still visible in the UI authoring tree.
    assert CHARACTER_ID in _top_level_texts(window2)

    # Approved lifecycle visible through the read boundary.
    pointer = window2._service.read_version_lifecycle(CHARACTER_ID, VERSION_ID)
    assert pointer.lifecycle_state == "APPROVED_AS_CANON"

    # Release visible; canonical current visible.
    releases_list = window2._service.list_published_releases(CHARACTER_ID)
    assert [item.release_id for item in releases_list] == [RELEASE_ID]
    current = window2._service.read_canonical_current(CHARACTER_ID)
    assert current is not None
    assert current.release_id == RELEASE_ID
