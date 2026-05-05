from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QPoint, Qt, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class SessionListEntry:
    """Display data for one session row in the left navigation pane."""

    session_id: str
    fix_version: str
    role: str
    sender_comp_id: str
    target_comp_id: str
    lifecycle_state: str
    host: str
    port: int
    in_seq_num: int
    out_seq_num: int
    state_category: str


def build_placeholder_sessions() -> list[SessionListEntry]:
    """Return placeholder sessions until backend-driven session loading is implemented."""
    return [
        SessionListEntry(
            session_id="CLIENT_A->BROKER_A",
            fix_version="FIX.4.4",
            role="Initiator",
            sender_comp_id="CLIENT_A",
            target_comp_id="BROKER_A",
            lifecycle_state="WAITING",
            host="127.0.0.1",
            port=9878,
            in_seq_num=1,
            out_seq_num=1,
            state_category="waiting",
        ),
        SessionListEntry(
            session_id="SIM_FEED->PRICE_CLIENT",
            fix_version="FIX.4.4",
            role="Acceptor",
            sender_comp_id="SIM_FEED",
            target_comp_id="PRICE_CLIENT",
            lifecycle_state="CONNECTED",
            host="127.0.0.1",
            port=9880,
            in_seq_num=17,
            out_seq_num=9,
            state_category="connected",
        ),
        SessionListEntry(
            session_id="DROP_COPY->OPS",
            fix_version="FIX.4.2",
            role="Initiator",
            sender_comp_id="DROP_COPY",
            target_comp_id="OPS",
            lifecycle_state="ERROR",
            host="10.1.0.22",
            port=9891,
            in_seq_num=208,
            out_seq_num=211,
            state_category="error",
        ),
    ]


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class _SessionRowWidget(QWidget):
    """Compact multiline row widget used inside the session list."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setProperty("sessionRow", "true")
        self.setProperty("selected", "false")

        self._indicator_label = QLabel("●", self)
        self._indicator_label.setObjectName("sessionRowIndicator")
        self._indicator_label.setProperty("sessionIndicator", "waiting")
        self._indicator_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        )
        self._indicator_label.setFixedWidth(18)

        self._primary_label = QLabel(self)
        self._primary_label.setObjectName("sessionRowPrimaryLabel")
        self._primary_label.setProperty("sessionRole", "primary")

        self._secondary_label = QLabel(self)
        self._secondary_label.setObjectName("sessionRowSecondaryLabel")
        self._secondary_label.setProperty("sessionRole", "secondary")
        self._secondary_label.setWordWrap(True)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)
        text_layout.addWidget(self._primary_label)
        text_layout.addWidget(self._secondary_label)

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(6, 4, 6, 4)
        root_layout.setSpacing(6)
        root_layout.addWidget(self._indicator_label, 0, Qt.AlignmentFlag.AlignTop)
        root_layout.addLayout(text_layout, 1)

    def _get_indicator_label(self) -> QLabel:
        """Return the state-indicator label, recovering it after wrapper recreation."""
        indicator_label = getattr(self, "_indicator_label", None)
        if isinstance(indicator_label, QLabel):
            return indicator_label

        indicator_label = self.findChild(QLabel, "sessionRowIndicator")
        if indicator_label is None:
            raise RuntimeError("Session row indicator label is not available")

        self._indicator_label = indicator_label
        return indicator_label

    def _get_primary_label(self) -> QLabel:
        """Return the primary summary label, recovering it after wrapper recreation."""
        primary_label = getattr(self, "_primary_label", None)
        if isinstance(primary_label, QLabel):
            return primary_label

        primary_label = self.findChild(QLabel, "sessionRowPrimaryLabel")
        if primary_label is None:
            raise RuntimeError("Session row primary label is not available")

        self._primary_label = primary_label
        return primary_label

    def _get_secondary_label(self) -> QLabel:
        """Return the secondary summary label, recovering it after wrapper recreation."""
        secondary_label = getattr(self, "_secondary_label", None)
        if isinstance(secondary_label, QLabel):
            return secondary_label

        secondary_label = self.findChild(QLabel, "sessionRowSecondaryLabel")
        if secondary_label is None:
            raise RuntimeError("Session row secondary label is not available")

        self._secondary_label = secondary_label
        return secondary_label

    def set_entry(self, entry: SessionListEntry, multiline: bool) -> None:
        """Update the row contents for the supplied session entry."""
        indicator_label = self._get_indicator_label()
        primary_label = self._get_primary_label()
        secondary_label = self._get_secondary_label()

        indicator_label.setProperty("sessionIndicator", entry.state_category)
        _repolish(indicator_label)

        primary_text = (
            f"{entry.fix_version} {entry.role} | "
            f"{entry.sender_comp_id} -> {entry.target_comp_id}"
        )
        secondary_text = (
            f"{entry.lifecycle_state} | {entry.host}:{entry.port} | "
            f"In:{entry.in_seq_num} Out:{entry.out_seq_num}"
        )

        if multiline:
            primary_label.setText(primary_text)
            secondary_label.setText(secondary_text)
            secondary_label.show()
        else:
            primary_label.setText(f"{primary_text} | {secondary_text}")
            secondary_label.hide()

        self.updateGeometry()

    def set_selected(self, selected: bool) -> None:
        """Reflect the QListWidget selection state in the custom row widget."""
        self.setProperty("selected", "true" if selected else "false")
        _repolish(self)


class SessionListWidget(QGroupBox):
    """Left-pane session list with multiline rows and context actions."""

    selection_changed = Signal(list)  # emitted when the selected session IDs change
    refresh_requested = Signal()  # emitted when the user chooses Refresh list
    start_requested = (
        Signal()
    )  # emitted when the user chooses Start for the selected session(s)
    stop_requested = (
        Signal()
    )  # emitted when the user chooses Stop for the selected session(s)
    restart_requested = (
        Signal()
    )  # emitted when the user chooses Restart for the selected session(s)
    show_session_messages_requested = (
        Signal()
    )  # emitted when session messages are requested
    close_session_requested = Signal()  # emitted when the user chooses Close session

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Session List", parent)
        self._entries_by_id: dict[str, SessionListEntry] = {}
        self._multiline_mode = True

        self._list_widget = QListWidget(self)
        self._list_widget.setObjectName("sessionList")
        self._list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list_widget.setSpacing(2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self._list_widget)

        self._create_context_actions()

        self._list_widget.itemSelectionChanged.connect(self._on_item_selection_changed)
        self._list_widget.customContextMenuRequested.connect(
            self._on_context_menu_requested
        )

        self.set_sessions([])

    def selected_session_ids(self) -> list[str]:
        """Return the currently selected session identifiers."""
        return [
            item.data(Qt.ItemDataRole.UserRole)
            for item in self._list_widget.selectedItems()
            if isinstance(item.data(Qt.ItemDataRole.UserRole), str)
        ]

    def session_ids(self) -> list[str]:
        """Return all visible session identifiers in display order."""
        return [
            item.data(Qt.ItemDataRole.UserRole)
            for index in range(self._list_widget.count())
            for item in [self._list_widget.item(index)]
            if isinstance(item.data(Qt.ItemDataRole.UserRole), str)
        ]

    def set_multiline_mode(self, enabled: bool) -> None:
        """Toggle compact multiline rendering for the session summaries."""
        if self._multiline_mode == enabled:
            return

        self._multiline_mode = enabled
        for index in range(self._list_widget.count()):
            item = self._list_widget.item(index)
            self._refresh_item_widget(item)

    def is_multiline_mode(self) -> bool:
        """Return whether multiline rendering is currently enabled."""
        return self._multiline_mode

    def set_sessions(self, sessions: Sequence[SessionListEntry]) -> None:
        """Replace the displayed sessions with the provided entries."""
        self._entries_by_id = {session.session_id: session for session in sessions}
        self._list_widget.clear()

        for session in sessions:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, session.session_id)
            self._list_widget.addItem(item)

            row_widget = _SessionRowWidget(self._list_widget)
            row_widget.set_entry(session, self._multiline_mode)
            self._list_widget.setItemWidget(item, row_widget)
            item.setSizeHint(row_widget.sizeHint())

        self._on_item_selection_changed()

    def add_session(self, session: SessionListEntry, *, select: bool = True) -> None:
        """Add or update a session entry in the list."""
        sessions = list(self._entries_by_id.values())
        for index, existing in enumerate(sessions):
            if existing.session_id != session.session_id:
                continue

            sessions[index] = session
            break
        else:
            sessions.append(session)

        self.set_sessions(sessions)
        if select:
            self.select_session(session.session_id)

    def remove_session(self, session_id: str) -> None:
        """Remove the session matching the provided identifier from the list."""
        sessions = [
            session
            for session in self._entries_by_id.values()
            if session.session_id != session_id
        ]
        self.set_sessions(sessions)

    def clear_sessions(self) -> None:
        """Remove all displayed sessions."""
        self.set_sessions([])

    def select_session(self, session_id: str) -> None:
        """Select the row matching the provided session identifier."""
        self._list_widget.clearSelection()
        for index in range(self._list_widget.count()):
            item = self._list_widget.item(index)
            if item.data(Qt.ItemDataRole.UserRole) != session_id:
                continue

            item.setSelected(True)
            self._list_widget.setCurrentItem(item)
            self._list_widget.scrollToItem(item)
            break

    def _create_context_actions(self) -> None:
        self._refresh_action = QAction("Refresh list", self)
        self._refresh_action.setObjectName("sessionRefreshAction")
        self._refresh_action.triggered.connect(self._on_refresh_requested)

        self._start_action = QAction("Start", self)
        self._start_action.setObjectName("sessionStartAction")
        self._start_action.triggered.connect(self._on_start_requested)

        self._stop_action = QAction("Stop", self)
        self._stop_action.setObjectName("sessionStopAction")
        self._stop_action.triggered.connect(self._on_stop_requested)

        self._restart_action = QAction("Restart", self)
        self._restart_action.setObjectName("sessionRestartAction")
        self._restart_action.triggered.connect(self._on_restart_requested)

        self._show_messages_action = QAction("Show session messages", self)
        self._show_messages_action.setObjectName("sessionShowMessagesAction")
        self._show_messages_action.triggered.connect(
            self._on_show_session_messages_requested
        )

        self._close_action = QAction("Close session", self)
        self._close_action.setObjectName("sessionCloseAction")
        self._close_action.triggered.connect(self._on_close_session_requested)

    def _refresh_item_widget(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return

        session_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(session_id, str):
            return

        entry = self._entries_by_id.get(session_id)
        row_widget = self._list_widget.itemWidget(item)
        if entry is None or not isinstance(row_widget, _SessionRowWidget):
            return

        row_widget.set_entry(entry, self._multiline_mode)
        row_widget.set_selected(item.isSelected())
        item.setSizeHint(row_widget.sizeHint())

    @Slot()
    def _on_item_selection_changed(self) -> None:
        for index in range(self._list_widget.count()):
            self._refresh_item_widget(self._list_widget.item(index))

        self.selection_changed.emit(self.selected_session_ids())

    @Slot(QPoint)
    def _on_context_menu_requested(self, position: QPoint) -> None:
        clicked_item = self._list_widget.itemAt(position)
        if clicked_item is not None and not clicked_item.isSelected():
            self._list_widget.clearSelection()
            clicked_item.setSelected(True)

        has_selection = bool(self.selected_session_ids())
        for action in (
            self._start_action,
            self._stop_action,
            self._restart_action,
            self._show_messages_action,
            self._close_action,
        ):
            action.setEnabled(has_selection)

        menu = QMenu(self)
        menu.addAction(self._refresh_action)
        menu.addSeparator()
        menu.addAction(self._start_action)
        menu.addAction(self._stop_action)
        menu.addAction(self._restart_action)
        menu.addAction(self._show_messages_action)
        menu.addAction(self._close_action)
        menu.exec(self._list_widget.mapToGlobal(position))

    @Slot()
    def _on_refresh_requested(self) -> None:
        self.refresh_requested.emit()

    @Slot()
    def _on_start_requested(self) -> None:
        self.start_requested.emit()

    @Slot()
    def _on_stop_requested(self) -> None:
        self.stop_requested.emit()

    @Slot()
    def _on_restart_requested(self) -> None:
        self.restart_requested.emit()

    @Slot()
    def _on_show_session_messages_requested(self) -> None:
        self.show_session_messages_requested.emit()

    @Slot()
    def _on_close_session_requested(self) -> None:
        self.close_session_requested.emit()
