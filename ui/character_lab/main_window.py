"""Qt-native Character Lab shell over ``services.character_lab_application``.

An application/editor shell for testing, inspecting, and (in a later product
stage) authoring AI characters and their versions -- not an in-game Ren'Py
screen. This foundation slice is fully offline: no provider/network call is
made anywhere in this module.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QFont, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from services.character_lab_application import (
    CharacterLabApplicationError,
    CharacterLabApplicationService,
    LabSession,
)

_ID_ROLE = int(Qt.ItemDataRole.UserRole)
_KIND_ROLE = _ID_ROLE + 1
_VERSION_ROLE = _ID_ROLE + 2
_KIND_CHARACTER = "character"
_KIND_VERSION = "version"
_KIND_SESSION = "session"


class CharacterLabMainWindow(QMainWindow):
    """Character Lab application shell: characters/sessions, dialogue, inspector."""

    def __init__(
        self, service: CharacterLabApplicationService, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._service = service
        self.setWindowTitle("NARRATIVE Character Lab")
        self.resize(1180, 720)
        self.setMinimumSize(860, 540)

        self._selected_character_id: Optional[str] = None
        self._selected_version_id: Optional[str] = None
        self._current_session_id: Optional[str] = None

        left = self._build_left_panel()
        center = self._build_center_panel()
        right = self._build_right_panel()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(center)
        splitter.addWidget(right)
        splitter.setSizes([300, 580, 300])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.addWidget(splitter)
        self.setCentralWidget(container)
        self.setStatusBar(QStatusBar(self))

        self.reload_characters()
        self._render_no_session()

    # -- Left panel: Персонажи / Сессии ---------------------------------

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)

        layout.addWidget(self._section_heading("Персонажи"))
        self.character_model = QStandardItemModel(self)
        self.character_view = QTreeView()
        self.character_view.setModel(self.character_model)
        self.character_view.setHeaderHidden(True)
        self.character_view.setAccessibleName("Персонажи")
        self.character_view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.character_view.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        layout.addWidget(self.character_view, 2)

        self.character_empty_label = self._empty_label(
            "Character Canon не настроен или персонажи недоступны."
        )
        layout.addWidget(self.character_empty_label)

        layout.addWidget(self._section_heading("Сессии"))
        self.new_session_button = QPushButton("+ Новая сессия")
        self.new_session_button.clicked.connect(self._on_new_session_clicked)
        layout.addWidget(self.new_session_button)

        self.session_model = QStandardItemModel(self)
        self.session_view = QListView()
        self.session_view.setModel(self.session_model)
        self.session_view.setAccessibleName("Сессии")
        self.session_view.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self.session_view.setSelectionMode(QListView.SelectionMode.SingleSelection)
        layout.addWidget(self.session_view, 1)

        self.character_view.selectionModel().currentChanged.connect(
            self._on_character_tree_selection_changed
        )
        self.session_view.selectionModel().currentChanged.connect(
            self._on_session_selection_changed
        )
        return panel

    # -- Center panel: dialogue workspace --------------------------------

    def _build_center_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 18)

        self.session_header_label = QLabel()
        font = QFont(self.session_header_label.font())
        font.setBold(True)
        font.setPointSize(font.pointSize() + 2)
        self.session_header_label.setFont(font)
        self.session_header_label.setWordWrap(True)
        layout.addWidget(self.session_header_label)

        self.transcript_view = QListWidget()
        self.transcript_view.setAccessibleName("Транскрипт")
        layout.addWidget(self.transcript_view, 1)

        composer_row = QHBoxLayout()
        self.composer_edit = QLineEdit()
        self.composer_edit.setPlaceholderText("Введите сообщение...")
        self.composer_edit.returnPressed.connect(self._on_send_clicked)
        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self._on_send_clicked)
        composer_row.addWidget(self.composer_edit, 1)
        composer_row.addWidget(self.send_button)
        layout.addLayout(composer_row)

        return panel

    # -- Right panel: inspector ------------------------------------------

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self._section_heading("Инспектор персонажа"))

        self.inspector_empty_label = self._empty_label("Выберите персонажа, чтобы увидеть данные.")
        layout.addWidget(self.inspector_empty_label)

        self.inspector_error_label = QLabel()
        self.inspector_error_label.setWordWrap(True)
        self.inspector_error_label.setVisible(False)
        layout.addWidget(self.inspector_error_label)

        form_container = QWidget()
        self.inspector_form = QFormLayout(form_container)
        self.inspector_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.inspector_values: dict[str, QLabel] = {}
        fields = (
            ("character_id", "ID персонажа"),
            ("label", "Отображаемое имя"),
            ("version", "Версия"),
            ("status", "Статус канона"),
            ("approved", "Утверждён как канон"),
            ("source", "Источник"),
            ("session", "Текущая сессия"),
        )
        for key, caption in fields:
            value = QLabel("—")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setWordWrap(True)
            self.inspector_values[key] = value
            self.inspector_form.addRow(caption, value)
        form_container.setVisible(False)
        self.inspector_form_container = form_container
        layout.addWidget(form_container)
        layout.addStretch(1)
        return panel

    # -- Shared small builders --------------------------------------------

    @staticmethod
    def _section_heading(text: str) -> QLabel:
        label = QLabel(text)
        font = QFont(label.font())
        font.setBold(True)
        label.setFont(font)
        return label

    @staticmethod
    def _empty_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setContentsMargins(8, 12, 8, 12)
        return label

    @staticmethod
    def _item(text: str, stable_id: str, kind: str, *, version_id: str | None = None) -> QStandardItem:
        item = QStandardItem(text)
        item.setEditable(False)
        item.setData(stable_id, _ID_ROLE)
        item.setData(kind, _KIND_ROLE)
        item.setData(version_id, _VERSION_ROLE)
        return item

    # -- Character tree ----------------------------------------------------

    def reload_characters(self) -> None:
        """Reload the character/version tree through the application facade."""
        try:
            characters = self._service.list_characters()
        except Exception:
            characters = ()
            self.statusBar().showMessage("Не удалось загрузить список персонажей.")

        self.character_model.clear()
        for character in characters:
            status_text = character.status or "статус недоступен"
            character_item = self._item(
                f"{character.label}\n{character.character_id} · {status_text}",
                character.character_id,
                _KIND_CHARACTER,
            )
            try:
                versions = self._service.list_versions(character.character_id)
            except CharacterLabApplicationError:
                versions = ()
            for version in versions:
                marker = "текущая" if version.is_active else ""
                version_item = self._item(
                    f"Версия {version.version_id} {marker}".rstrip(),
                    character.character_id,
                    _KIND_VERSION,
                    version_id=version.version_id,
                )
                character_item.appendRow(version_item)
            self.character_model.appendRow(character_item)

        has_items = self.character_model.rowCount() > 0
        self.character_view.setVisible(has_items)
        self.character_empty_label.setVisible(not has_items)
        if has_items:
            self.character_view.expandAll()
        self.statusBar().showMessage(f"Готово — персонажей: {len(characters)}")

    def _on_character_tree_selection_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        if not current.isValid():
            return
        character_id = current.data(_ID_ROLE)
        kind = current.data(_KIND_ROLE)
        if not isinstance(character_id, str) or not character_id:
            return
        version_id = current.data(_VERSION_ROLE) if kind == _KIND_VERSION else None
        self._selected_character_id = character_id
        self._selected_version_id = version_id
        self._update_inspector(character_id)

    def _update_inspector(self, character_id: str) -> None:
        try:
            detail = self._service.get_character_detail(character_id)
        except CharacterLabApplicationError as exc:
            self.inspector_error_label.setText(f"{exc.code}: {exc.message}")
            self.inspector_error_label.setVisible(True)
            self.inspector_form_container.setVisible(False)
            self.inspector_empty_label.setVisible(False)
            return
        self.inspector_error_label.setVisible(False)
        self.inspector_empty_label.setVisible(False)
        self.inspector_form_container.setVisible(True)
        values = {
            "character_id": detail.character_id,
            "label": detail.label,
            "version": detail.active_version_id or "недоступна",
            "status": detail.status or "недоступен",
            "approved": "Да" if detail.canon_approved else "Нет",
            "source": detail.source_ref or "недоступен",
            "session": self._session_binding_text(),
        }
        for key, value in values.items():
            self.inspector_values[key].setText(str(value))

    def _session_binding_text(self) -> str:
        if self._current_session_id is None:
            return "—"
        try:
            session = self._service.get_session(self._current_session_id)
        except CharacterLabApplicationError:
            return "—"
        return f"{session.session_id[:8]} → {session.character_id} · {session.version_id or '—'}"

    # -- Sessions -----------------------------------------------------------

    def _on_new_session_clicked(self) -> None:
        if self._selected_character_id is None:
            self.statusBar().showMessage("Сначала выберите персонажа.")
            return
        session = self._service.create_session(self._selected_character_id, self._selected_version_id)
        item = self._item(
            self._session_label(session),
            session.session_id,
            _KIND_SESSION,
        )
        self.session_model.appendRow(item)
        index = self.session_model.indexFromItem(item)
        self.session_view.setCurrentIndex(index)
        self.statusBar().showMessage(f"Создана новая сессия: {session.session_id[:8]}")

    @staticmethod
    def _session_label(session: LabSession) -> str:
        return f"{session.character_id} · {session.version_id or '—'}\n{session.session_id[:8]}"

    def _on_session_selection_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        if not current.isValid():
            self._current_session_id = None
            self._render_no_session()
            return
        session_id = current.data(_ID_ROLE)
        if not isinstance(session_id, str) or not session_id:
            return
        self._current_session_id = session_id
        self._render_session()

    def _render_no_session(self) -> None:
        self.session_header_label.setText("Сессия не выбрана")
        self.transcript_view.clear()
        self.composer_edit.setEnabled(False)
        self.send_button.setEnabled(False)

    def _render_session(self) -> None:
        try:
            session = self._service.get_session(self._current_session_id)
        except CharacterLabApplicationError:
            self._current_session_id = None
            self._render_no_session()
            return
        self.session_header_label.setText(
            f"{session.character_id} · версия {session.version_id or '—'} · "
            f"сессия {session.session_id[:8]} (офлайн)"
        )
        self.transcript_view.clear()
        for message in session.transcript:
            self.transcript_view.addItem(QListWidgetItem(f"{message.role}: {message.content}"))
        self.composer_edit.setEnabled(True)
        self.send_button.setEnabled(True)
        if self._selected_character_id == session.character_id:
            self._update_inspector(session.character_id)

    def _on_send_clicked(self) -> None:
        if self._current_session_id is None:
            return
        text = self.composer_edit.text().strip()
        if not text:
            return
        try:
            self._service.append_message(self._current_session_id, "user", text)
        except CharacterLabApplicationError as exc:
            self.statusBar().showMessage(f"{exc.code}: {exc.message}")
            return
        self.composer_edit.clear()
        self._render_session()
