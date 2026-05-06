from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPoint, Qt, Signal, Slot
from PySide6.QtGui import QAction, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class SendMessageTab(QWidget):
    """Manual send workspace for raw FIX or Kafka messages."""

    send_all_requested = Signal()  # emitted when the user requests sending all messages
    send_selected_requested = (
        Signal()
    )  # emitted when the user requests sending selected messages
    send_current_and_next_requested = (
        Signal()
    )  # emitted when the user sends the current block and advances
    reset_requested = Signal()  # emitted when the user resets send progression
    record_test_scenario_requested = (
        Signal()
    )  # emitted when the user starts recording a test scenario
    load_requested = Signal()  # emitted when the user requests loading message text
    save_requested = Signal()  # emitted when the user requests saving message text
    edit_requested = Signal()  # emitted when the user requests structured editing
    insert_soh_requested = (
        Signal()
    )  # emitted when the user inserts a SOH delimiter into the editor
    word_wrap_toggled = Signal(bool)  # emitted when editor word wrap is toggled
    session_changed = Signal(str)  # emitted when the selected session changes
    search_text_changed = Signal(
        str
    )  # emitted when the raw-message search text changes

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._session_selector = QComboBox(self)
        self._session_selector.setObjectName("sendMessageSessionCombo")

        self._rate_spin = QDoubleSpinBox(self)
        self._rate_spin.setObjectName("sendMessageRateSpin")
        self._rate_spin.setDecimals(4)
        self._rate_spin.setRange(0.0, 99999.0)

        self._send_count_spin = QSpinBox(self)
        self._send_count_spin.setObjectName("sendMessageCountSpin")
        self._send_count_spin.setRange(1, 9999)
        self._send_count_spin.setValue(1)

        self._message_editor = QPlainTextEdit(self)
        self._message_editor.setObjectName("sendMessageEditor")
        self._message_editor.setPlaceholderText(
            "8=FIX.4.4|9=...|35=D|49=SENDER|56=TARGET|11=ORDER_1|55=ABCDEF|54=1|60=...|"
        )
        self._message_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._message_editor.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        self._send_all_button = QPushButton("Send all", self)
        self._send_all_button.setObjectName("sendAllButton")
        self._send_selected_button = QPushButton("Send selected", self)
        self._send_selected_button.setObjectName("sendSelectedButton")
        self._send_current_next_button = QPushButton("Send current\nand go Next", self)
        self._send_current_next_button.setObjectName("sendCurrentAndNextButton")
        self._reset_button = QPushButton("Reset", self)
        self._reset_button.setObjectName("sendMessageResetButton")
        self._record_scenario_button = QPushButton("Record Test\nScenario", self)
        self._record_scenario_button.setObjectName("recordTestScenarioButton")

        self._autoincrement_edit = QLineEdit("35 11 60", self)
        self._autoincrement_edit.setObjectName("sendMessageAutoincrementEdit")
        self._search_edit = QLineEdit(self)
        self._search_edit.setObjectName("sendMessageSearchEdit")
        self._search_edit.setPlaceholderText("Search raw messages")

        self._build_ui()
        self._create_editor_actions()
        self._wire_signals()
        self.set_available_sessions([])

    def set_available_sessions(
        self,
        session_ids: Sequence[str],
        *,
        selected_session_id: str | None = None,
    ) -> None:
        """Populate the session selector with available session IDs."""
        previous_session = self.selected_session_id()
        target_session = selected_session_id or previous_session

        self._session_selector.blockSignals(True)
        self._session_selector.clear()
        self._session_selector.addItem("Select session")
        for session_id in session_ids:
            self._session_selector.addItem(session_id)

        if target_session and target_session in session_ids:
            self._session_selector.setCurrentText(target_session)
        else:
            self._session_selector.setCurrentIndex(0)
        self._session_selector.blockSignals(False)

    def selected_session_id(self) -> str | None:
        """Return the currently selected session ID, if any."""
        current_text = self._session_selector.currentText()
        if not current_text or current_text == "Select session":
            return None
        return current_text

    def message_text(self) -> str:
        """Return the raw message text from the editor."""
        return self._message_editor.toPlainText()

    def set_message_text(self, text: str) -> None:
        """Replace the current editor contents with the provided text."""
        self._message_editor.setPlainText(text)

    def editable_message_text(self) -> str | None:
        """Return the current or nearest non-empty message block for editing."""
        return self.current_message_block()

    def replace_current_message_block(self, text: str) -> None:
        """Replace the current message block without rewriting other editor blocks."""
        message_text = self.message_text()
        if message_text == "":
            self.set_message_text(text)
            return

        message_lines = message_text.split("\n")
        current_block_number = self._nearest_non_empty_block_index(message_lines)
        if current_block_number is None:
            self.set_message_text(text)
            return

        message_lines[current_block_number] = text
        self.set_message_text("\n".join(message_lines))

        cursor = self._message_editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(
            min(current_block_number, max(self._message_editor.blockCount() - 1, 0))
        ):
            cursor.movePosition(QTextCursor.MoveOperation.Down)
        self._message_editor.setTextCursor(cursor)

    def focus_editor(self) -> None:
        """Move keyboard focus to the raw message editor."""
        self._message_editor.setFocus(Qt.FocusReason.OtherFocusReason)

    def all_message_blocks(self) -> list[str]:
        """Return all non-empty message blocks from the raw editor."""
        return [
            line.strip() for line in self.message_text().splitlines() if line.strip()
        ]

    def selected_message_blocks(self) -> list[str]:
        """Return selected non-empty message blocks from the raw editor."""
        selected_text = self._message_editor.textCursor().selectedText()
        if not selected_text:
            return []

        return [
            line.strip()
            for line in selected_text.replace("\u2029", "\n").splitlines()
            if line.strip()
        ]

    def current_message_block(self) -> str | None:
        """Return the current or nearest non-empty message block under the cursor."""
        current_block_number = self._nearest_non_empty_block_index(
            self.message_text().split("\n")
        )
        if current_block_number is None:
            return None

        current_text = self._message_editor.document().findBlockByNumber(
            current_block_number
        ).text().strip()
        if not current_text:
            return None
        return current_text

    def _nearest_non_empty_block_index(self, message_lines: list[str]) -> int | None:
        if not message_lines or all(not line.strip() for line in message_lines):
            return None

        cursor_block_number = min(
            self._message_editor.textCursor().blockNumber(),
            len(message_lines) - 1,
        )

        if message_lines[cursor_block_number].strip():
            return cursor_block_number

        for block_number in range(cursor_block_number - 1, -1, -1):
            if message_lines[block_number].strip():
                return block_number

        for block_number in range(cursor_block_number + 1, len(message_lines)):
            if message_lines[block_number].strip():
                return block_number

        return None

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)
        controls_layout.addWidget(QLabel("Session:", self))
        controls_layout.addWidget(self._session_selector, 1)
        controls_layout.addStretch()
        controls_layout.addWidget(QLabel("Rate (msg/sec):", self))
        controls_layout.addWidget(self._rate_spin)
        controls_layout.addSpacing(12)
        controls_layout.addWidget(QLabel("Send count:", self))
        controls_layout.addWidget(self._send_count_spin)

        editor_layout = QHBoxLayout()
        editor_layout.setSpacing(8)
        editor_layout.addWidget(self._message_editor, 1)

        button_column = QVBoxLayout()
        button_column.setSpacing(6)
        button_column.addWidget(self._send_all_button)
        button_column.addWidget(self._send_selected_button)
        button_column.addWidget(self._send_current_next_button)
        button_column.addWidget(self._reset_button)
        button_column.addWidget(self._record_scenario_button)
        button_column.addStretch()
        editor_layout.addLayout(button_column)

        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(8)
        footer_layout.addWidget(QLabel("Autoincrement tags:", self))
        footer_layout.addWidget(self._autoincrement_edit, 1)
        footer_layout.addWidget(QLabel("Search:", self))
        footer_layout.addWidget(self._search_edit, 1)

        root.addLayout(controls_layout)
        root.addLayout(editor_layout, 1)
        root.addLayout(footer_layout)

    def _create_editor_actions(self) -> None:
        self._load_action = QAction("Load", self)
        self._load_action.setObjectName("sendMessageLoadAction")

        self._save_action = QAction("Save", self)
        self._save_action.setObjectName("sendMessageSaveAction")

        self._edit_action = QAction("Edit", self)
        self._edit_action.setObjectName("sendMessageEditAction")

        self._insert_soh_action = QAction("Insert <SOH>", self)
        self._insert_soh_action.setObjectName("sendMessageInsertSohAction")

        self._word_wrap_action = QAction("Word Wrap", self)
        self._word_wrap_action.setObjectName("sendMessageWordWrapAction")
        self._word_wrap_action.setCheckable(True)
        self._word_wrap_action.setChecked(False)

    def _wire_signals(self) -> None:
        self._send_all_button.clicked.connect(self.send_all_requested)
        self._send_selected_button.clicked.connect(self.send_selected_requested)
        self._send_current_next_button.clicked.connect(
            self.send_current_and_next_requested
        )
        self._reset_button.clicked.connect(self.reset_requested)
        self._record_scenario_button.clicked.connect(
            self.record_test_scenario_requested
        )

        self._load_action.triggered.connect(self.load_requested)
        self._save_action.triggered.connect(self.save_requested)
        self._edit_action.triggered.connect(self.edit_requested)
        self._insert_soh_action.triggered.connect(self._on_insert_soh_requested)
        self._word_wrap_action.toggled.connect(self._on_word_wrap_toggled)

        self._session_selector.currentTextChanged.connect(self._on_session_text_changed)
        self._search_edit.textChanged.connect(self._on_search_text_changed)
        self._message_editor.customContextMenuRequested.connect(
            self._on_editor_context_menu_requested
        )

    @Slot(QPoint)
    def _on_editor_context_menu_requested(self, position: QPoint) -> None:
        menu = QMenu(self)
        menu.addAction(self._load_action)
        menu.addAction(self._save_action)
        menu.addAction(self._edit_action)
        menu.addSeparator()
        menu.addAction(self._insert_soh_action)
        menu.addAction(self._word_wrap_action)
        menu.exec(self._message_editor.mapToGlobal(position))

    @Slot()
    def _on_insert_soh_requested(self) -> None:
        cursor = self._message_editor.textCursor()
        cursor.insertText("\x01")
        self._message_editor.setTextCursor(cursor)
        self.insert_soh_requested.emit()

    @Slot(bool)
    def _on_word_wrap_toggled(self, checked: bool) -> None:
        mode = (
            QPlainTextEdit.LineWrapMode.WidgetWidth
            if checked
            else QPlainTextEdit.LineWrapMode.NoWrap
        )
        self._message_editor.setLineWrapMode(mode)
        self.word_wrap_toggled.emit(checked)

    @Slot(str)
    def _on_session_text_changed(self, session_text: str) -> None:
        if session_text == "Select session":
            self.session_changed.emit("")
            return
        self.session_changed.emit(session_text)

    @Slot(str)
    def _on_search_text_changed(self, search_text: str) -> None:
        if not search_text:
            cursor = self._message_editor.textCursor()
            cursor.clearSelection()
            self._message_editor.setTextCursor(cursor)
            self.search_text_changed.emit(search_text)
            return

        if not self._message_editor.find(search_text):
            cursor = self._message_editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self._message_editor.setTextCursor(cursor)
            self._message_editor.find(search_text)

        self.search_text_changed.emit(search_text)
