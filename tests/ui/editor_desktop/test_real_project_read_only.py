"""Read-only offscreen proof against the tracked NARRATIVE project authority."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PySide6.QtCore import Qt

from ui.editor_desktop.app import create_editor_service
from ui.editor_desktop.main_window import EditorMainWindow

EXPECTED_SCENES = (
    "sc_kira_hidden_problem_001",
    "sc_kira_sergey_message_again_001",
    "sc_kira_yoga_hall_warmup_001",
)


class ReadOnlyFacadeGuard:
    """Expose only reads; any accidental mutation call fails the proof."""

    def __init__(self, service):
        self.service = service
        self.calls: list[str] = []

    def _read(self, name, *args):
        self.calls.append(name)
        return getattr(self.service, name)(*args)

    def list_scenes(self):
        return self._read("list_scenes")

    def list_characters(self):
        return self._read("list_characters")

    def list_locations(self):
        return self._read("list_locations")

    def get_scene_workspace(self, scene_id):
        return self._read("get_scene_workspace", scene_id)

    def create_scene(self, *args):
        raise AssertionError("UI called create_scene")

    def save_draft(self, *args):
        raise AssertionError("UI called save_draft")

    def fork_scene_version(self, *args):
        raise AssertionError("UI called fork_scene_version")

    def accept_scene(self, *args):
        raise AssertionError("UI called accept_scene")


def _authority_guard_values(repo_root: Path) -> tuple[str, ...]:
    files_and_fields = (
        (
            repo_root / "authoring/accepted_ordered_ass/scenes/"
            "onrv623jojqv66lpm5qv62dbnrwf653bojwxk4c7gaydc/versions/1.json",
            "content_hash",
        ),
        (
            repo_root / "authoring/scene_drafts/sc_kira_hidden_problem_001/versions/1.json",
            "content_hash",
        ),
        (
            repo_root / "authoring/accepted_ordered_ass/scenes/"
            "onrv623jojqv62djmrsgk3s7obzg6ytmmvwv6mbqge/versions/1.json",
            "content_hash",
        ),
        (
            repo_root / "authoring/scene_drafts/sc_kira_sergey_message_again_001/versions/1.json",
            "content_hash",
        ),
        (
            repo_root / "authoring/accepted_ordered_ass/scenes/"
            "onrv623jojqv643fojtwk6k7nvsxg43bm5sv6ylhmfuw4xzqgayq/versions/1.json",
            "content_hash",
        ),
    )
    values = [json.loads(path.read_text(encoding="utf-8"))[field] for path, field in files_and_fields]
    canonical = repo_root / "novel" / "game" / "ordered_ass_generated.rpy"
    values.append(hashlib.sha256(canonical.read_bytes()).hexdigest())
    return tuple(values)


def test_real_project_window_is_strictly_read_only(qapp):
    repo_root = Path(__file__).resolve().parents[3]
    expected_guards = (
        "c27491900abf097a3113e6200b1d6335ea39b3b08818c5bc1533bc4784bd40e5",
        "f84b8c5ef90252658e48d067bd822cce645d6cb2642b01a9a3c926c3937f0a89",
        "df8bc151c385a070d3b2a6636eed342b9d51e837469aebaa671d0090657f7e70",
        "2871fef786e827568f5c4cdf6b2adf43f02a8cbfad09547051cd2f6869607e7d",
        "29175b557598a696db562c8154a2bb52eaee9df71929c2dac5fed0456dcffbd9",
        "f888a579c3b948ac98588927f25a5a6bb5a0db2fe20163fd39926384b60ed236",
    )
    before = _authority_guard_values(repo_root)
    assert before == expected_guards

    guarded = ReadOnlyFacadeGuard(create_editor_service(repo_root))
    window = EditorMainWindow(guarded)
    window.show()
    try:
        qapp.processEvents()
        scene_ids = tuple(
            window.scene_model.index(row, 0).data(int(Qt.ItemDataRole.UserRole))
            for row in range(window.scene_model.rowCount())
        )
        location_ids = tuple(
            window.location_model.index(row, 0).data(int(Qt.ItemDataRole.UserRole))
            for row in range(window.location_model.rowCount())
        )
        assert window.isVisible()
        assert scene_ids == EXPECTED_SCENES
        assert window.scene_model.rowCount() == 3
        assert location_ids == ("gym", "yoga_hall")
        assert window.character_model.rowCount() == 0
        assert not window.character_empty_label.isHidden()

        index = window.scene_model.index(0, 0)
        window.scene_view.setCurrentIndex(index)
        qapp.processEvents()
        assert window.workspace_values["scene_id"].text() == EXPECTED_SCENES[0]
        assert window.workspace_values["lifecycle"].text() == "ACCEPTED"
        assert window.workspace_values["acceptance"].text().startswith("Accepted")
        assert guarded.calls == [
            "list_scenes",
            "list_characters",
            "list_locations",
            "get_scene_workspace",
        ]
    finally:
        window.close()
        qapp.processEvents()

    assert _authority_guard_values(repo_root) == before
