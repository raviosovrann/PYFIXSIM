from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, Slot

if TYPE_CHECKING:
	from src.ui.main_window import MainWindow


class AppController(QObject):
	"""First-pass controller that wires UI signals to placeholder service behavior."""

	status_message_changed = Signal(str)  # emitted when the controller wants to update the status bar
	application_state_changed = Signal(str)  # emitted when the controller updates application state text
	session_context_changed = Signal(list)  # emitted when selected-session context changes
	event_logged = Signal(str)  # emitted when the controller wants to append an event-log line
	auto_scroll_preference_changed = Signal(bool)  # emitted when event-viewer auto-scroll should change
	keep_logs_preference_changed = Signal(bool)  # emitted when the keep-logs preference should change

	def __init__(self, window: MainWindow, engine_service: object | None = None) -> None:
		super().__init__(window)
		self._window = window
		self._engine_service = engine_service

		self._wire_output_signals()
		self._wire_ui_signals()

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

	def _wire_ui_signals(self) -> None:
		self._window.session_list_widget.selection_changed.connect(
			self._on_session_selection_changed
		)
		self._window.session_created.connect(self._on_session_created)
		self._window.create_kafka_session_requested.connect(self._on_create_kafka_session_requested)
		self._window.start_session_requested.connect(self._on_start_session_requested)
		self._window.stop_session_requested.connect(self._on_stop_session_requested)
		self._window.restart_session_requested.connect(self._on_restart_session_requested)
		self._window.create_message_requested.connect(self._on_create_message_requested)
		self._window.load_message_requested.connect(self._on_load_message_requested)
		self._window.save_message_requested.connect(self._on_save_message_requested)
		self._window.edit_message_requested.connect(self._on_edit_message_requested)
		self._window.send_current_message_requested.connect(self._on_send_current_message_requested)
		self._window.send_batch_requested.connect(self._on_send_batch_requested)
		self._window.auto_scroll_toggled.connect(self._on_auto_scroll_toggled)
		self._window.keep_logs_toggled.connect(self._on_keep_logs_toggled)

	@Slot(list)
	def _on_session_selection_changed(self, session_ids: list[str]) -> None:
		self.session_context_changed.emit(session_ids)

	@Slot(dict)
	def _on_session_created(self, config: dict[str, object]) -> None:
		sender_comp_id = str(config.get("sender_comp_id") or "SENDER")
		target_comp_id = str(config.get("target_comp_id") or "TARGET")
		fix_version = str(config.get("fix_version") or "FIX.4.4")
		session_type = str(config.get("session_type") or "Initiator")

		self.application_state_changed.emit("Application: Session created")
		self.status_message_changed.emit("New session was created")
		self.event_logged.emit(
			"[session] Controller registered new session: "
			f"{sender_comp_id}->{target_comp_id} ({fix_version} {session_type})"
		)

	@Slot()
	def _on_create_kafka_session_requested(self) -> None:
		self.event_logged.emit("[console] Kafka session dialog is not implemented yet.")

	@Slot()
	def _on_start_session_requested(self) -> None:
		self.event_logged.emit("[session] Placeholder start session requested.")

	@Slot()
	def _on_stop_session_requested(self) -> None:
		self.event_logged.emit("[session] Placeholder stop session requested.")

	@Slot()
	def _on_restart_session_requested(self) -> None:
		self.event_logged.emit("[session] Placeholder restart session requested.")

	@Slot()
	def _on_create_message_requested(self) -> None:
		self.event_logged.emit("[console] Placeholder create message requested.")

	@Slot()
	def _on_load_message_requested(self) -> None:
		self.event_logged.emit("[console] Placeholder load message requested.")

	@Slot()
	def _on_save_message_requested(self) -> None:
		self.event_logged.emit("[console] Placeholder save message requested.")

	@Slot()
	def _on_edit_message_requested(self) -> None:
		self.event_logged.emit("[console] Placeholder edit message requested.")

	@Slot()
	def _on_send_current_message_requested(self) -> None:
		self.event_logged.emit("[outgoing] Placeholder send current message requested.")

	@Slot()
	def _on_send_batch_requested(self) -> None:
		self.event_logged.emit("[outgoing] Placeholder send batch requested.")

	@Slot(bool)
	def _on_auto_scroll_toggled(self, checked: bool) -> None:
		self.auto_scroll_preference_changed.emit(checked)

	@Slot(bool)
	def _on_keep_logs_toggled(self, checked: bool) -> None:
		self.keep_logs_preference_changed.emit(checked)
