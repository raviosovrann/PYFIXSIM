from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QListWidget,
    QPlainTextEdit,
)
from PySide6.QtTest import QTest
import simplefix  # type: ignore[import-untyped]

import src.ui.controller as controller_module
from src.config.session_config import SessionConfig, save_config
from src.engine.local_acceptor import LocalFIXAcceptor
from src.engine.service import FIXEngineService
from src.engine.session import SessionConnectionError, SessionState
from src.ui.main_window import MainWindow

_WAIT_TIMEOUT = 5.0
_POLL_INTERVAL_MS = 10


def _wait_for_qt(
    qapp: QApplication,
    predicate: Callable[[], bool],
    *,
    timeout: float = _WAIT_TIMEOUT,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        QTest.qWait(_POLL_INTERVAL_MS)

    qapp.processEvents()
    return predicate()


def _valid_fix_message(*, cl_ord_id: str, msg_type: str = "D") -> str:
    return (
        f"8=FIX.4.4\x019=148\x0135={msg_type}\x0134=1080\x0149=TESTBUY1\x01"
        f"52=20180920-18:14:19.508\x0156=TESTSELL1\x0111={cl_ord_id}\x0115=USD\x0121=2\x01"
        "40=1\x0154=1\x0155=MSFT\x0160=20180920-18:14:19.492\x0110=092\x01"
    )


class _FakeSession:
    def __init__(
        self,
        config: SessionConfig,
        *,
        fail_on_logon: bool = False,
        fail_on_close: bool = False,
    ) -> None:
        self._config = config
        self._fail_on_logon = fail_on_logon
        self._fail_on_close = fail_on_close
        self.state = SessionState.DISCONNECTED
        self.calls: list[str] = []
        self.close_reasons: list[str | None] = []
        self.sent_messages: list[object] = []
        self._next_seq_num = config.out_seq_num
        self._inbound_handlers: list[object] = []

    @property
    def config(self) -> SessionConfig:
        return self._config

    def connect(self) -> None:
        self.calls.append("connect")
        self.state = SessionState.CONNECTED

    def logon(self) -> None:
        self.calls.append("logon")
        if self._fail_on_logon:
            raise SessionConnectionError("logon failed")
        self._next_seq_num += 1
        self.state = SessionState.ACTIVE

    def close(self, reason: str | None = None) -> None:
        self.calls.append("close")
        self.close_reasons.append(reason)
        if self._fail_on_close:
            raise SessionConnectionError("close failed")
        self.state = SessionState.DISCONNECTED

    def next_out_seq_num(self) -> int:
        msg_seq_num = self._next_seq_num
        self._next_seq_num += 1
        return msg_seq_num

    def register_inbound_message_handler(self, handler: object) -> None:
        self._inbound_handlers.append(handler)

    def send(self, message: object) -> None:
        self.calls.append("send")
        self.sent_messages.append(message)

    def send_heartbeat(self, TestReqID: str | None = None) -> simplefix.FixMessage:
        self.calls.append("heartbeat")
        heartbeat = simplefix.FixMessage()
        heartbeat.append_pair(8, self._config.fix_version)
        heartbeat.append_pair(35, "0")
        heartbeat.append_pair(49, self._config.sender_comp_id)
        heartbeat.append_pair(56, self._config.target_comp_id)
        heartbeat.append_pair(34, str(self.next_out_seq_num()))
        heartbeat.append_pair(52, "20260506-12:30:45.000")
        if TestReqID:
            heartbeat.append_pair(112, TestReqID)
        self.sent_messages.append(heartbeat)
        return heartbeat


def _create_config_file(
    tmp_path: Path,
    *,
    sender_comp_id: str = "CLIENT",
    target_comp_id: str = "SERVER",
    host: str = "127.0.0.1",
    port: int = 9876,
) -> Path:
    return save_config(
        SessionConfig(
            sender_comp_id=sender_comp_id,
            target_comp_id=target_comp_id,
            host=host,
            port=port,
        ),
        tmp_path / "session.cfg",
    )


def test_app_controller_updates_selected_session_context_and_logs_service_events(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    service = FIXEngineService(session_factory=_FakeSession)
    window = MainWindow(
        engine_service=service,
        config_path=_create_config_file(tmp_path),
    )
    window.show()
    qapp.processEvents()

    list_widget = window.findChild(QListWidget, "sessionList")
    assert list_widget is not None
    assert window.app_controller is not None

    first_item = list_widget.item(0)
    first_item.setSelected(True)
    qapp.processEvents()

    assert window.session_state_label.text() == "Session: CLIENT->SERVER"

    window.send_message_tab.set_message_text(
        "8=FIX.4.2\x0135=0\x0149=CLIENT\x0156=SERVER\x0134=1\x0152=20260504-12:30:45.000\x01"
    )
    window.send_batch_requested.emit()
    qapp.processEvents()

    assert (
        "[outgoing] CLIENT->SERVER | Sent Logon" in window.events_viewer.toPlainText()
    )
    assert (
        "[outgoing] CLIENT->SERVER | Sent FIX message 35=0"
        in window.events_viewer.toPlainText()
    )

    window.close()


def test_app_controller_applies_session_created_updates(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    service = FIXEngineService(session_factory=_FakeSession)
    window = MainWindow(
        engine_service=service,
        config_path=_create_config_file(tmp_path),
    )
    window.show()
    qapp.processEvents()

    window.session_created.emit(
        {
            "sender_comp_id": "BUY_SIDE",
            "target_comp_id": "SELL_SIDE",
            "fix_version": "FIX.4.4",
            "session_type": "Initiator",
            "remote_host": "127.0.0.1",
            "remote_port": 9878,
        }
    )
    qapp.processEvents()

    assert window.application_state_label.text() == "Application: Session created"
    assert (
        "New session was created: BUY_SIDE->SELL_SIDE"
        in window.events_viewer.toPlainText()
    )

    window.close()


def test_app_controller_start_and_stop_operate_against_engine_service(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    service = FIXEngineService(session_factory=_FakeSession)
    window = MainWindow(
        engine_service=service,
        config_path=_create_config_file(tmp_path),
    )
    window.show()
    qapp.processEvents()

    list_widget = window.findChild(QListWidget, "sessionList")
    assert list_widget is not None

    first_item = list_widget.item(0)
    first_item.setSelected(True)
    qapp.processEvents()

    window.start_session_requested.emit()
    qapp.processEvents()

    session = cast(_FakeSession, service.active_session)
    assert session.calls == ["connect", "logon"]
    assert window.application_state_label.text() == "Application: Session active"

    window.stop_session_requested.emit()
    qapp.processEvents()

    assert session.calls == ["connect", "logon", "close"]
    assert "Client requested stop" in str(session.close_reasons[-1])

    window.close()


def test_app_controller_reuses_active_session_when_start_requested_twice(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    service = FIXEngineService(session_factory=_FakeSession)
    window = MainWindow(
        engine_service=service,
        config_path=_create_config_file(tmp_path),
    )
    window.show()
    qapp.processEvents()

    list_widget = window.findChild(QListWidget, "sessionList")
    assert list_widget is not None

    first_item = list_widget.item(0)
    first_item.setSelected(True)
    qapp.processEvents()

    window.start_session_requested.emit()
    qapp.processEvents()

    session = cast(_FakeSession, service.active_session)
    assert session.calls == ["connect", "logon"]

    window.start_session_requested.emit()
    qapp.processEvents()

    assert cast(_FakeSession, service.active_session) is session
    assert session.calls == ["connect", "logon"]

    window.close()


def test_app_controller_reports_load_message_read_errors(
    qapp: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow(config_path=_create_config_file(tmp_path))
    window.show()
    qapp.processEvents()

    monkeypatch.setattr(
        controller_module.QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: ("broken.fix", "FIX text (*.fix *.txt)"),
    )
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda self, encoding="utf-8": (_ for _ in ()).throw(OSError("boom read")),
    )

    window.load_message_requested.emit()
    qapp.processEvents()

    assert "boom read" in window.statusBar().currentMessage()
    assert "[console] boom read" in window.events_viewer.toPlainText()

    window.close()


def test_app_controller_reports_save_message_write_errors(
    qapp: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow(config_path=_create_config_file(tmp_path))
    window.show()
    qapp.processEvents()

    window.send_message_tab.set_message_text("8=FIX.4.2|35=0|")

    monkeypatch.setattr(
        controller_module.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: ("broken.fix", "FIX text (*.fix *.txt)"),
    )
    monkeypatch.setattr(
        Path,
        "write_text",
        lambda self, text, encoding="utf-8": (_ for _ in ()).throw(OSError("boom write")),
    )

    window.save_message_requested.emit()
    qapp.processEvents()

    assert "boom write" in window.statusBar().currentMessage()
    assert "[console] boom write" in window.events_viewer.toPlainText()

    window.close()


def test_app_controller_reports_session_switch_close_errors(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    service = FIXEngineService(
        session_factory=lambda config: _FakeSession(
            config,
            fail_on_close=config.sender_comp_id == "CLIENT",
        )
    )
    window = MainWindow(
        engine_service=service,
        config_path=_create_config_file(tmp_path),
    )
    window.show()
    qapp.processEvents()

    list_widget = window.findChild(QListWidget, "sessionList")
    assert list_widget is not None

    first_item = list_widget.item(0)
    first_item.setSelected(True)
    qapp.processEvents()

    window.start_session_requested.emit()
    qapp.processEvents()

    window.session_created.emit(
        {
            "sender_comp_id": "BUY_SIDE",
            "target_comp_id": "SELL_SIDE",
            "fix_version": "FIX.4.4",
            "session_type": "Initiator",
            "remote_host": "127.0.0.1",
            "remote_port": 9878,
        }
    )
    qapp.processEvents()

    list_widget.item(1).setSelected(True)
    qapp.processEvents()

    window.start_session_requested.emit()
    qapp.processEvents()

    assert "close failed" in window.statusBar().currentMessage()
    assert "[console] close failed" in window.events_viewer.toPlainText()

    window.close()


def test_app_controller_opens_structured_editor_and_updates_current_message(
    qapp: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow(config_path=_create_config_file(tmp_path))
    window.show()
    qapp.processEvents()

    window.send_message_tab.set_message_text(
        f"{_valid_fix_message(cl_ord_id='ORDER_1', msg_type='D')}\n"
        f"{_valid_fix_message(cl_ord_id='ORDER_2', msg_type='F')}"
    )
    window.workspace_tabs.setCurrentIndex(2)

    editor = window.findChild(QPlainTextEdit, "sendMessageEditor")
    assert editor is not None

    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.Start)
    cursor.movePosition(cursor.MoveOperation.Down)
    editor.setTextCursor(cursor)
    qapp.processEvents()

    def _accept_with_changes(dialog) -> int:
        table = dialog.table_widget()
        for row in range(table.rowCount()):
            tag_item = table.item(row, 0)
            value_item = table.item(row, 2)
            if tag_item is None or value_item is None:
                continue
            if tag_item.text() == "11":
                value_item.setText("ORDER_99")
                break
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(
        controller_module.TableViewEditor,
        "exec",
        _accept_with_changes,
    )

    window.edit_message_requested.emit()
    qapp.processEvents()

    assert window.workspace_tabs.currentWidget() is window.send_message_tab
    assert editor.hasFocus() is True
    assert window.send_message_tab.message_text() == (
        f"{_valid_fix_message(cl_ord_id='ORDER_1', msg_type='D')}\n"
        f"{_valid_fix_message(cl_ord_id='ORDER_99', msg_type='F')}"
    )
    assert (
        window.statusBar().currentMessage()
        == "Updated FIX message from structured editor"
    )

    window.close()


def test_app_controller_creates_soh_delimited_fix_message(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    window = MainWindow(config_path=_create_config_file(tmp_path))
    window.show()
    qapp.processEvents()

    list_widget = window.findChild(QListWidget, "sessionList")
    assert list_widget is not None

    first_item = list_widget.item(0)
    first_item.setSelected(True)
    qapp.processEvents()

    window.create_message_requested.emit()
    qapp.processEvents()

    created_message = window.send_message_tab.message_text()
    assert "\x01" in created_message
    assert "|" not in created_message
    assert created_message.startswith("8=FIX.4.2\x01")
    assert (
        window.statusBar().currentMessage()
        == "Created a NewOrderSingle template in the editor"
    )

    window.close()


def test_app_controller_routes_created_orders_through_typed_send_path(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    service = FIXEngineService(session_factory=_FakeSession)
    window = MainWindow(
        engine_service=service,
        config_path=_create_config_file(tmp_path),
    )
    window.show()
    qapp.processEvents()

    list_widget = window.findChild(QListWidget, "sessionList")
    assert list_widget is not None

    first_item = list_widget.item(0)
    first_item.setSelected(True)
    qapp.processEvents()

    window.create_message_requested.emit()
    window.send_current_message_requested.emit()
    qapp.processEvents()

    event_text = window.events_viewer.toPlainText()
    assert "NewOrderSingle 11=ORDER_" in event_text
    assert "Sent FIX message 35=D" not in event_text

    session = cast(_FakeSession, service.active_session)
    assert session is not None
    assert any(
        b"35=D" in bytes(cast(simplefix.FixMessage, message).encode())
        for message in session.sent_messages
    )

    window.close()


def test_app_controller_logs_execution_report_from_real_acceptor(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    acceptor = LocalFIXAcceptor(port=0)
    acceptor.start()
    window = MainWindow(
        config_path=_create_config_file(
            tmp_path,
            host="127.0.0.1",
            port=acceptor.bound_port,
        )
    )
    window.show()

    try:
        qapp.processEvents()
        list_widget = window.findChild(QListWidget, "sessionList")
        assert list_widget is not None

        first_item = list_widget.item(0)
        first_item.setSelected(True)
        qapp.processEvents()

        window.start_session_requested.emit()
        window.create_message_requested.emit()
        window.send_current_message_requested.emit()

        assert _wait_for_qt(
            qapp,
            lambda: "ExecutionReport" in window.events_viewer.toPlainText(),
        )

        assert "ExecutionReport" in window.events_viewer.toPlainText()
        assert "Connected to 127.0.0.1" in window.events_viewer.toPlainText()
        assert "Sent Logon" in window.events_viewer.toPlainText()
        assert "NewOrderSingle" in window.events_viewer.toPlainText()
        assert "35=8" in window.events_viewer.toPlainText()
        assert "55=AAPL" in window.events_viewer.toPlainText()
    finally:
        window.close()
        acceptor.stop()


def test_app_controller_edits_nearest_message_when_cursor_is_on_trailing_blank_line(
    qapp: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow(config_path=_create_config_file(tmp_path))
    window.show()
    qapp.processEvents()

    window.send_message_tab.set_message_text(
        f"{_valid_fix_message(cl_ord_id='ORDER_1', msg_type='D')}\n"
        f"{_valid_fix_message(cl_ord_id='ORDER_2', msg_type='F')}\n"
    )

    editor = window.findChild(QPlainTextEdit, "sendMessageEditor")
    assert editor is not None

    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    qapp.processEvents()

    def _accept_with_changes(dialog) -> int:
        table = dialog.table_widget()
        for row in range(table.rowCount()):
            tag_item = table.item(row, 0)
            value_item = table.item(row, 2)
            if tag_item is None or value_item is None:
                continue
            if tag_item.text() == "11":
                value_item.setText("ORDER_99")
                break
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(
        controller_module.TableViewEditor,
        "exec",
        _accept_with_changes,
    )

    window.edit_message_requested.emit()
    qapp.processEvents()

    assert window.send_message_tab.message_text() == (
        f"{_valid_fix_message(cl_ord_id='ORDER_1', msg_type='D')}\n"
        f"{_valid_fix_message(cl_ord_id='ORDER_99', msg_type='F')}\n"
    )
    assert (
        window.statusBar().currentMessage()
        == "Updated FIX message from structured editor"
    )

    window.close()


def test_app_controller_rejects_structured_edit_for_single_character_input(
    qapp: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow(config_path=_create_config_file(tmp_path))
    window.show()
    qapp.processEvents()

    window.send_message_tab.set_message_text("\x01")

    dialog_calls: list[str] = []

    def _record_dialog_open(_dialog: object) -> int:
        dialog_calls.append("opened")
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(
        controller_module.TableViewEditor,
        "exec",
        _record_dialog_open,
    )

    window.edit_message_requested.emit()
    qapp.processEvents()

    assert dialog_calls == []
    assert (
        window.statusBar().currentMessage()
        == "Structured editor requires a complete FIX message."
    )

    window.close()


def test_app_controller_rejects_structured_edit_for_malformed_fix_fields(
    qapp: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow(config_path=_create_config_file(tmp_path))
    window.show()
    qapp.processEvents()

    window.send_message_tab.set_message_text(
        "8=FIX.4.4\x019=148\x0135=D\x0134=1080\x0149=TESTBUY1\x0152=20180920-18:14:19.508"
        "\x0156=TESTSELL1\x0111=636730640278898634\x0115=USD\x0121=2\x01=\x0140=1"
        "\x0154=1\x0155=MSFT\x0160=20180920-18:14:19.492\x0110=092\x01"
    )

    dialog_calls: list[str] = []

    def _record_dialog_open(_dialog: object) -> int:
        dialog_calls.append("opened")
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(
        controller_module.TableViewEditor,
        "exec",
        _record_dialog_open,
    )

    window.edit_message_requested.emit()
    qapp.processEvents()

    assert dialog_calls == []
    assert (
        window.statusBar().currentMessage()
        == "Structured editor requires populated numeric tag=value FIX fields."
    )

    window.close()


def test_app_controller_rejects_structured_edit_when_required_tags_are_missing(
    qapp: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow(config_path=_create_config_file(tmp_path))
    window.show()
    qapp.processEvents()

    window.send_message_tab.set_message_text("8=FIX.4.4\x0135=D\x0111=ORDER_42\x01")

    dialog_calls: list[str] = []

    def _record_dialog_open(_dialog: object) -> int:
        dialog_calls.append("opened")
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(
        controller_module.TableViewEditor,
        "exec",
        _record_dialog_open,
    )

    window.edit_message_requested.emit()
    qapp.processEvents()

    assert dialog_calls == []
    assert (
        window.statusBar().currentMessage()
        == (
            "Structured editor requires FIX tags 8, 9, 34, 35, 49, 52, 56, 60, "
            "and 10 with values."
        )
    )

    window.close()


def test_app_controller_rejects_structured_edit_for_pipe_delimited_message(
    qapp: QApplication,
    tmp_path: Path,
    monkeypatch,
) -> None:
    window = MainWindow(config_path=_create_config_file(tmp_path))
    window.show()
    qapp.processEvents()

    window.send_message_tab.set_message_text(
        "8=FIX.4.2|9=144|35=D|49=TEST_SENDER1|56=TEST_TARGET|34=1|"
        "52=20260506-03:29:38.134|11=ORDER_232938|21=1|55=AAPL|54=1|"
        "60=20260506-03:29:38.134|38=100|40=2|44=25.5|10=096|"
    )

    dialog_calls: list[str] = []

    def _record_dialog_open(_dialog: object) -> int:
        dialog_calls.append("opened")
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(
        controller_module.TableViewEditor,
        "exec",
        _record_dialog_open,
    )

    window.edit_message_requested.emit()
    qapp.processEvents()

    assert dialog_calls == []
    assert (
        window.statusBar().currentMessage()
        == "Structured editor requires FIX fields to be separated by <SOH> characters."
    )

    window.close()


def test_app_controller_rejects_sending_pipe_delimited_messages(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    service = FIXEngineService(session_factory=_FakeSession)
    window = MainWindow(
        engine_service=service,
        config_path=_create_config_file(tmp_path),
    )
    window.show()
    qapp.processEvents()

    list_widget = window.findChild(QListWidget, "sessionList")
    assert list_widget is not None

    first_item = list_widget.item(0)
    first_item.setSelected(True)
    qapp.processEvents()

    window.send_message_tab.set_message_text(
        "8=FIX.4.2|35=0|49=CLIENT|56=SERVER|34=1|52=20260504-12:30:45.000|"
    )
    window.send_batch_requested.emit()
    qapp.processEvents()

    assert (
        window.statusBar().currentMessage()
        == "FIX messages must use <SOH> as the field delimiter."
    )
    assert (
        "[console] FIX messages must use <SOH> as the field delimiter."
        in window.events_viewer.toPlainText()
    )
    assert service.active_session is None

    window.close()
