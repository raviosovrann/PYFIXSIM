from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from src.config.session_config import (
    SessionConfig,
    SessionConfigError,
    load_config,
    save_config,
)
from src.engine.service import (
    EngineMessageEvent,
    FIXEngineService,
    FIXEngineServiceError,
)
from src.engine.session import SessionState
from src.messages.order import MessageValidationError, NewOrderSingle

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow


class AppController(QObject):
    """Wire built UI widgets to the FIX engine service and config-backed state."""

    status_message_changed = Signal(
        str
    )  # emitted when the controller wants to update the status bar
    application_state_changed = Signal(
        str
    )  # emitted when the controller updates application state text
    session_context_changed = Signal(
        list
    )  # emitted when selected-session context changes
    event_logged = Signal(
        str
    )  # emitted when the controller wants to append an event-log line
    auto_scroll_preference_changed = Signal(
        bool
    )  # emitted when event-viewer auto-scroll should change
    keep_logs_preference_changed = Signal(
        bool
    )  # emitted when the keep-logs preference should change

    def __init__(
        self,
        window: MainWindow,
        engine_service: FIXEngineService | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        super().__init__(window)
        self._window = window
        self._engine_service = engine_service or FIXEngineService()
        self._config_path = config_path
        self._known_session_configs: dict[str, SessionConfig] = {}
        self._selected_session_id: str | None = None

        self._wire_output_signals()
        self._wire_engine_service()
        self._wire_ui_signals()
        self._bootstrap_sessions()

    def _wire_output_signals(self) -> None:
        self.status_message_changed.connect(self._window.set_status_message)
        self.application_state_changed.connect(self._window.set_application_state)
        self.session_context_changed.connect(self._window.set_selected_session_context)
        self.event_logged.connect(self._window.append_event)
        self.auto_scroll_preference_changed.connect(
            self._window.events_viewer_panel.set_auto_scroll_enabled
        )
        self.keep_logs_preference_changed.connect(
            self._window.events_viewer_panel.set_keep_logs_enabled
        )

    def _wire_engine_service(self) -> None:
        self._engine_service.register_state_change_handler(
            self._on_engine_state_changed
        )
        self._engine_service.register_outbound_message_handler(
            self._on_outbound_message
        )
        self._engine_service.register_inbound_message_handler(self._on_inbound_message)
        self._engine_service.register_error_handler(self._on_engine_error)

    def _wire_ui_signals(self) -> None:
        self._window.session_list_widget.selection_changed.connect(
            self._on_session_selection_changed
        )
        self._window.session_created.connect(self._on_session_created)
        self._window.create_kafka_session_requested.connect(
            self._on_create_kafka_session_requested
        )
        self._window.start_session_requested.connect(self._on_start_session_requested)
        self._window.stop_session_requested.connect(self._on_stop_session_requested)
        self._window.restart_session_requested.connect(
            self._on_restart_session_requested
        )
        self._window.show_session_messages_requested.connect(
            self._on_show_session_messages_requested
        )
        self._window.close_session_requested.connect(self._on_close_session_requested)
        self._window.close_all_sessions_requested.connect(
            self._on_close_all_sessions_requested
        )
        self._window.refresh_sessions_requested.connect(
            self._on_refresh_sessions_requested
        )
        self._window.create_message_requested.connect(self._on_create_message_requested)
        self._window.load_message_requested.connect(self._on_load_message_requested)
        self._window.save_message_requested.connect(self._on_save_message_requested)
        self._window.edit_message_requested.connect(self._on_edit_message_requested)
        self._window.send_current_message_requested.connect(
            self._on_send_current_message_requested
        )
        self._window.send_selected_messages_requested.connect(
            self._on_send_selected_messages_requested
        )
        self._window.send_batch_requested.connect(self._on_send_batch_requested)
        self._window.auto_scroll_toggled.connect(self._on_auto_scroll_toggled)
        self._window.keep_logs_toggled.connect(self._on_keep_logs_toggled)

    def _bootstrap_sessions(self) -> None:
        try:
            config = load_config(self._config_path)
        except SessionConfigError as exc:
            self.event_logged.emit(f"[console] Unable to load session config: {exc}")
            return

        self._register_session(config, select=False)
        self.event_logged.emit(
            f"[console] Loaded session configuration for {self._session_id(config)}"
        )

    def _register_session(self, config: SessionConfig, *, select: bool) -> None:
        session_id = self._session_id(config)
        self._known_session_configs[session_id] = config
        self._window.upsert_session_from_config(
            config,
            lifecycle_state="WAITING",
            state_category="waiting",
            select=select,
        )

    def _resolve_target_session_id(self) -> str | None:
        combo_session_id = self._window.send_message_tab.selected_session_id()
        if combo_session_id and combo_session_id in self._known_session_configs:
            return combo_session_id

        selected_session_ids = self._window.session_list_widget.selected_session_ids()
        if selected_session_ids:
            return selected_session_ids[0]

        if len(self._known_session_configs) == 1:
            return next(iter(self._known_session_configs))

        return None

    def _ensure_session_for_id(self, session_id: str) -> SessionConfig:
        config = self._known_session_configs[session_id]
        active_config = self._engine_service.active_config
        if active_config is not None and self._session_id(active_config) == session_id:
            return config

        active_session = self._engine_service.active_session
        if (
            active_session is not None
            and active_session.state is not SessionState.DISCONNECTED
        ):
            self._engine_service.close_session("Switching active session")

        self._engine_service.create_session(config)
        return config

    def _ensure_selected_session(self) -> SessionConfig | None:
        session_id = self._resolve_target_session_id()
        if session_id is None:
            self.status_message_changed.emit("No session is available for this action")
            self.event_logged.emit("[console] No session is available for this action.")
            return None

        if not self._window.session_list_widget.selected_session_ids():
            self._window.session_list_widget.select_session(session_id)

        return self._ensure_session_for_id(session_id)

    def _render_message_for_editor(self, raw_message: str) -> str:
        return raw_message.replace("\x01", "|")

    def _send_message_blocks(self, message_blocks: list[str]) -> None:
        if not message_blocks:
            self.status_message_changed.emit("No FIX messages are available to send")
            return

        config = self._ensure_selected_session()
        if config is None:
            return

        try:
            self._engine_service.open_session(config)
            for message_block in message_blocks:
                self._engine_service.send_raw_message(message_block)
        except (FIXEngineServiceError, MessageValidationError) as exc:
            self._on_engine_error(exc)
            return

        self.status_message_changed.emit(
            f"Sent {len(message_blocks)} FIX message(s) for {self._session_id(config)}"
        )

    @staticmethod
    def _session_id(config: SessionConfig) -> str:
        return f"{config.sender_comp_id}->{config.target_comp_id}"

    @staticmethod
    def _state_details(state: SessionState) -> tuple[str, str]:
        if state is SessionState.ACTIVE:
            return "CONNECTED", "connected"
        if state is SessionState.LOGGING_OUT:
            return "DISCONNECTING", "waiting"
        if state is SessionState.CONNECTED:
            return "CONNECTED", "connected"
        if state is SessionState.CONNECTING:
            return "CONNECTING", "waiting"
        if state is SessionState.LOGGING_ON:
            return "LOGGING ON", "waiting"
        return "WAITING", "waiting"

    @Slot(list)
    def _on_session_selection_changed(self, session_ids: list[str]) -> None:
        self._selected_session_id = session_ids[0] if session_ids else None
        self.session_context_changed.emit(session_ids)

    @Slot(dict)
    def _on_session_created(self, config_data: dict[str, object]) -> None:
        try:
            config = SessionConfig.from_dict(config_data)
            save_config(config, self._config_path)
        except SessionConfigError as exc:
            self._on_engine_error(exc)
            return

        self._register_session(config, select=True)
        self.application_state_changed.emit("Application: Session created")
        self.status_message_changed.emit("New session was created")
        self.event_logged.emit(
            f"[session] New session was created: {self._session_id(config)} ({config.fix_version} {config.session_type})"
        )

    @Slot()
    def _on_create_kafka_session_requested(self) -> None:
        self.status_message_changed.emit("Kafka sessions are not implemented yet")
        self.event_logged.emit("[console] Kafka sessions are not implemented yet.")

    @Slot()
    def _on_start_session_requested(self) -> None:
        config = self._ensure_selected_session()
        if config is None:
            return

        try:
            self._engine_service.open_session(config)
        except FIXEngineServiceError as exc:
            self._on_engine_error(exc)

    @Slot()
    def _on_stop_session_requested(self) -> None:
        if self._engine_service.active_session is None:
            self.status_message_changed.emit("No active session is available to stop")
            return

        try:
            self._engine_service.close_session("Client requested stop")
        except FIXEngineServiceError as exc:
            self._on_engine_error(exc)

    @Slot()
    def _on_restart_session_requested(self) -> None:
        config = self._ensure_selected_session()
        if config is None:
            return

        try:
            if self._engine_service.active_session is not None:
                self._engine_service.close_session("Client requested restart")
            self._engine_service.open_session(config)
        except FIXEngineServiceError as exc:
            self._on_engine_error(exc)

    @Slot()
    def _on_show_session_messages_requested(self) -> None:
        session_id = self._resolve_target_session_id()
        if session_id is None:
            self.status_message_changed.emit("No session is selected")
            return

        self.event_logged.emit(f"[session] Showing messages for {session_id}")

    @Slot()
    def _on_close_session_requested(self) -> None:
        session_id = self._resolve_target_session_id()
        if session_id is None:
            self.status_message_changed.emit("No session is selected")
            return

        active_config = self._engine_service.active_config
        if active_config is not None and self._session_id(active_config) == session_id:
            try:
                if self._engine_service.active_session is not None:
                    self._engine_service.close_session("Client requested close")
            except FIXEngineServiceError as exc:
                self._on_engine_error(exc)

        self._known_session_configs.pop(session_id, None)
        self._window.remove_session_entry(session_id)
        self.session_context_changed.emit([])
        self.status_message_changed.emit(f"Closed session {session_id}")

    @Slot()
    def _on_close_all_sessions_requested(self) -> None:
        if self._engine_service.active_session is not None:
            try:
                self._engine_service.close_session("Client requested close all")
            except FIXEngineServiceError as exc:
                self._on_engine_error(exc)

        self._known_session_configs.clear()
        self._window.clear_session_entries()
        self.session_context_changed.emit([])
        self.application_state_changed.emit("Application: Ready")
        self.status_message_changed.emit("Closed all sessions")

    @Slot()
    def _on_refresh_sessions_requested(self) -> None:
        try:
            config = load_config(self._config_path)
        except SessionConfigError as exc:
            self._on_engine_error(exc)
            return

        self._register_session(config, select=False)
        self.status_message_changed.emit("Session configuration refreshed")

    @Slot()
    def _on_create_message_requested(self) -> None:
        config = self._ensure_selected_session()
        if config is None:
            return

        order = NewOrderSingle(
            ClOrdID=f"ORDER_{datetime.now().strftime('%H%M%S')}",
            Symbol="AAPL",
            Side="1",
            OrderQty=100,
            OrdType="2",
            Price=25.5,
        )
        fix_message = order.to_fix_message(config, MsgSeqNum=config.out_seq_num)
        raw_message = self._render_message_for_editor(
            bytes(fix_message.encode()).decode("utf-8", errors="replace")
        )
        self._window.send_message_tab.set_message_text(raw_message)
        self._window.send_message_tab.focus_editor()
        self.status_message_changed.emit(
            "Created a NewOrderSingle template in the editor"
        )

    @Slot()
    def _on_load_message_requested(self) -> None:
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self._window,
            "Load FIX message",
            "",
            "FIX text (*.fix *.txt);;All files (*)",
        )
        if not file_path:
            return

        message_text = Path(file_path).read_text(encoding="utf-8")
        self._window.send_message_tab.set_message_text(message_text)
        self._window.send_message_tab.focus_editor()
        self.status_message_changed.emit(
            f"Loaded FIX message from {Path(file_path).name}"
        )

    @Slot()
    def _on_save_message_requested(self) -> None:
        message_text = self._window.send_message_tab.message_text().strip()
        if not message_text:
            self.status_message_changed.emit("There is no message text to save")
            return

        file_path, _selected_filter = QFileDialog.getSaveFileName(
            self._window,
            "Save FIX message",
            "fix-message.fix",
            "FIX text (*.fix *.txt);;All files (*)",
        )
        if not file_path:
            return

        Path(file_path).write_text(message_text, encoding="utf-8")
        self.status_message_changed.emit(f"Saved FIX message to {Path(file_path).name}")

    @Slot()
    def _on_edit_message_requested(self) -> None:
        self._window.workspace_tabs.setCurrentWidget(self._window.send_message_tab)
        self._window.send_message_tab.focus_editor()
        self.status_message_changed.emit("Send Message editor focused for editing")

    @Slot()
    def _on_send_current_message_requested(self) -> None:
        current_block = self._window.send_message_tab.current_message_block()
        self._send_message_blocks([current_block] if current_block else [])

    @Slot()
    def _on_send_selected_messages_requested(self) -> None:
        selected_blocks = self._window.send_message_tab.selected_message_blocks()
        if not selected_blocks:
            current_block = self._window.send_message_tab.current_message_block()
            selected_blocks = [current_block] if current_block else []
        self._send_message_blocks(selected_blocks)

    @Slot()
    def _on_send_batch_requested(self) -> None:
        self._send_message_blocks(self._window.send_message_tab.all_message_blocks())

    @Slot(bool)
    def _on_auto_scroll_toggled(self, checked: bool) -> None:
        self.auto_scroll_preference_changed.emit(checked)

    @Slot(bool)
    def _on_keep_logs_toggled(self, checked: bool) -> None:
        self.keep_logs_preference_changed.emit(checked)

    @Slot(SessionState)
    def _on_engine_state_changed(self, state: SessionState) -> None:
        config = self._engine_service.active_config
        if config is None:
            return

        lifecycle_state, state_category = self._state_details(state)
        self._window.upsert_session_from_config(
            config,
            lifecycle_state=lifecycle_state,
            state_category=state_category,
            select=False,
        )

        if state is SessionState.ACTIVE:
            self.application_state_changed.emit("Application: Session active")
            self.status_message_changed.emit(
                f"Session {self._session_id(config)} is ACTIVE"
            )
        elif state is SessionState.DISCONNECTED:
            self.application_state_changed.emit("Application: Ready")

    @Slot(EngineMessageEvent)
    def _on_outbound_message(self, event: EngineMessageEvent) -> None:
        raw_message = (
            f" | {self._render_message_for_editor(event.raw_message)}"
            if event.raw_message
            else ""
        )
        self.event_logged.emit(
            f"[outgoing] {event.session_id} | {event.message}{raw_message}"
        )

    @Slot(EngineMessageEvent)
    def _on_inbound_message(self, event: EngineMessageEvent) -> None:
        raw_message = (
            f" | {self._render_message_for_editor(event.raw_message)}"
            if event.raw_message
            else ""
        )
        self.event_logged.emit(
            f"[incoming] {event.session_id} | {event.message}{raw_message}"
        )

    @Slot(Exception)
    def _on_engine_error(self, error: Exception) -> None:
        self.status_message_changed.emit(str(error))
        self.event_logged.emit(f"[console] {error}")
