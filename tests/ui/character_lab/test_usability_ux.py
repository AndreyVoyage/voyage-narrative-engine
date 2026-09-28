"""Character Lab usability slice UI tests: revision UX + testing binding + canon."""

from __future__ import annotations

from services.character_lab_application import (
    AUTHORING_PERSISTENCE_FAILED,
    IMMUTABLE_PERSISTENCE_FAILED,
    CharacterLabApplicationConfig,
    CharacterLabApplicationError,
    CharacterLabApplicationService,
)
from tests.character_dialogue._helpers import make_semantic
from ui.character_lab.main_window import (
    _AUTH_DATA_ROLE,
    _KIND_AUTH_REVISION,
    CharacterLabMainWindow,
)


def _semantic(name: str) -> dict:
    data = make_semantic()
    data["identity"]["display_name"] = name
    return data


def _make_window(tmp_path):
    service = CharacterLabApplicationService(
        CharacterLabApplicationConfig(character_authoring_root=tmp_path / "authoring"),
        dialogue_provider=lambda messages, system: "Ответ персонажа.",
    )
    return CharacterLabMainWindow(service), service


def _create_and_select(
    window,
    service,
    *,
    character_id="char_marina",
    version_id="v1",
    revision_id="r1",
    name="Марина",
):
    service.create_character(
        character_id=character_id,
        version_id=version_id,
        revision_id=revision_id,
        version_label="v1",
        semantic=_semantic(name),
    )
    window._reload_authoring_tree()
    window._select_authoring_revision(character_id, version_id, revision_id)


# -- Revision UX ----------------------------------------------------------


def test_save_as_new_revision_allocates_next(qapp, tmp_path):
    window, service = _make_window(tmp_path)
    _create_and_select(window, service, revision_id="r1", name="Лина")
    window.authoring_biography_edit.setPlainText("Обновлённая биография.")
    window.save_revision_button.click()

    assert window._authoring_revision_id == "r2"
    ids = {r.revision_id for r in service.list_authoring_revisions("char_marina", "v1")}
    assert ids == {"r1", "r2"}
    assert "Сохранена новая ревизия r2" in window.statusBar().currentMessage()


def test_save_does_not_overwrite_selected_revision(qapp, tmp_path):
    window, service = _make_window(tmp_path)
    _create_and_select(window, service, revision_id="r1", name="Лина")
    before = service.load_revision_semantic("char_marina", "v1", "r1").snapshot_hash

    window.authoring_biography_edit.setPlainText("Изменено.")
    window.save_revision_button.click()

    after = service.load_revision_semantic("char_marina", "v1", "r1").snapshot_hash
    assert before == after  # r1 immutable
    assert window._authoring_revision_id == "r2"


def test_save_honors_explicit_unused_custom_id(qapp, tmp_path):
    window, service = _make_window(tmp_path)
    _create_and_select(window, service, revision_id="r1", name="Лина")
    window.authoring_revision_id_edit.setText("my-custom")
    window.save_revision_button.click()
    assert window._authoring_revision_id == "my-custom"


def test_tree_exposes_new_revision(qapp, tmp_path):
    window, service = _make_window(tmp_path)
    _create_and_select(window, service, revision_id="r1", name="Лина")
    window.save_revision_button.click()
    assert window._authoring_revision_id == "r2"
    assert any(
        item.revision_id == "r2"
        for item in service.list_authoring_revisions("char_marina", "v1")
    )


def test_known_duplicate_error_mapped(qapp, tmp_path):
    window, service = _make_window(tmp_path)
    _create_and_select(window, service, revision_id="r1", name="Лина")
    window._show_save_revision_failure(
        CharacterLabApplicationError(
            IMMUTABLE_PERSISTENCE_FAILED, "revision 'r1' already exists"
        ),
        "r1",
    )
    message = window.statusBar().currentMessage()
    assert "IMMUTABLE_PERSISTENCE_FAILED" not in message
    assert "уже существует" in message


