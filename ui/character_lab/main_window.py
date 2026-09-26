"""Qt-native Character Lab shell over ``services.character_lab_application``.

An application/editor shell for testing, inspecting, and (in a later product
stage) authoring AI characters and their versions -- not an in-game Ren'Py
screen. This foundation slice is fully offline: no provider/network call is
made anywhere in this module.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QFont, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
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

_AUTH_DATA_ROLE = _ID_ROLE + 20
_KIND_AUTH_CHARACTER = "authoring_character"
_KIND_AUTH_VERSION = "authoring_version"
_KIND_AUTH_REVISION = "authoring_revision"


def _parse_comma_list(text: str) -> list[str]:
    """Split a comma-separated form value into a trimmed, non-empty list."""

    return [part.strip() for part in text.split(",") if part.strip()]


def _join_list(values: object) -> str:
    """Render a semantic list value back into a comma-separated form value."""

    if isinstance(values, (list, tuple)):
        return ", ".join(str(item) for item in values)
    return ""


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

        self._authoring_character_id: Optional[str] = None
        self._authoring_version_id: Optional[str] = None
        self._authoring_revision_id: Optional[str] = None
        self._authoring_snapshot_hash: Optional[str] = None
        self._authoring_release_id: Optional[str] = None

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
        self._reload_authoring_tree()
        self._refresh_authoring_display()

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

    # -- Center panel: dialogue workspace + authoring ---------------------

    def _build_center_panel(self) -> QWidget:
        tabs = QTabWidget()
        tabs.addTab(self._build_dialogue_panel(), "Диалог")
        tabs.addTab(self._build_authoring_panel(), "Авторинг")
        return tabs

    def _build_dialogue_panel(self) -> QWidget:
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

    # -- Authoring panel: create / edit / approve / publish / export ------

    def _build_authoring_panel(self) -> QWidget:
        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(4, 4, 4, 4)

        create_box = QGroupBox("Создать персонажа")
        create_layout = QVBoxLayout(create_box)
        form_container = QWidget()
        form = QFormLayout(form_container)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.authoring_character_id_edit = QLineEdit()
        self.authoring_version_id_edit = QLineEdit()
        self.authoring_revision_id_edit = QLineEdit()
        self.authoring_version_label_edit = QLineEdit()
        self.authoring_display_name_edit = QLineEdit()
        form.addRow("ID персонажа", self.authoring_character_id_edit)
        form.addRow("ID версии", self.authoring_version_id_edit)
        form.addRow("ID ревизии", self.authoring_revision_id_edit)
        form.addRow("Метка версии", self.authoring_version_label_edit)
        form.addRow("Отображаемое имя", self.authoring_display_name_edit)

        self.authoring_biography_edit = QPlainTextEdit()
        self.authoring_biography_edit.setPlaceholderText("Биография персонажа")
        form.addRow("Биография", self.authoring_biography_edit)

        self.authoring_personality_edit = QLineEdit()
        self.authoring_behavioral_edit = QLineEdit()
        self.authoring_emotional_edit = QLineEdit()
        self.authoring_goals_edit = QLineEdit()
        form.addRow("Личность", self.authoring_personality_edit)
        form.addRow("Поведение", self.authoring_behavioral_edit)
        form.addRow("Эмоции", self.authoring_emotional_edit)
        form.addRow("Цели/мотивация", self.authoring_goals_edit)

        self.authoring_speech_style_edit = QLineEdit()
        self.authoring_register_edit = QLineEdit()
        form.addRow("Стиль речи", self.authoring_speech_style_edit)
        form.addRow("Регистр", self.authoring_register_edit)

        self.authoring_relational_edit = QLineEdit()
        self.authoring_attachment_edit = QLineEdit()
        form.addRow("Отношения", self.authoring_relational_edit)
        form.addRow("Привязанность", self.authoring_attachment_edit)

        self.authoring_appearance_edit = QLineEdit()
        self.authoring_boundaries_edit = QLineEdit()
        form.addRow("Внешность", self.authoring_appearance_edit)
        form.addRow("Границы", self.authoring_boundaries_edit)

        create_layout.addWidget(form_container)
        self.create_character_button = QPushButton("Создать персонажа")
        self.create_character_button.clicked.connect(self._on_create_character_clicked)
        create_layout.addWidget(self.create_character_button)
        outer.addWidget(create_box)

        tree_box = QGroupBox("Персонажи (авторинг)")
        tree_layout = QVBoxLayout(tree_box)
        self.authoring_tree = QTreeWidget()
        self.authoring_tree.setHeaderHidden(True)
        self.authoring_tree.setAccessibleName("Персонажи авторинга")
        self.authoring_tree.itemSelectionChanged.connect(
            self._on_authoring_tree_selection_changed
        )
        tree_layout.addWidget(self.authoring_tree)
        outer.addWidget(tree_box, 1)

        self.authoring_selection_label = QLabel("Персонаж не выбран")
        self.authoring_selection_label.setWordWrap(True)
        outer.addWidget(self.authoring_selection_label)

        self.authoring_releases_label = QLabel("Опубликованные релизы: —")
        self.authoring_releases_label.setWordWrap(True)
        outer.addWidget(self.authoring_releases_label)

        self.authoring_current_label = QLabel("Текущая версия: —")
        self.authoring_current_label.setWordWrap(True)
        outer.addWidget(self.authoring_current_label)

        actions_box = QGroupBox("Действия")
        actions_layout = QVBoxLayout(actions_box)

        self.authoring_decided_by_edit = QLineEdit()
        self.authoring_decided_by_edit.setPlaceholderText("Кто утверждает (decided_by)")
        actions_layout.addWidget(self.authoring_decided_by_edit)

        self.authoring_release_id_edit = QLineEdit()
        self.authoring_release_id_edit.setPlaceholderText("release_id")
        actions_layout.addWidget(self.authoring_release_id_edit)

        self.authoring_display_name_publish_edit = QLineEdit()
        self.authoring_display_name_publish_edit.setPlaceholderText("display_name релиза")
        actions_layout.addWidget(self.authoring_display_name_publish_edit)

        self.authoring_export_path_edit = QLineEdit()
        self.authoring_export_path_edit.setPlaceholderText("Путь экспорта .vchar")
        actions_layout.addWidget(self.authoring_export_path_edit)

        self.save_revision_button = QPushButton("Сохранить revision")
        self.save_revision_button.clicked.connect(self._on_save_revision_clicked)
        actions_layout.addWidget(self.save_revision_button)

        self.submit_button = QPushButton("Отправить на утверждение")
        self.submit_button.clicked.connect(self._on_submit_clicked)
        actions_layout.addWidget(self.submit_button)

        self.approve_button = QPushButton("Утвердить")
        self.approve_button.clicked.connect(self._on_approve_clicked)
        actions_layout.addWidget(self.approve_button)

        self.publish_button = QPushButton("Опубликовать")
        self.publish_button.clicked.connect(self._on_publish_clicked)
        actions_layout.addWidget(self.publish_button)

        self.set_current_button = QPushButton("Сделать текущей версией")
        self.set_current_button.clicked.connect(self._on_set_current_clicked)
        actions_layout.addWidget(self.set_current_button)

        self.export_button = QPushButton("Экспортировать .vchar")
        self.export_button.clicked.connect(self._on_export_clicked)
        actions_layout.addWidget(self.export_button)

        outer.addWidget(actions_box)
        outer.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        return scroll

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

    # -- Authoring handlers / helpers ------------------------------------

    def _collect_semantic(self) -> dict[str, Any]:
        """Read the authoring form into a CharacterSemantic-shaped dict."""

        display_name = (
            self.authoring_display_name_edit.text().strip()
            or self.authoring_character_id_edit.text().strip()
        )
        register = self.authoring_register_edit.text().strip() or None
        return {
            "identity": {"display_name": display_name},
            "biography": self.authoring_biography_edit.toPlainText(),
            "psychology": {
                "personality": _parse_comma_list(self.authoring_personality_edit.text()),
                "behavioral_traits": _parse_comma_list(self.authoring_behavioral_edit.text()),
                "emotional_tendencies": _parse_comma_list(self.authoring_emotional_edit.text()),
                "goals_motivations": _parse_comma_list(self.authoring_goals_edit.text()),
            },
            "speech": {
                "speech_style": self.authoring_speech_style_edit.text().strip(),
                "register": register,
            },
            "character_relations": {
                "relational_tendencies": _parse_comma_list(self.authoring_relational_edit.text()),
                "attachment_traits": _parse_comma_list(self.authoring_attachment_edit.text()),
            },
            "appearance": {
                "descriptors": _parse_comma_list(self.authoring_appearance_edit.text())
            },
            "boundaries": {
                "principles": _parse_comma_list(self.authoring_boundaries_edit.text())
            },
            "visual_identity": {},
        }

    def _load_semantic_to_form(self, semantic: Mapping[str, Any]) -> None:
        """Populate the authoring form from a loaded semantic snapshot."""

        identity = semantic.get("identity") or {}
        self.authoring_display_name_edit.setText(str(identity.get("display_name", "")))
        self.authoring_biography_edit.setPlainText(str(semantic.get("biography", "")))

        psychology = semantic.get("psychology") or {}
        self.authoring_personality_edit.setText(_join_list(psychology.get("personality")))
        self.authoring_behavioral_edit.setText(_join_list(psychology.get("behavioral_traits")))
        self.authoring_emotional_edit.setText(_join_list(psychology.get("emotional_tendencies")))
        self.authoring_goals_edit.setText(_join_list(psychology.get("goals_motivations")))

        speech = semantic.get("speech") or {}
        self.authoring_speech_style_edit.setText(str(speech.get("speech_style", "")))
        register = speech.get("register")
        self.authoring_register_edit.setText("" if register is None else str(register))

        relations = semantic.get("character_relations") or {}
        self.authoring_relational_edit.setText(_join_list(relations.get("relational_tendencies")))
        self.authoring_attachment_edit.setText(_join_list(relations.get("attachment_traits")))

        appearance = semantic.get("appearance") or {}
        self.authoring_appearance_edit.setText(_join_list(appearance.get("descriptors")))
        boundaries = semantic.get("boundaries") or {}
        self.authoring_boundaries_edit.setText(_join_list(boundaries.get("principles")))

    def _require_authoring_selection(self) -> bool:
        if not (
            self._authoring_character_id
            and self._authoring_version_id
            and self._authoring_revision_id
            and self._authoring_snapshot_hash
        ):
            self.statusBar().showMessage("Сначала создайте или выберите ревизию.")
            return False
        return True

    def _on_create_character_clicked(self) -> None:
        character_id = self.authoring_character_id_edit.text().strip()
        version_id = self.authoring_version_id_edit.text().strip()
        revision_id = self.authoring_revision_id_edit.text().strip()
        version_label = self.authoring_version_label_edit.text().strip()
        if not (character_id and version_id and revision_id):
            self.statusBar().showMessage("Заполните ID персонажа, версии и ревизии.")
            return
        try:
            result = self._service.create_character(
                character_id=character_id,
                version_id=version_id,
                revision_id=revision_id,
                version_label=version_label,
                semantic=self._collect_semantic(),
            )
        except CharacterLabApplicationError as exc:
            self.statusBar().showMessage(f"{exc.code}: {exc.message}")
            return
        self._authoring_character_id = result.character_id
        self._authoring_version_id = result.version_id
        self._authoring_revision_id = result.revision_id
        self._authoring_snapshot_hash = result.snapshot_hash
        self._reload_authoring_tree()
        self._refresh_authoring_display()
        self.statusBar().showMessage(
            f"Создан персонаж {result.character_id} (ревизия {result.revision_id})"
        )

    def _on_save_revision_clicked(self) -> None:
        if not (self._authoring_character_id and self._authoring_version_id):
            self.statusBar().showMessage("Сначала создайте или выберите персонажа.")
            return
        revision_id = self.authoring_revision_id_edit.text().strip()
        if not revision_id:
            self.statusBar().showMessage("Укажите новый ID ревизии.")
            return
        try:
            result = self._service.save_character(
                character_id=self._authoring_character_id,
                version_id=self._authoring_version_id,
                revision_id=revision_id,
                semantic=self._collect_semantic(),
            )
        except CharacterLabApplicationError as exc:
            self.statusBar().showMessage(f"{exc.code}: {exc.message}")
            return
        self._authoring_revision_id = result.revision_id
        self._authoring_snapshot_hash = result.snapshot_hash
        self._reload_authoring_tree()
        self._refresh_authoring_display()
        self.statusBar().showMessage(f"Сохранена ревизия {result.revision_id}")

    def _on_submit_clicked(self) -> None:
        if not self._require_authoring_selection():
            return
        try:
            result = self._service.submit_for_approval(
                character_id=self._authoring_character_id,
                version_id=self._authoring_version_id,
                revision_id=self._authoring_revision_id,
                snapshot_hash=self._authoring_snapshot_hash,
            )
        except CharacterLabApplicationError as exc:
            self.statusBar().showMessage(f"{exc.code}: {exc.message}")
            return
        self._refresh_authoring_display()
        self.statusBar().showMessage(f"Отправлено на утверждение: {result.lifecycle_state}")

    def _on_approve_clicked(self) -> None:
        if not self._require_authoring_selection():
            return
        decided_by = self.authoring_decided_by_edit.text()
        if not decided_by.strip():
            self.statusBar().showMessage("Укажите, кто утверждает (decided_by).")
            return
        try:
            result = self._service.approve_as_canon(
                character_id=self._authoring_character_id,
                version_id=self._authoring_version_id,
                revision_id=self._authoring_revision_id,
                snapshot_hash=self._authoring_snapshot_hash,
                decided_by=decided_by,
            )
        except CharacterLabApplicationError as exc:
            self.statusBar().showMessage(f"{exc.code}: {exc.message}")
            return
        self._refresh_authoring_display()
        self.statusBar().showMessage(f"Утверждено: {result.lifecycle_state}")

    def _on_publish_clicked(self) -> None:
        if not self._require_authoring_selection():
            return
        release_id = self.authoring_release_id_edit.text().strip()
        display_name = self.authoring_display_name_publish_edit.text().strip()
        if not release_id or not display_name:
            self.statusBar().showMessage("Укажите release_id и display_name.")
            return
        try:
            result = self._service.publish_character_release(
                character_id=self._authoring_character_id,
                version_id=self._authoring_version_id,
                revision_id=self._authoring_revision_id,
                snapshot_hash=self._authoring_snapshot_hash,
                release_id=release_id,
                display_name=display_name,
                set_current=False,
            )
        except CharacterLabApplicationError as exc:
            self._show_publication_failure(exc)
            return
        self._authoring_release_id = result.release_id
        self._refresh_authoring_display()
        self.statusBar().showMessage(f"Опубликовано: {result.release_id}")

    def _show_publication_failure(self, exc: CharacterLabApplicationError) -> None:
        """Surface LAB-L5 partial success: publication durable but a later stage failed."""

        result = getattr(exc, "result", None)
        published = getattr(exc, "published", False)
        if published and result is not None:
            self._authoring_release_id = result.release_id
            self._refresh_authoring_display()
            self.statusBar().showMessage(
                f"Публикация успешна ({result.release_id}), но {exc.code}: {exc.message}"
            )
        else:
            self.statusBar().showMessage(f"{exc.code}: {exc.message}")

    def _on_set_current_clicked(self) -> None:
        if not self._authoring_character_id:
            self.statusBar().showMessage("Сначала создайте или выберите персонажа.")
            return
        release_id = self.authoring_release_id_edit.text().strip() or self._authoring_release_id
        if not release_id:
            self.statusBar().showMessage("Укажите release_id для назначения текущей.")
            return
        try:
            result = self._service.designate_canonical_current(
                character_id=self._authoring_character_id,
                release_id=release_id,
            )
        except CharacterLabApplicationError as exc:
            self.statusBar().showMessage(f"{exc.code}: {exc.message}")
            return
        self._refresh_authoring_display()
        self.statusBar().showMessage(f"Текущая версия назначена: {result.release_id}")

    def _on_export_clicked(self) -> None:
        if not self._authoring_character_id:
            self.statusBar().showMessage("Сначала создайте или выберите персонажа.")
            return
        release_id = self.authoring_release_id_edit.text().strip() or self._authoring_release_id
        destination = self.authoring_export_path_edit.text().strip()
        if not release_id or not destination:
            self.statusBar().showMessage("Укажите release_id и путь экспорта.")
            return
        try:
            result = self._service.export_character_release(
                character_id=self._authoring_character_id,
                release_id=release_id,
                destination=destination,
            )
        except CharacterLabApplicationError as exc:
            self.statusBar().showMessage(f"{exc.code}: {exc.message}")
            return
        self.statusBar().showMessage(f"Экспортировано: {result.destination}")

    def _reload_authoring_tree(self) -> None:
        self.authoring_tree.clear()
        try:
            characters = self._service.list_authoring_characters()
        except CharacterLabApplicationError as exc:
            self.statusBar().showMessage(f"{exc.code}: {exc.message}")
            return
        for character in characters:
            char_item = QTreeWidgetItem([character.character_id])
            char_item.setData(
                0,
                _AUTH_DATA_ROLE,
                {"kind": _KIND_AUTH_CHARACTER, "character_id": character.character_id},
            )
            self.authoring_tree.addTopLevelItem(char_item)
            try:
                versions = self._service.list_authoring_versions(character.character_id)
            except CharacterLabApplicationError:
                versions = ()
            for version in versions:
                ver_item = QTreeWidgetItem(
                    [f"{version.version_id} · {version.lifecycle_state}"]
                )
                ver_item.setData(
                    0,
                    _AUTH_DATA_ROLE,
                    {
                        "kind": _KIND_AUTH_VERSION,
                        "character_id": character.character_id,
                        "version_id": version.version_id,
                    },
                )
                char_item.addChild(ver_item)
                try:
                    revisions = self._service.list_authoring_revisions(
                        character.character_id, version.version_id
                    )
                except CharacterLabApplicationError:
                    revisions = ()
                for revision in revisions:
                    rev_item = QTreeWidgetItem(
                        [f"{revision.revision_id} · {revision.snapshot_hash[:8]}"]
                    )
                    rev_item.setData(
                        0,
                        _AUTH_DATA_ROLE,
                        {
                            "kind": _KIND_AUTH_REVISION,
                            "character_id": character.character_id,
                            "version_id": version.version_id,
                            "revision_id": revision.revision_id,
                            "snapshot_hash": revision.snapshot_hash,
                        },
                    )
                    ver_item.addChild(rev_item)
            char_item.setExpanded(True)

    def _on_authoring_tree_selection_changed(self) -> None:
        items = self.authoring_tree.selectedItems()
        if not items:
            return
        data = items[0].data(0, _AUTH_DATA_ROLE)
        if not isinstance(data, dict) or data.get("kind") != _KIND_AUTH_REVISION:
            return
        try:
            loaded = self._service.load_revision_semantic(
                data["character_id"], data["version_id"], data["revision_id"]
            )
        except CharacterLabApplicationError as exc:
            self.statusBar().showMessage(f"{exc.code}: {exc.message}")
            return
        self._authoring_character_id = loaded.character_id
        self._authoring_version_id = loaded.version_id
        self._authoring_revision_id = loaded.revision_id
        self._authoring_snapshot_hash = loaded.snapshot_hash
        self.authoring_character_id_edit.setText(loaded.character_id)
        self.authoring_version_id_edit.setText(loaded.version_id)
        self.authoring_revision_id_edit.setText(loaded.revision_id)
        self._load_semantic_to_form(loaded.semantic)
        self._refresh_authoring_display()

    def _refresh_authoring_display(self) -> None:
        character = self._authoring_character_id
        version = self._authoring_version_id
        revision = self._authoring_revision_id
        snapshot = self._authoring_snapshot_hash
        if not (character and version and revision):
            self.authoring_selection_label.setText("Персонаж не выбран")
            self.authoring_releases_label.setText("Опубликованные релизы: —")
            self.authoring_current_label.setText("Текущая версия: —")
            return

        lifecycle = "?"
        try:
            pointer = self._service.read_version_lifecycle(character, version)
            lifecycle = pointer.lifecycle_state
        except CharacterLabApplicationError:
            pass
        snapshot_prefix = snapshot[:8] if snapshot else ""
        self.authoring_selection_label.setText(
            f"{character} / {version} / {revision} · {lifecycle} · {snapshot_prefix}"
        )

        try:
            releases = self._service.list_published_releases(character)
        except CharacterLabApplicationError:
            releases = ()
        if releases:
            lines = ", ".join(
                f"{item.release_id}@{item.package_hash[:8]}" for item in releases
            )
        else:
            lines = "—"
        self.authoring_releases_label.setText(f"Опубликованные релизы: {lines}")

        try:
            current = self._service.read_canonical_current(character)
        except CharacterLabApplicationError:
            current = None
        self.authoring_current_label.setText(
            f"Текущая версия: {current.release_id if current else '—'}"
        )
