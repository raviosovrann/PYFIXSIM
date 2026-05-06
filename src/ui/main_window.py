from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.ui.create_session_dialog import CreateSessionDialog
from src.ui.controller import AppController
from src.ui.message_log import EventsViewer
from src.ui.order_panel import SendMessageTab
from src.ui.session_widget import SessionListEntry, SessionListWidget
from src.ui.theme import get_app_stylesheet

if TYPE_CHECKING:
    from src.config.session_config import SessionConfig
    from src.engine.service import FIXEngineService


class MainWindow(QMainWindow):
    """Main application shell for the FIX Client Simulator UI."""

    create_fix_session_requested = (
        Signal()
    )  # emitted when Session -> Create new FIX Session... is chosen
    create_kafka_session_requested = (
        Signal()
    )  # emitted when Session -> Create new Kafka Session... is chosen
    start_session_requested = Signal()  # emitted when Session -> Start is chosen
    stop_session_requested = Signal()  # emitted when Session -> Stop is chosen
    restart_session_requested = Signal()  # emitted when Session -> Restart is chosen
    show_session_messages_requested = (
        Signal()
    )  # emitted when session message visibility is toggled from menus
    close_session_requested = Signal()  # emitted when Session -> Close is chosen
    close_all_sessions_requested = (
        Signal()
    )  # emitted when Session -> Close all is chosen
    refresh_sessions_requested = (
        Signal()
    )  # emitted when the user requests a session refresh
    session_created = Signal(
        dict
    )  # emitted when a new session configuration is submitted
    create_message_requested = Signal()  # emitted when Message -> Create... is chosen
    load_message_requested = Signal()  # emitted when Message -> Load... is chosen
    save_message_requested = Signal()  # emitted when Message -> Save... is chosen
    edit_message_requested = Signal()  # emitted when Message -> Edit... is chosen
    send_current_message_requested = (
        Signal()
    )  # emitted when Message -> Send current message is chosen
    send_selected_messages_requested = Signal()  # emitted when Send selected is chosen
    send_batch_requested = Signal()  # emitted when Message -> Send batch... is chosen
    clear_events_requested = (
        Signal()
    )  # emitted when the Events Viewer should be cleared
    auto_scroll_toggled = Signal(
        bool
    )  # emitted when the Events Viewer auto-scroll changes
    keep_logs_toggled = Signal(
        bool
    )  # emitted when the Events Viewer keep-logs setting changes

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        engine_service: FIXEngineService | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._auto_scroll_enabled = True
        self._create_session_dialog: CreateSessionDialog | None = None

        self.setWindowTitle("FIXSIM — FIX Client Simulator")
        self.setMinimumSize(1180, 760)
        self.resize(1360, 860)
        self.setStyleSheet(get_app_stylesheet())

        self.session_list_widget = SessionListWidget(self)
        self.send_message_tab = SendMessageTab(self)
        self.events_viewer_panel = EventsViewer(self)
        self.workspace_tabs = QTabWidget(self)
        self.events_viewer = self.events_viewer_panel.log_view()
        self.filter_events_edit = self.events_viewer_panel.filter_line_edit()
        self.application_state_label = QLabel("Application: Ready", self)
        self.session_state_label = QLabel("Session: No session selected", self)

        self._build_menu_bar()
        self._build_central_layout()
        self._build_status_bar()
        self._wire_session_widget()
        self._wire_send_message_tab()
        self._wire_events_viewer_panel()
        self._sync_send_message_sessions()
        self.create_fix_session_requested.connect(self._show_create_session_dialog)
        self.app_controller = AppController(
            self,
            engine_service=engine_service,
            config_path=config_path,
        )
        self._seed_placeholder_content()

    def set_application_state(self, message: str) -> None:
        """Update the permanent application-state label."""
        self.application_state_label.setText(message)

    def set_selected_session_context(self, session_ids: list[str]) -> None:
        """Update selected-session UI context from controller-driven signals."""
        self._sync_send_message_sessions(session_ids[0] if session_ids else None)

        if not session_ids:
            self.session_state_label.setText("Session: No session selected")
            return

        if len(session_ids) == 1:
            self.session_state_label.setText(f"Session: {session_ids[0]}")
            return

        self.session_state_label.setText(
            f"Session: {session_ids[0]} (+{len(session_ids) - 1} more)"
        )

    def set_status_message(self, message: str) -> None:
        """Show a transient message in the status bar."""
        self.statusBar().showMessage(message, 5000)

    def append_event(self, message: str) -> None:
        """Append a line to the events viewer."""
        self.events_viewer_panel.append_event(message)

    def upsert_session_from_config(
        self,
        config: SessionConfig,
        *,
        lifecycle_state: str,
        state_category: str,
        select: bool = False,
    ) -> None:
        """Create or update a session-list entry from a typed session configuration."""
        entry = SessionListEntry(
            session_id=f"{config.sender_comp_id}->{config.target_comp_id}",
            fix_version=config.fix_version,
            role=config.session_type,
            sender_comp_id=config.sender_comp_id,
            target_comp_id=config.target_comp_id,
            lifecycle_state=lifecycle_state,
            host=config.host,
            port=config.port,
            in_seq_num=config.in_seq_num,
            out_seq_num=config.out_seq_num,
            state_category=state_category,
        )
        self.session_list_widget.add_session(entry, select=select)

    def remove_session_entry(self, session_id: str) -> None:
        """Remove the matching session from the list widget."""
        self.session_list_widget.remove_session(session_id)

    def clear_session_entries(self) -> None:
        """Remove all sessions from the session list widget."""
        self.session_list_widget.clear_sessions()

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        session_menu = menu_bar.addMenu("Session")
        message_menu = menu_bar.addMenu("Message")
        events_menu = menu_bar.addMenu("Events Viewer")
        options_menu = menu_bar.addMenu("Options")
        help_menu = menu_bar.addMenu("Help")

        self._add_action(
            session_menu, "Create new FIX Session...", self._on_create_fix_session
        )
        self._add_action(
            session_menu, "Create new Kafka Session...", self._on_create_kafka_session
        )
        session_menu.addSeparator()
        self._add_action(session_menu, "Start", self._on_start_session)
        self._add_action(session_menu, "Stop", self._on_stop_session)
        self._add_action(session_menu, "Restart", self._on_restart_session)
        self._add_action(
            session_menu,
            "Show session messages",
            self._on_show_session_messages,
            checkable=True,
        )
        session_menu.addSeparator()
        self._add_action(session_menu, "Close", self._on_close_session)
        self._add_action(session_menu, "Close all", self._on_close_all_sessions)
        self._add_action(session_menu, "Refresh", self._on_refresh_sessions)
        session_menu.addSeparator()
        self._add_action(session_menu, "Exit", self._on_exit)

        self._add_action(message_menu, "Create", self._on_create_message)
        self._add_action(message_menu, "Load", self._on_load_message)
        self._add_action(message_menu, "Save", self._on_save_message)
        self._add_action(message_menu, "Edit", self._on_edit_message)
        message_menu.addSeparator()
        self._add_action(
            message_menu, "Send current message", self._on_send_current_message
        )
        self._add_action(message_menu, "Send batch", self._on_send_batch)

        self._add_action(
            events_menu,
            "Auto scroll",
            self._on_auto_scroll_toggled,
            checkable=True,
            checked=True,
        )
        self._add_action(events_menu, "Clear event viewer", self._on_clear_events)
        self._add_action(
            events_menu,
            "Keep logs",
            self._on_keep_logs_toggled,
            checkable=True,
        )

        self._add_action(options_menu, "Allow message re-sending", None, checkable=True)
        self._add_action(options_menu, "Override SenderCompID", None, checkable=True)
        self._add_action(options_menu, "Override TargetCompID", None, checkable=True)
        self._add_action(options_menu, "Restore sessions", None, checkable=True)
        self._add_action(
            options_menu, "Reconnect restored sessions", None, checkable=True
        )
        self._add_action(
            options_menu, "Show restore sessions dialog", None, checkable=True
        )
        self._add_action(
            options_menu,
            "Multiline session information",
            self._on_multiline_session_information_toggled,
            checkable=True,
            checked=True,
        )

        self._add_action(help_menu, "View Help", self._on_help)
        self._add_action(help_menu, "About", self._on_about)

    def _add_action(
        self,
        menu: QWidget,
        text: str,
        slot: Callable[..., None] | None,
        *,
        checkable: bool = False,
        checked: bool = False,
    ) -> QAction:
        action = QAction(text, self)
        action.setCheckable(checkable)
        if checkable:
            action.setChecked(checked)
        if slot is None:
            action.setEnabled(False)
        else:
            action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _build_central_layout(self) -> None:
        top_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        top_splitter.setChildrenCollapsible(False)
        top_splitter.addWidget(self._build_session_pane())
        top_splitter.addWidget(self._build_workspace_tabs())
        top_splitter.setSizes([320, 960])

        main_splitter = QSplitter(Qt.Orientation.Vertical, self)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(self._build_events_viewer_panel())
        main_splitter.setSizes([500, 260])

        self.setCentralWidget(main_splitter)

    def _build_session_pane(self) -> QWidget:
        return self.session_list_widget

    def _build_workspace_tabs(self) -> QWidget:
        self.workspace_tabs.addTab(self.send_message_tab, "Send Message")
        self.workspace_tabs.addTab(self._build_replay_tab(), "Replay")
        self.workspace_tabs.addTab(self._build_test_scenarios_tab(), "Test Scenarios")
        return self.workspace_tabs

    def _build_replay_tab(self) -> QWidget:
        tab = QWidget(self)
        root = QVBoxLayout(tab)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        file_row = QHBoxLayout()
        file_row.setSpacing(8)
        file_row.addWidget(QLabel("Log file:", tab))
        file_path = QLineEdit(tab)
        file_path.setPlaceholderText("Select replay log file")
        file_row.addWidget(file_path, 1)

        browse_button = QPushButton("...", tab)
        browse_button.setEnabled(False)
        file_row.addWidget(browse_button)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel("From:", tab))
        from_spin = QSpinBox(tab)
        from_spin.setRange(0, 999999)
        filter_row.addWidget(from_spin)
        filter_row.addWidget(QLabel("To:", tab))
        to_spin = QSpinBox(tab)
        to_spin.setRange(0, 999999)
        filter_row.addWidget(to_spin)
        filter_row.addWidget(QLabel("Message type:", tab))
        filter_row.addWidget(QLineEdit(tab), 1)
        filter_row.addWidget(QLabel("Rate (msg/sec):", tab))
        filter_row.addWidget(QDoubleSpinBox(tab))
        filter_row.addWidget(QLabel("Send count:", tab))
        send_count = QSpinBox(tab)
        send_count.setRange(1, 9999)
        send_count.setValue(1)
        filter_row.addWidget(send_count)

        options_row = QHBoxLayout()
        options_row.setSpacing(8)
        use_timestamps = QCheckBox("Use timestamps", tab)
        use_timestamps.setChecked(True)
        options_row.addWidget(use_timestamps)
        options_row.addWidget(QLabel("Speed:", tab))
        speed_spin = QDoubleSpinBox(tab)
        speed_spin.setRange(0.1, 100.0)
        speed_spin.setValue(1.0)
        options_row.addWidget(speed_spin)
        options_row.addStretch()
        for title in ("Play", "Pause", "Stop", "Next"):
            button = QPushButton(title, tab)
            button.setEnabled(False)
            options_row.addWidget(button)

        placeholder = QLabel(
            "Replay transport wiring is intentionally stubbed until ReplayTab is built.",
            tab,
        )
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)

        root.addLayout(file_row)
        root.addLayout(filter_row)
        root.addWidget(placeholder, 1)
        root.addLayout(options_row)

        return tab

    def _build_test_scenarios_tab(self) -> QWidget:
        tab = QWidget(self)
        root = QHBoxLayout(tab)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        placeholder = QPlainTextEdit(tab)
        placeholder.setReadOnly(True)
        placeholder.setPlainText(
            "Action | Test Scenario Name | Session | Details\n"
            "------------------------------------------------\n"
            "Run    | Order happy path    | FIX44   | Not Started\n\n"
            "This placeholder keeps the Test Scenarios tab visible while the dedicated\n"
            "widget and designer dialogs are built in later checklist steps."
        )

        button_column = QVBoxLayout()
        button_column.setSpacing(6)
        create_button = QPushButton("Create Test Scenario", tab)
        create_button.setEnabled(False)
        button_column.addWidget(create_button)
        button_column.addStretch()

        root.addWidget(placeholder, 1)
        root.addLayout(button_column)

        return tab

    def _build_events_viewer_panel(self) -> QWidget:
        return self.events_viewer_panel

    def _build_status_bar(self) -> None:
        status_bar = QStatusBar(self)
        self.setStatusBar(status_bar)
        status_bar.addPermanentWidget(self.application_state_label)
        status_bar.addPermanentWidget(self.session_state_label)
        status_bar.showMessage("FIX Client Simulator is ready")

    def _wire_session_widget(self) -> None:
        self.session_list_widget.refresh_requested.connect(self._on_refresh_sessions)
        self.session_list_widget.start_requested.connect(self._on_start_session)
        self.session_list_widget.stop_requested.connect(self._on_stop_session)
        self.session_list_widget.restart_requested.connect(self._on_restart_session)
        self.session_list_widget.show_session_messages_requested.connect(
            self._on_show_session_messages_from_session_list
        )
        self.session_list_widget.close_session_requested.connect(self._on_close_session)

    def _wire_send_message_tab(self) -> None:
        self.send_message_tab.load_requested.connect(self._on_load_message)
        self.send_message_tab.save_requested.connect(self._on_save_message)
        self.send_message_tab.edit_requested.connect(self._on_edit_message)
        self.send_message_tab.send_all_requested.connect(self._on_send_batch)
        self.send_message_tab.send_selected_requested.connect(
            self._on_send_selected_messages
        )
        self.send_message_tab.send_current_and_next_requested.connect(
            self._on_send_current_message
        )
        self.send_message_tab.reset_requested.connect(self._on_reset_send_message_tab)
        self.send_message_tab.record_test_scenario_requested.connect(
            self._on_record_test_scenario_requested
        )
        self.send_message_tab.insert_soh_requested.connect(
            self._on_insert_soh_requested
        )
        self.send_message_tab.word_wrap_toggled.connect(
            self._on_send_message_word_wrap_toggled
        )
        self.send_message_tab.session_changed.connect(
            self._on_send_message_session_changed
        )
        self.send_message_tab.search_text_changed.connect(
            self._on_send_message_search_text_changed
        )

    def _wire_events_viewer_panel(self) -> None:
        self.events_viewer_panel.filters_changed.connect(
            self._on_events_viewer_filters_changed
        )
        self.events_viewer_panel.search_text_changed.connect(
            self._on_events_viewer_filter_text_changed
        )

    def _sync_send_message_sessions(
        self, selected_session_id: str | None = None
    ) -> None:
        self.send_message_tab.set_available_sessions(
            self.session_list_widget.session_ids(),
            selected_session_id=selected_session_id,
        )

    def _seed_placeholder_content(self) -> None:
        self.events_viewer_panel.clear_events()
        self.append_event("[console] FIX Client Simulator is ready.")

    def _ensure_create_session_dialog(self) -> CreateSessionDialog:
        dialog = self._create_session_dialog
        if dialog is None:
            dialog = CreateSessionDialog(self)
            dialog.session_config_submitted.connect(
                self._on_create_session_dialog_submitted
            )
            dialog.export_for_console_requested.connect(
                self._on_export_for_console_requested
            )
            self._create_session_dialog = dialog

        return dialog

    @Slot()
    def _show_create_session_dialog(self) -> None:
        dialog = self._ensure_create_session_dialog()
        dialog.open()
        self.set_status_message("Create FIX Session dialog opened")

    @Slot()
    def _on_create_fix_session(self) -> None:
        self.set_status_message("Create new FIX Session requested")
        self.create_fix_session_requested.emit()

    @Slot(dict)
    def _on_create_session_dialog_submitted(self, config: dict[str, object]) -> None:
        self.session_created.emit(config)

    @Slot(dict)
    def _on_export_for_console_requested(self, config: dict[str, object]) -> None:
        sender_comp_id = str(config.get("sender_comp_id") or "")
        target_comp_id = str(config.get("target_comp_id") or "")
        fix_version = str(config.get("fix_version") or "")
        session_type = str(config.get("session_type") or "")
        self.append_event(
            "[console] Export for console requested: "
            f"{fix_version} {session_type} {sender_comp_id}->{target_comp_id}"
        )
        self.set_status_message("FIX session configuration exported for console")

    @Slot()
    def _on_create_kafka_session(self) -> None:
        self.set_status_message("Create new Kafka Session requested")
        self.create_kafka_session_requested.emit()

    @Slot()
    def _on_start_session(self) -> None:
        self.set_status_message("Start session requested")
        self.start_session_requested.emit()

    @Slot()
    def _on_stop_session(self) -> None:
        self.set_status_message("Stop session requested")
        self.stop_session_requested.emit()

    @Slot()
    def _on_restart_session(self) -> None:
        self.set_status_message("Restart session requested")
        self.restart_session_requested.emit()

    @Slot(bool)
    def _on_show_session_messages(self, checked: bool) -> None:
        message = (
            "Show session messages enabled"
            if checked
            else "Show session messages disabled"
        )
        self.set_status_message(message)
        self.show_session_messages_requested.emit()

    @Slot()
    def _on_show_session_messages_from_session_list(self) -> None:
        self.set_status_message("Show session messages requested")
        self.show_session_messages_requested.emit()

    @Slot()
    def _on_close_session(self) -> None:
        self.set_status_message("Close session requested")
        self.close_session_requested.emit()

    @Slot()
    def _on_close_all_sessions(self) -> None:
        self.set_status_message("Close all sessions requested")
        self.close_all_sessions_requested.emit()

    @Slot()
    def _on_refresh_sessions(self) -> None:
        self.set_status_message("Session refresh requested")
        self.refresh_sessions_requested.emit()

    @Slot(bool)
    def _on_multiline_session_information_toggled(self, checked: bool) -> None:
        self.session_list_widget.set_multiline_mode(checked)
        self.set_status_message(
            "Multiline session information enabled"
            if checked
            else "Multiline session information disabled"
        )

    @Slot()
    def _on_create_message(self) -> None:
        self.set_status_message("Create message requested")
        self.create_message_requested.emit()

    @Slot()
    def _on_load_message(self) -> None:
        self.set_status_message("Load message requested")
        self.load_message_requested.emit()

    @Slot()
    def _on_save_message(self) -> None:
        self.set_status_message("Save message requested")
        self.save_message_requested.emit()

    @Slot()
    def _on_edit_message(self) -> None:
        self.set_status_message("Edit message requested")
        self.edit_message_requested.emit()

    @Slot()
    def _on_send_current_message(self) -> None:
        self.set_status_message("Send current message requested")
        self.send_current_message_requested.emit()

    @Slot()
    def _on_send_selected_messages(self) -> None:
        self.set_status_message("Send selected messages requested")
        self.send_selected_messages_requested.emit()

    @Slot()
    def _on_send_batch(self) -> None:
        self.set_status_message("Send batch requested")
        self.send_batch_requested.emit()

    @Slot()
    def _on_reset_send_message_tab(self) -> None:
        self.send_message_tab.set_message_text("")
        self.set_status_message("Send Message workspace reset")

    @Slot()
    def _on_record_test_scenario_requested(self) -> None:
        self.workspace_tabs.setCurrentIndex(2)
        self.set_status_message("Record Test Scenario requested")

    @Slot()
    def _on_insert_soh_requested(self) -> None:
        self.set_status_message("<SOH> inserted into message editor")

    @Slot(bool)
    def _on_send_message_word_wrap_toggled(self, checked: bool) -> None:
        self.set_status_message(
            "Word Wrap enabled" if checked else "Word Wrap disabled"
        )

    @Slot(str)
    def _on_send_message_session_changed(self, session_id: str) -> None:
        if session_id:
            self.set_status_message(f"Send Message session selected: {session_id}")

    @Slot(str)
    def _on_send_message_search_text_changed(self, search_text: str) -> None:
        if not search_text:
            return
        self.set_status_message(f"Searching Send Message tab for: {search_text}")

    @Slot()
    def _on_events_viewer_filters_changed(self) -> None:
        self.set_status_message("Events Viewer filters updated")

    @Slot(str)
    def _on_events_viewer_filter_text_changed(self, search_text: str) -> None:
        if not search_text:
            return
        self.set_status_message(f"Filtering Events Viewer by: {search_text}")

    @Slot(bool)
    def _on_auto_scroll_toggled(self, checked: bool) -> None:
        self._auto_scroll_enabled = checked
        self.events_viewer_panel.set_auto_scroll_enabled(checked)
        self.set_status_message(
            "Events Viewer auto-scroll enabled"
            if checked
            else "Events Viewer auto-scroll disabled"
        )
        self.auto_scroll_toggled.emit(checked)

    @Slot()
    def _on_clear_events(self) -> None:
        self.events_viewer_panel.clear_events()
        self.set_status_message("Events Viewer cleared")
        self.clear_events_requested.emit()

    @Slot(bool)
    def _on_keep_logs_toggled(self, checked: bool) -> None:
        self.events_viewer_panel.set_keep_logs_enabled(checked)
        self.set_status_message(
            "Keep logs enabled" if checked else "Keep logs disabled"
        )
        self.keep_logs_toggled.emit(checked)

    @Slot()
    def _on_exit(self) -> None:
        self.close()

    @Slot()
    def _on_help(self) -> None:
        QMessageBox.information(
            self,
            "FIXSIM Help",
            "Help content is still a placeholder in the first MainWindow pass.",
        )

    @Slot()
    def _on_about(self) -> None:
        QMessageBox.information(
            self,
            "About FIXSIM",
            "FIXSIM MainWindow shell\n\n"
            "The application shell is in place with placeholder menus, tabs, and status text.",
        )