def test_unexpected_persistence_not_falsely_mapped(qapp, tmp_path):
    window, service = _make_window(tmp_path)
    _create_and_select(window, service, revision_id="r1", name="Лина")
    window._show_save_revision_failure(
        CharacterLabApplicationError(
            AUTHORING_PERSISTENCE_FAILED, "authoring persistence failed"
        ),
        "r2",
    )
    message = window.statusBar().currentMessage()
    assert "AUTHORING_PERSISTENCE_FAILED" in message
    assert "уже существует" not in message


# -- Testing binding UX ---------------------------------------------------


def test_binding_shows_selection_before_session(qapp, tmp_path):
    window, service = _make_window(tmp_path)
    _create_and_select(window, service, revision_id="r3", name="Лина Дуарте")
    text = window.testing_binding_label.text()
    assert "Лина Дуарте" in text
    assert "v1" in text
    assert "r3" in text


def test_binding_updates_with_selection_change(qapp, tmp_path):
    window, service = _make_window(tmp_path)
    _create_and_select(window, service, revision_id="r1", name="Лина")
    assert "r1" in window.testing_binding_label.text()

    service.save_character(
        character_id="char_marina",
        version_id="v1",
        revision_id="r2",
        semantic=_semantic("Лина"),
    )
    window._reload_authoring_tree()
    window._select_authoring_revision("char_marina", "v1", "r2")
    assert "r2" in window.testing_binding_label.text()


def test_new_session_matches_displayed_revision(qapp, tmp_path):
    window, service = _make_window(tmp_path)
    _create_and_select(window, service, revision_id="r3", name="Лина")
    assert "r3" in window.testing_binding_label.text()

    window.testing_new_session_button.click()
    assert window._testing_session_id is not None
    session = service.get_test_dialogue_session(window._testing_session_id)
    assert session.pin.revision_id == "r3"
    assert session.pin.version_id == "v1"


def test_existing_session_not_rebound_on_selection_change(qapp, tmp_path):
    window, service = _make_window(tmp_path)
    _create_and_select(window, service, revision_id="r1", name="Лина")
    window.testing_new_session_button.click()
    session_id = window._testing_session_id
    assert session_id is not None

    service.save_character(
        character_id="char_marina",
        version_id="v1",
        revision_id="r2",
        semantic=_semantic("Лина"),
    )
    window._reload_authoring_tree()
    window._select_authoring_revision("char_marina", "v1", "r2")

    session = service.get_test_dialogue_session(session_id)
    assert session.pin.revision_id == "r1"


def test_no_selection_binding_empty_with_guidance(qapp, tmp_path):
    window, service = _make_window(tmp_path)
    assert window.testing_binding_label.text() == ""
    assert "Авторинг" in window.testing_hint_label.text()


# -- Canon panel wording --------------------------------------------------


def test_canon_empty_label_does_not_imply_authoring_empty(qapp, tmp_path):
    window, service = _make_window(tmp_path)
    text = window.character_empty_label.text()
    assert "Канонические персонажи" in text
    assert "Авторинг" in text
    assert "Character Canon не настроен" not in text


# -- Review-fix coverage: actual tree selection / snapshot independence ------


def test_save_keeps_new_revision_as_actual_tree_current_item(qapp, tmp_path):
    """FIX 1 / TEST A: the freshly saved revision is the real tree currentItem."""
    window, service = _make_window(tmp_path)
    _create_and_select(window, service, revision_id="r1", name="Лина")

    window.authoring_biography_edit.setPlainText("Изменённая биография.")
    window.save_revision_button.click()

    # r2 exists in the backend (immutable store)
    ids = {r.revision_id for r in service.list_authoring_revisions("char_marina", "v1")}
    assert ids == {"r1", "r2"}

    # actual QTreeWidget currentItem corresponds to r2 (NOT via service list)
    current = window.authoring_tree.currentItem()
    assert current is not None
    data = current.data(0, _AUTH_DATA_ROLE)
    assert isinstance(data, dict)
    assert data.get("kind") == _KIND_AUTH_REVISION
    assert data.get("character_id") == "char_marina"
    assert data.get("version_id") == "v1"
    assert data.get("revision_id") == "r2"

    # internal coordinate agrees with the tree
    assert window._authoring_character_id == "char_marina"
    assert window._authoring_version_id == "v1"
    assert window._authoring_revision_id == "r2"

    # form revision_id displays r2
    assert window.authoring_revision_id_edit.text() == "r2"


