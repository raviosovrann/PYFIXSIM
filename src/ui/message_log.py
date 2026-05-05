from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import (
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.ui.theme import get_event_role_colors


@dataclass(slots=True)
class _EventEntry:
    """In-memory representation of one event-log line."""

    timestamp: str
    raw_text: str
    category: str
    scope: str


class _EventLogHighlighter(QSyntaxHighlighter):
    """Apply semantic foreground colors to event-log lines."""

    def __init__(self, document: QTextDocument, parent: QWidget | None = None) -> None:
        super().__init__(document)
        role_colors = get_event_role_colors()
        self._formats: dict[str, QTextCharFormat] = {}
        for role, color in role_colors.items():
            text_format = QTextCharFormat()
            text_format.setForeground(color)
            self._formats[role] = text_format

    def highlightBlock(self, text: str) -> None:
        lower_text = text.lower()
        if "[incoming]" in lower_text:
            self.setFormat(0, len(text), self._formats["incoming"])
            return

        if "[outgoing]" in lower_text:
            self.setFormat(0, len(text), self._formats["outgoing"])
            return

        if "[session]" in lower_text:
            self.setFormat(0, len(text), self._formats["session"])
            return

        self.setFormat(0, len(text), self._formats["console"])


class EventsViewer(QGroupBox):
    """Lower-panel event viewer with filters and semantic highlighting."""

    filters_changed = (
        Signal()
    )  # emitted when any Events Viewer visibility filter changes
    search_text_changed = Signal(str)  # emitted when the free-text filter changes

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Events Viewer", parent)
        self._entries: list[_EventEntry] = []
        self._auto_scroll_enabled = True
        self._keep_logs_enabled = False

        self._log_view = QPlainTextEdit(self)
        self._log_view.setObjectName("eventsViewerLog")
        self._log_view.setReadOnly(True)
        self._log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self._timestamp_checkbox = QCheckBox("Timestamp", self)
        self._timestamp_checkbox.setObjectName("eventsViewerTimestampCheckbox")
        self._timestamp_checkbox.setChecked(True)

        self._header_trailer_checkbox = QCheckBox("Header/Trailer", self)
        self._header_trailer_checkbox.setObjectName("eventsViewerHeaderTrailerCheckbox")
        self._header_trailer_checkbox.setChecked(True)

        self._application_checkbox = QCheckBox("Application", self)
        self._application_checkbox.setObjectName("eventsViewerApplicationCheckbox")
        self._application_checkbox.setChecked(True)

        self._session_checkbox = QCheckBox("Session", self)
        self._session_checkbox.setObjectName("eventsViewerSessionCheckbox")
        self._session_checkbox.setChecked(True)

        self._grid_view_checkbox = QCheckBox("Grid View", self)
        self._grid_view_checkbox.setObjectName("eventsViewerGridViewCheckbox")

        self._split_window_checkbox = QCheckBox("Split Window", self)
        self._split_window_checkbox.setObjectName("eventsViewerSplitWindowCheckbox")

        self._incoming_checkbox = QCheckBox("Incoming", self)
        self._incoming_checkbox.setObjectName("eventsViewerIncomingCheckbox")
        self._incoming_checkbox.setChecked(True)

        self._outgoing_checkbox = QCheckBox("Outgoing", self)
        self._outgoing_checkbox.setObjectName("eventsViewerOutgoingCheckbox")
        self._outgoing_checkbox.setChecked(True)

        self._console_checkbox = QCheckBox("Console", self)
        self._console_checkbox.setObjectName("eventsViewerConsoleCheckbox")
        self._console_checkbox.setChecked(True)

        self._filter_edit = QLineEdit(self)
        self._filter_edit.setObjectName("eventsViewerFilterEdit")
        self._filter_edit.setPlaceholderText("Enter text to filter the event stream")

        self._highlighter = _EventLogHighlighter(self._log_view.document(), self)

        self._build_ui()
        self._wire_signals()

    def log_view(self) -> QPlainTextEdit:
        """Return the internal read-only event log widget."""
        return self._log_view

    def filter_line_edit(self) -> QLineEdit:
        """Return the free-text filter line edit."""
        return self._filter_edit

    def append_event(self, message: str) -> None:
        """Append an event line and refresh the visible log."""
        self._entries.append(
            _EventEntry(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                raw_text=message,
                category=self._classify_category(message),
                scope=self._classify_scope(message),
            )
        )
        self._render_entries()

    def clear_events(self) -> None:
        """Remove all currently stored events from the viewer."""
        self._entries.clear()
        self._render_entries()

    def set_auto_scroll_enabled(self, enabled: bool) -> None:
        """Enable or disable automatic scroll-to-end on appended events."""
        self._auto_scroll_enabled = enabled

    def is_auto_scroll_enabled(self) -> bool:
        """Return whether automatic scrolling is enabled."""
        return self._auto_scroll_enabled

    def set_keep_logs_enabled(self, enabled: bool) -> None:
        """Store whether logs should be kept across future lifecycle operations."""
        self._keep_logs_enabled = enabled

    def is_keep_logs_enabled(self) -> bool:
        """Return whether the keep-logs preference is enabled."""
        return self._keep_logs_enabled

    def toPlainText(self) -> str:
        """Return the visible text currently rendered in the log view."""
        return self._log_view.toPlainText()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 8)
        layout.setSpacing(8)

        filters_row = QHBoxLayout()
        filters_row.setSpacing(8)
        filters_row.addWidget(self._timestamp_checkbox)
        filters_row.addWidget(self._header_trailer_checkbox)
        filters_row.addWidget(self._application_checkbox)
        filters_row.addWidget(self._session_checkbox)
        filters_row.addWidget(self._grid_view_checkbox)
        filters_row.addWidget(self._split_window_checkbox)
        filters_row.addWidget(self._incoming_checkbox)
        filters_row.addWidget(self._outgoing_checkbox)
        filters_row.addWidget(self._console_checkbox)
        filters_row.addStretch()
        filters_row.addWidget(QLabel("Filter events by:", self))
        filters_row.addWidget(self._filter_edit, 1)

        layout.addWidget(self._log_view, 1)
        layout.addLayout(filters_row)

    def _wire_signals(self) -> None:
        for checkbox in (
            self._timestamp_checkbox,
            self._header_trailer_checkbox,
            self._application_checkbox,
            self._session_checkbox,
            self._grid_view_checkbox,
            self._split_window_checkbox,
            self._incoming_checkbox,
            self._outgoing_checkbox,
            self._console_checkbox,
        ):
            checkbox.toggled.connect(self._on_filter_control_toggled)

        self._filter_edit.textChanged.connect(self._on_filter_text_changed)

    def _entry_is_visible(self, entry: _EventEntry) -> bool:
        if entry.category == "incoming" and not self._incoming_checkbox.isChecked():
            return False

        if entry.category == "outgoing" and not self._outgoing_checkbox.isChecked():
            return False

        if entry.category == "console" and not self._console_checkbox.isChecked():
            return False

        if entry.scope == "application" and not self._application_checkbox.isChecked():
            return False

        if entry.scope == "session" and not self._session_checkbox.isChecked():
            return False

        filter_text = self._filter_edit.text().strip().lower()
        if filter_text and filter_text not in entry.raw_text.lower():
            return False

        return True

    def _render_entries(self) -> None:
        visible_lines: list[str] = []
        for entry in self._entries:
            if not self._entry_is_visible(entry):
                continue

            if self._timestamp_checkbox.isChecked():
                visible_lines.append(f"[{entry.timestamp}] {entry.raw_text}")
            else:
                visible_lines.append(entry.raw_text)

        self._log_view.setPlainText("\n".join(visible_lines))
        if self._auto_scroll_enabled:
            cursor = self._log_view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._log_view.setTextCursor(cursor)

    def _classify_category(self, message: str) -> str:
        lower_message = message.lower()
        if "[incoming]" in lower_message:
            return "incoming"
        if "[outgoing]" in lower_message:
            return "outgoing"
        return "console"

    def _classify_scope(self, message: str) -> str:
        lower_message = message.lower()
        if "[session]" in lower_message:
            return "session"
        if "[console]" in lower_message:
            return "console"
        return "application"

    @Slot(bool)
    def _on_filter_control_toggled(self, _checked: bool) -> None:
        self._render_entries()
        self.filters_changed.emit()

    @Slot(str)
    def _on_filter_text_changed(self, search_text: str) -> None:
        self._render_entries()
        self.search_text_changed.emit(search_text)
        self.filters_changed.emit()
