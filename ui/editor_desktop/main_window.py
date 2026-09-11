"""Qt-native read-only editor shell over ``services.editor_application``."""

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
    QListView,
    QMainWindow,
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

_T = TypeVar("_T")
_ID_ROLE = int(Qt.ItemDataRole.UserRole)


class EditorMainWindow(QMainWindow):
    """Small read-only project browser backed exclusively by the app facade."""

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
        layout.addStretch(1)
        return panel

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

    def _on_scene_selected(self, current: QModelIndex, _previous: QModelIndex) -> None:
        scene_id = current.data(_ID_ROLE)
        if not isinstance(scene_id, str) or not scene_id:
            return
        try:
            workspace = self._service.get_scene_workspace(scene_id)
        except EditorApplicationError as exc:
            self._show_error(exc.code, exc.message)
            return
        except Exception:
            self._show_error(INTERNAL_ERROR, "Unable to open the selected scene.")
            return
        self._show_workspace(workspace)
        self.statusBar().showMessage(f"Opened {workspace.scene_id} read-only")

    def _show_workspace(self, workspace: EditorSceneWorkspace) -> None:
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
        self.workspace_hint.setText("Current scene state (read-only)")
        self.workspace_error.setVisible(False)
        self.workspace_form_container.setVisible(True)

    def _show_error(self, code: str, message: str) -> None:
        text = f"{code}: {message}"
        self.workspace_error.setText(text)
        self.workspace_error.setVisible(True)
        self.workspace_hint.setText("Select a scene to inspect its current state.")
        self.workspace_form_container.setVisible(False)
        self.statusBar().showMessage(text)
