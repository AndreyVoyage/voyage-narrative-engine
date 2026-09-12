"""Qt-native editor shell over ``services.editor_application``."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TypeVar

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QFont, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from services.editor_application import (
    INTERNAL_ERROR,
    EditorApplicationError,
    EditorApplicationService,
    EditorCharacterSummary,
    EditorLocationSummary,
    EditorSceneSummary,
    EditorSceneWorkspace,
)

from .draft_editing import LIFECYCLE_DRAFT, DraftEditSession, UnsavedDecision

_T = TypeVar("_T")
_ID_ROLE = int(Qt.ItemDataRole.UserRole)
_LIFECYCLE_ACCEPTED = "ACCEPTED"


class EditorMainWindow(QMainWindow):
    """Small project editor backed exclusively by the application facade."""

    def __init__(self, service: EditorApplicationService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self.setWindowTitle("NARRATIVE Scenario Editor")
        self.resize(1080, 680)
        self.setMinimumSize(780, 500)

        self.scene_model = QStandardItemModel(self)
        self.character_model = QStandardItemModel(self)
        self.location_model = QStandardItemModel(self)

        self.scene_view = self._make_list(self.scene_model, "Project scenes")
        self.character_view = self._make_list(self.character_model, "Project characters")
        self.location_view = self._make_list(self.location_model, "Project locations")

        self.character_empty_label = self._empty_label(
            "Character Canon is not configured or has no available characters."
        )
        self.location_empty_label = self._empty_label("No locations are available.")
        self.scene_empty_label = self._empty_label("No project scenes are available.")

        navigation = QTabWidget()
        navigation.setDocumentMode(True)
        navigation.addTab(
            self._browser_page(self.scene_view, self.scene_empty_label), "Scenes"
        )
        navigation.addTab(
            self._browser_page(self.character_view, self.character_empty_label),
            "Characters",
        )
        navigation.addTab(
            self._browser_page(self.location_view, self.location_empty_label),
            "Locations",
        )

        workspace = self._build_workspace()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(navigation)
        splitter.addWidget(workspace)
        splitter.setSizes([340, 740])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.addWidget(splitter)
        self.setCentralWidget(container)
        self.setStatusBar(QStatusBar(self))

        self.scene_view.selectionModel().currentChanged.connect(
            self._on_scene_selected
        )
        self._current_workspace: EditorSceneWorkspace | None = None
        self._draft_session: DraftEditSession | None = None
        self._restoring_selection = False
        self.entry_text_edits: dict[str, QPlainTextEdit] = {}
        self.reload_project()

    @staticmethod
    def _make_list(model: QStandardItemModel, accessible_name: str) -> QListView:
        view = QListView()
        view.setModel(model)
        view.setAccessibleName(accessible_name)
        view.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        view.setSelectionMode(QListView.SelectionMode.SingleSelection)
        view.setUniformItemSizes(True)
        return view

    @staticmethod
    def _empty_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setContentsMargins(12, 16, 12, 16)
        return label

    @staticmethod
    def _browser_page(view: QListView, empty_label: QLabel) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(view, 1)
        layout.addWidget(empty_label)
        return page

    def _build_workspace(self) -> QWidget:
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 22)

        heading = QLabel("Scene workspace")
        font = QFont(heading.font())
        font.setPointSize(font.pointSize() + 4)
        font.setBold(True)
        heading.setFont(font)
        layout.addWidget(heading)

        self.workspace_hint = QLabel("Select a scene to inspect its current state.")
        self.workspace_hint.setWordWrap(True)
        layout.addWidget(self.workspace_hint)

        self.workspace_error = QLabel()
        self.workspace_error.setWordWrap(True)
        self.workspace_error.setVisible(False)
        layout.addWidget(self.workspace_error)

        form_container = QWidget()
        self.workspace_form = QFormLayout(form_container)
        self.workspace_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.workspace_values: dict[str, QLabel] = {}
        fields = (
            ("scene_id", "Scene ID"),
            ("title", "Title"),
            ("version", "Latest version"),
            ("lifecycle", "Lifecycle"),
            ("acceptance", "Acceptance"),
            ("entries", "Entries"),
            ("manifest", "Project membership"),
        )
        for key, caption in fields:
            value = QLabel("—")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setWordWrap(True)
            self.workspace_values[key] = value
            self.workspace_form.addRow(caption, value)
        form_container.setVisible(False)
        self.workspace_form_container = form_container
        layout.addWidget(form_container)

        self.accepted_immutable_label = QLabel(
            "This scene version is ACCEPTED and immutable — editing is disabled."
        )
        self.accepted_immutable_label.setWordWrap(True)
        self.accepted_immutable_label.setVisible(False)
        layout.addWidget(self.accepted_immutable_label)

        self.start_revision_button = QPushButton("Start new revision")
        self.start_revision_button.setToolTip(
            "Keep the accepted version unchanged and create a new editable draft."
        )
        self.start_revision_button.setVisible(False)
        self.start_revision_button.setEnabled(False)
        self.start_revision_button.clicked.connect(self._start_new_revision)
        layout.addWidget(self.start_revision_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.draft_editor_container = self._build_draft_editor()
        self.draft_editor_container.setVisible(False)
        layout.addWidget(self.draft_editor_container)

        layout.addStretch(1)
        return panel

    def _build_draft_editor(self) -> QWidget:
        container = QWidget()
        editor_layout = QVBoxLayout(container)
        editor_layout.setContentsMargins(0, 12, 0, 0)

        header = QHBoxLayout()
        self.dirty_label = QLabel("")
        self.save_draft_button = QPushButton("Save draft")
        self.save_draft_button.setEnabled(False)
        self.save_draft_button.clicked.connect(self._save_current_draft)
        header.addWidget(self.dirty_label, 1)
        header.addWidget(self.save_draft_button)
        editor_layout.addLayout(header)

        fields = QFormLayout()
        fields.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.scene_title_edit = QLineEdit()
        self.location_edit = QLineEdit()
        self.content_rating_edit = QLineEdit()
        self.scene_title_edit.textChanged.connect(
            lambda value: self._on_scene_field_edited("scene_title", value)
        )
        self.location_edit.textChanged.connect(
            lambda value: self._on_scene_field_edited("location_id", value)
        )
        self.content_rating_edit.textChanged.connect(
            lambda value: self._on_scene_field_edited("content_rating", value)
        )
        fields.addRow("Scene title", self.scene_title_edit)
        fields.addRow("Location", self.location_edit)
        fields.addRow("Content rating", self.content_rating_edit)
        editor_layout.addLayout(fields)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        entries_host = QWidget()
        self._entries_layout = QVBoxLayout(entries_host)
        self._entries_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(entries_host)
        editor_layout.addWidget(scroll, 1)
        return container

    @staticmethod
    def _item(text: str, stable_id: str, tooltip: str) -> QStandardItem:
        item = QStandardItem(text)
        item.setEditable(False)
        item.setData(stable_id, _ID_ROLE)
        item.setToolTip(tooltip)
        return item

    def _read_collection(
        self,
        label: str,
        reader: Callable[[], tuple[_T, ...]],
    ) -> tuple[_T, ...]:
        try:
            return reader()
        except EditorApplicationError as exc:
            self._load_had_error = True
            self._show_error(exc.code, exc.message)
        except Exception:
            self._load_had_error = True
            self._show_error(INTERNAL_ERROR, f"Unable to load {label}.")
        return ()

    def reload_project(self) -> None:
        """Reload the three read-only collections through the facade."""

        self._load_had_error = False
        scenes = self._read_collection("scenes", self._service.list_scenes)
        characters = self._read_collection("characters", self._service.list_characters)
        locations = self._read_collection("locations", self._service.list_locations)
        self._set_scenes(scenes)
        self._set_characters(characters)
        self._set_locations(locations)
        if not self._load_had_error:
            self.statusBar().showMessage(
                f"Ready — {len(scenes)} scenes, {len(characters)} characters, "
                f"{len(locations)} locations"
            )

    def _set_scenes(self, scenes: Iterable[EditorSceneSummary]) -> None:
        self.scene_model.clear()
        for scene in scenes:
            title = scene.title or "Untitled scene"
            details = f"{scene.scene_id}  ·  v{scene.latest_version or '—'}  ·  {scene.lifecycle or 'Unavailable'}"
            self.scene_model.appendRow(
                self._item(f"{title}\n{details}", scene.scene_id, scene.scene_id)
            )
        has_items = self.scene_model.rowCount() > 0
        self.scene_view.setVisible(has_items)
        self.scene_empty_label.setVisible(not has_items)

    def _set_characters(self, characters: Iterable[EditorCharacterSummary]) -> None:
        self.character_model.clear()
        for character in characters:
            status = character.status or "Status unavailable"
            self.character_model.appendRow(
                self._item(
                    f"{character.label}\n{character.character_id}  ·  {status}",
                    character.character_id,
                    character.character_id,
                )
            )
        has_items = self.character_model.rowCount() > 0
        self.character_view.setVisible(has_items)
        self.character_empty_label.setVisible(not has_items)

    def _set_locations(self, locations: Iterable[EditorLocationSummary]) -> None:
        self.location_model.clear()
        for location in locations:
            tier = location.tier or "Tier unavailable"
            self.location_model.appendRow(
                self._item(
                    f"{location.label}\n{location.location_id}  ·  {tier}",
                    location.location_id,
                    location.location_id,
                )
            )
        has_items = self.location_model.rowCount() > 0
        self.location_view.setVisible(has_items)
        self.location_empty_label.setVisible(not has_items)

    def _on_scene_selected(self, current: QModelIndex, previous: QModelIndex) -> None:
        if self._restoring_selection:
            return
        scene_id = current.data(_ID_ROLE)
        if not isinstance(scene_id, str) or not scene_id:
            return
        if not self._confirm_leaving_dirty_session(scene_id, previous):
            return
        self._load_scene_workspace(scene_id)

    def _load_scene_workspace(
        self, scene_id: str, *, preserve_workspace_on_error: bool = False
    ) -> EditorSceneWorkspace | None:
        """Load and render one scene through the existing facade read path."""

        try:
            workspace = self._service.get_scene_workspace(scene_id)
        except EditorApplicationError as exc:
            if preserve_workspace_on_error:
                self._show_workspace_operation_error(exc.code, exc.message)
            else:
                self._show_error(exc.code, exc.message)
            return None
        except Exception:
            if preserve_workspace_on_error:
                self._show_workspace_operation_error(
                    INTERNAL_ERROR, "Unable to reload the scene workspace."
                )
            else:
                self._show_error(INTERNAL_ERROR, "Unable to open the selected scene.")
            return None
        self._show_workspace(workspace)
        if workspace.lifecycle == LIFECYCLE_DRAFT:
            self.statusBar().showMessage(
                f"Opened {workspace.scene_id} — draft editable"
            )
        else:
            self.statusBar().showMessage(f"Opened {workspace.scene_id} read-only")
        return workspace

    def _confirm_leaving_dirty_session(
        self, target_scene_id: str, previous: QModelIndex
    ) -> bool:
        """Unsaved-change protection before switching scenes.

        SAVE continues only when the save actually succeeds; DISCARD drops the
        buffer; CANCEL (or a failed SAVE) restores the previous selection.
        """
        session = self._draft_session
        if session is None or not session.is_dirty or session.scene_id == target_scene_id:
            return True
        decision = self._ask_unsaved_changes()
        if decision is UnsavedDecision.DISCARD:
            return True
        if decision is UnsavedDecision.SAVE and self._save_current_draft():
            return True
        self._restore_scene_selection(session.scene_id, previous)
        return False

    def _restore_scene_selection(self, scene_id: str, previous: QModelIndex) -> None:
        index = self._index_for_scene(scene_id)
        if not index.isValid():
            index = previous
        self._restoring_selection = True
        self.scene_view.setCurrentIndex(index)
        self._restoring_selection = False

    def _index_for_scene(self, scene_id: str) -> QModelIndex:
        for row in range(self.scene_model.rowCount()):
            index = self.scene_model.index(row, 0)
            if index.data(_ID_ROLE) == scene_id:
                return index
        return QModelIndex()

    def _show_workspace(self, workspace: EditorSceneWorkspace) -> None:
        self._current_workspace = workspace
        self._refresh_workspace_summary(workspace)
        self._refresh_scene_item(workspace)
        self.workspace_hint.setText("Current scene state (read-only)")
        self.workspace_error.setVisible(False)
        self.workspace_form_container.setVisible(True)
        if workspace.lifecycle == LIFECYCLE_DRAFT:
            self._draft_session = DraftEditSession(
                workspace.scene_id,
                workspace.latest_version,
                workspace.lifecycle,
                workspace.body,
            )
            self._rebuild_draft_editor()
            self.accepted_immutable_label.setVisible(False)
            self.start_revision_button.setVisible(False)
            self.start_revision_button.setEnabled(False)
            self.draft_editor_container.setVisible(True)
        else:
            self._draft_session = None
            self.draft_editor_container.setVisible(False)
            is_accepted = workspace.lifecycle == _LIFECYCLE_ACCEPTED
            self.accepted_immutable_label.setVisible(is_accepted)
            self.start_revision_button.setVisible(is_accepted)
            self.start_revision_button.setEnabled(
                is_accepted and workspace.can_fork_next_version
            )

    def _refresh_scene_item(self, workspace: EditorSceneWorkspace) -> None:
        index = self._index_for_scene(workspace.scene_id)
        item = self.scene_model.itemFromIndex(index) if index.isValid() else None
        if item is None:
            return
        body = workspace.body if isinstance(workspace.body, dict) else {}
        title = body.get("scene_title") or "Untitled scene"
        details = (
            f"{workspace.scene_id}  ·  v{workspace.latest_version}  ·  "
            f"{workspace.lifecycle}"
        )
        item.setText(f"{title}\n{details}")

    def _refresh_workspace_summary(self, workspace: EditorSceneWorkspace) -> None:
        body = workspace.body if isinstance(workspace.body, dict) else {}
        entries = body.get("entries")
        entry_count = len(entries) if isinstance(entries, list) else "Unavailable"
        acceptance = workspace.acceptance
        if isinstance(acceptance, dict):
            ass_id = acceptance.get("ass_id")
            acceptance_text = f"Accepted · {ass_id}" if ass_id else "Accepted"
        else:
            acceptance_text = "Not accepted"

        values = {
            "scene_id": workspace.scene_id,
            "title": body.get("scene_title") or "Untitled scene",
            "version": str(workspace.latest_version),
            "lifecycle": workspace.lifecycle,
            "acceptance": acceptance_text,
            "entries": str(entry_count),
            "manifest": "Included" if workspace.manifest_included else "Not included",
        }
        for key, value in values.items():
            self.workspace_values[key].setText(str(value))

    def _show_error(self, code: str, message: str) -> None:
        text = f"{code}: {message}"
        self.workspace_error.setText(text)
        self.workspace_error.setVisible(True)
        self.workspace_hint.setText("Select a scene to inspect its current state.")
        self.workspace_form_container.setVisible(False)
        self.draft_editor_container.setVisible(False)
        self.accepted_immutable_label.setVisible(False)
        self.start_revision_button.setVisible(False)
        self.start_revision_button.setEnabled(False)
        self._current_workspace = None
        self._draft_session = None
        self.statusBar().showMessage(text)

    def _show_workspace_operation_error(self, code: str, message: str) -> None:
        """Show a mutation error without discarding the visible workspace."""
        text = f"{code}: {message}"
        self.workspace_error.setText(text)
        self.workspace_error.setVisible(True)
        self.statusBar().showMessage(text)

    def _show_save_error(self, code: str, message: str) -> None:
        """Save-failure surface: error shown, buffer and dirty state preserved."""
        self._show_workspace_operation_error(code, message)

    def _rebuild_draft_editor(self) -> None:
        session = self._draft_session
        if session is None:
            return
        self.scene_title_edit.setText(session.scene_field("scene_title"))
        self.location_edit.setText(session.scene_field("location_id"))
        self.content_rating_edit.setText(session.scene_field("content_rating"))

        while self._entries_layout.count():
            item = self._entries_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.entry_text_edits = {}
        for entry in session.entries():
            entry_id = str(entry.get("entry_id") or "")
            if session.is_text_entry(entry):
                caption = QLabel(
                    f"Text entry '{entry_id}' · {entry.get('presentation') or '—'}"
                )
                self._entries_layout.addWidget(caption)
                edit = QPlainTextEdit()
                edit.setObjectName(f"entry_text_{entry_id}")
                edit.setPlainText(session.entry_text(entry_id))
                edit.textChanged.connect(
                    lambda entry_id=entry_id: self._on_entry_text_edited(entry_id)
                )
                self.entry_text_edits[entry_id] = edit
                self._entries_layout.addWidget(edit)
            else:
                label = QLabel(
                    f"Entry '{entry_id}' ({entry.get('kind') or 'unknown'}) — "
                    "not editable in this version; preserved on save."
                )
                label.setWordWrap(True)
                self._entries_layout.addWidget(label)
        self._entries_layout.addStretch(1)
        self._update_dirty_ui()

    def _on_scene_field_edited(self, key: str, value: str) -> None:
        if self._draft_session is None:
            return
        self._draft_session.set_scene_field(key, value)
        self._update_dirty_ui()

    def _on_entry_text_edited(self, entry_id: str) -> None:
        if self._draft_session is None:
            return
        edit = self.entry_text_edits.get(entry_id)
        if edit is None:
            return
        self._draft_session.set_entry_text(entry_id, edit.toPlainText())
        self._update_dirty_ui()

    def _update_dirty_ui(self) -> None:
        session = self._draft_session
        dirty = session is not None and session.editable and session.is_dirty
        self.dirty_label.setText("Unsaved changes" if dirty else "")
        self.save_draft_button.setEnabled(dirty)

    def _save_current_draft(self) -> bool:
        """Save through the facade only; False leaves the buffer dirty."""
        session = self._draft_session
        if session is None or not session.editable or not session.is_dirty:
            return False
        result = self._service.save_draft(
            session.scene_id, session.version, session.body_for_save()
        )
        if not result.ok:
            self._show_save_error(result.code, result.message)
            return False
        session.mark_saved()
        self.workspace_error.setVisible(False)
        try:
            self._refresh_workspace_summary(
                self._service.get_scene_workspace(session.scene_id)
            )
        except EditorApplicationError:
            pass
        self._update_dirty_ui()
        self.statusBar().showMessage(result.message)
        return True

    def _start_new_revision(self) -> bool:
        """Fork the exact loaded ACCEPTED version, then reload the same scene."""

        workspace = self._current_workspace
        if (
            workspace is None
            or workspace.lifecycle != _LIFECYCLE_ACCEPTED
            or not workspace.can_fork_next_version
        ):
            return False
        scene_id = workspace.scene_id
        source_version = workspace.latest_version
        if not self._confirm_start_new_revision(scene_id, source_version):
            return False
        try:
            result = self._service.fork_scene_version(scene_id, source_version)
        except EditorApplicationError as exc:
            self._show_workspace_operation_error(exc.code, exc.message)
            return False
        except Exception:
            self._show_workspace_operation_error(
                INTERNAL_ERROR, "Unable to start a new scene revision."
            )
            return False
        if not result.ok:
            self._show_workspace_operation_error(result.code, result.message)
            return False
        if self._load_scene_workspace(
            scene_id, preserve_workspace_on_error=True
        ) is None:
            return False
        self.statusBar().showMessage(result.message)
        return True

    def _confirm_start_new_revision(self, scene_id: str, version: int) -> bool:
        """Ask before creating the persistent next SceneVersion."""

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Start new revision")
        box.setText(f"Start a new revision of {scene_id} from version {version}?")
        box.setInformativeText(
            "The accepted version will remain unchanged. "
            "A new editable draft revision will be created."
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _ask_unsaved_changes(self) -> UnsavedDecision:
        """Built-in modal prompt; extracted so tests can stub the decision."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Unsaved changes")
        box.setText("The current draft has unsaved changes.")
        box.setInformativeText("Do you want to save them before continuing?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        result = box.exec()
        if result == QMessageBox.StandardButton.Save:
            return UnsavedDecision.SAVE
        if result == QMessageBox.StandardButton.Discard:
            return UnsavedDecision.DISCARD
        return UnsavedDecision.CANCEL

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        session = self._draft_session
        if session is not None and session.editable and session.is_dirty:
            decision = self._ask_unsaved_changes()
            if decision is UnsavedDecision.CANCEL:
                event.ignore()
                return
            if decision is UnsavedDecision.SAVE and not self._save_current_draft():
                event.ignore()
                return
        super().closeEvent(event)