def test_snapshot_hash_and_content_independent_across_revisions(qapp, tmp_path):
    """FIX 3 / TEST B: r1 stays immutable; r2 gets its own hash and content."""
    window, service = _make_window(tmp_path)
    _create_and_select(window, service, revision_id="r1", name="Лина")

    r1 = service.load_revision_semantic("char_marina", "v1", "r1")
    r1_hash = r1.snapshot_hash
    r1_bio = r1.semantic["biography"]
    assert r1_bio != "Изменённая биография."

    window.authoring_biography_edit.setPlainText("Изменённая биография.")
    window.save_revision_button.click()

    assert window._authoring_revision_id == "r2"

    r1_after = service.load_revision_semantic("char_marina", "v1", "r1")
    r2 = service.load_revision_semantic("char_marina", "v1", "r2")

    # r1 snapshot/hash and semantic content unchanged
    assert r1_after.snapshot_hash == r1_hash
    assert r1_after.semantic["biography"] == r1_bio

    # r2 has an independent snapshot/hash and contains the edit
    assert r2.snapshot_hash != r1_hash
    assert r2.semantic["biography"] == "Изменённая биография."


def test_full_session_binding_transition_active_vs_next(qapp, tmp_path):
    """FIX 3 / TEST C: active session stays r1 while next binding follows to r2."""
    window, service = _make_window(tmp_path)

    # 1-2. select Authoring r1; pending binding says r1
    _create_and_select(window, service, revision_id="r1", name="Лина")
    assert "r1" in window.testing_binding_label.text()

    # 3-4. create Test Dialogue session; actual pin == r1
    window.testing_new_session_button.click()
    first_session_id = window._testing_session_id
    assert first_session_id is not None
    first = service.get_test_dialogue_session(first_session_id)
    assert first.pin.revision_id == "r1"

    # 5. switch Authoring selection to r2
    service.save_character(
        character_id="char_marina",
        version_id="v1",
        revision_id="r2",
        semantic=_semantic("Лина"),
    )
    window._reload_authoring_tree()
    window._select_authoring_revision("char_marina", "v1", "r2")

    # 6-8. active session still r1 (header), pending NEXT binding says r2
    assert first.pin.revision_id == "r1"
    assert "r1" in window.testing_header_label.text()
    assert "r2" in window.testing_binding_label.text()
    assert "r1" not in window.testing_binding_label.text()

    # 9-10. create a new session -> pin r2
    window.testing_new_session_button.click()
    second_session_id = window._testing_session_id
    assert second_session_id is not None
    assert second_session_id != first_session_id
    second = service.get_test_dialogue_session(second_session_id)
    assert second.pin.revision_id == "r2"

    # 11. old session object remains pinned to r1
    old = service.get_test_dialogue_session(first_session_id)
    assert old.pin.revision_id == "r1"


def test_saved_revision_updates_pending_binding_without_reselection(qapp, tmp_path):
    """FIX 3 / TEST D: saving r2 -> r3 updates pending binding automatically."""
    window, service = _make_window(tmp_path)
    _create_and_select(window, service, revision_id="r2", name="Лина")
    assert "r2" in window.testing_binding_label.text()

    window.authoring_biography_edit.setPlainText("Новая биография.")
    window.save_revision_button.click()

    assert window._authoring_revision_id == "r3"
    assert "r3" in window.testing_binding_label.text()
    assert "r2" not in window.testing_binding_label.text()


# -- Version-aware selection regression --------------------------------------


def _create_multi_version(
    window,
    service,
    *,
    character_id="char_x",
    with_v2_r2=False,
):
    """Persist char_x with v1/r1, v1/r2, v2/r1 (and optionally v2/r2)."""
    service.create_character(
        character_id=character_id,
        version_id="v1",
        revision_id="r1",
        version_label="v1",
        semantic=_semantic("Лина"),
    )
    service.save_character(
        character_id=character_id,
        version_id="v1",
        revision_id="r2",
        semantic=_semantic("Лина"),
    )
    service.create_new_version(
        character_id=character_id,
        version_id="v2",
        revision_id="r1",
        version_label="v2",
        semantic=_semantic("Лина"),
    )
    if with_v2_r2:
        service.save_character(
            character_id=character_id,
            version_id="v2",
            revision_id="r2",
            semantic=_semantic("Лина"),
        )


def test_save_selects_exact_version_coordinate(qapp, tmp_path):
    """Multi-version repro: save from v2/r1 must select v2/r2, never v1/r2."""
    window, service = _make_window(tmp_path)
    _create_multi_version(window, service)
    window._reload_authoring_tree()
    window._select_authoring_revision("char_x", "v2", "r1")

    # sanity: correct starting coordinate selected
    assert window._authoring_character_id == "char_x"
    assert window._authoring_version_id == "v2"
    assert window._authoring_revision_id == "r1"

    window.authoring_biography_edit.setPlainText("Изменённая биография.")
    window.save_revision_button.click()

    # backend preserves v1/r2 and creates v2/r2 as independent coordinates
    v1_ids = {r.revision_id for r in service.list_authoring_revisions("char_x", "v1")}
    v2_ids = {r.revision_id for r in service.list_authoring_revisions("char_x", "v2")}
    assert "r2" in v1_ids
    assert "r2" in v2_ids

    # actual tree currentItem == char_x / v2 / r2 (NOT v1/r2)
    current = window.authoring_tree.currentItem()
    assert current is not None
    data = current.data(0, _AUTH_DATA_ROLE)
    assert data.get("character_id") == "char_x"
    assert data.get("version_id") == "v2"
    assert data.get("revision_id") == "r2"

    # internal coordinate agrees with the exact version
    assert window._authoring_character_id == "char_x"
    assert window._authoring_version_id == "v2"
    assert window._authoring_revision_id == "r2"

    # form revision id
    assert window.authoring_revision_id_edit.text() == "r2"

    # Testing pending binding includes version v2 + revision r2 (not v1)
    binding = window.testing_binding_label.text()
    assert "v2" in binding
    assert "r2" in binding
    assert "v1" not in binding


def test_new_session_pins_exact_version_coordinate(qapp, tmp_path):
    """Wrong version selection must not propagate into Test Dialogue pin."""
    window, service = _make_window(tmp_path)
    _create_multi_version(window, service)
    window._reload_authoring_tree()
    window._select_authoring_revision("char_x", "v2", "r1")

    window.authoring_biography_edit.setPlainText("Изменённая биография.")
    window.save_revision_button.click()

    assert window._authoring_version_id == "v2"
    assert window._authoring_revision_id == "r2"
    assert "v2" in window.testing_binding_label.text()

    window.testing_new_session_button.click()
    session_id = window._testing_session_id
    assert session_id is not None
    session = service.get_test_dialogue_session(session_id)
    assert session.pin.character_id == "char_x"
    assert session.pin.version_id == "v2"
    assert session.pin.revision_id == "r2"


def test_select_authoring_revision_requires_exact_version(qapp, tmp_path):
    """Direct helper: v1/r2 and v2/r2 both exist; request v2/r2 selects v2/r2."""
    window, service = _make_window(tmp_path)
    _create_multi_version(window, service, with_v2_r2=True)
    window._reload_authoring_tree()

    window._select_authoring_revision("char_x", "v2", "r2")

    current = window.authoring_tree.currentItem()
    assert current is not None
    data = current.data(0, _AUTH_DATA_ROLE)
    assert data.get("character_id") == "char_x"
    assert data.get("version_id") == "v2"
    assert data.get("revision_id") == "r2"


def test_select_authoring_revision_no_fallback_to_other_version(qapp, tmp_path):
    """Missing version must not silently select same revision_id in another version."""
    window, service = _make_window(tmp_path)
    # Only v1/r2 exists; v2 does not.
    service.create_character(
        character_id="char_x",
        version_id="v1",
        revision_id="r1",
        version_label="v1",
        semantic=_semantic("Лина"),
    )
    service.save_character(
        character_id="char_x",
        version_id="v1",
        revision_id="r2",
        semantic=_semantic("Лина"),
    )
    window._reload_authoring_tree()

    window._select_authoring_revision("char_x", "v2", "r2")

    # v1/r2 must NOT be selected as a substitute for the missing v2/r2
    assert window.authoring_tree.currentItem() is None

