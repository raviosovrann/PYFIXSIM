from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtWidgets import QApplication, QListWidget

from src.config.session_config import SessionConfig, save_config
from src.engine.service import FIXEngineService
from src.engine.session import SessionConnectionError, SessionState
from src.ui.main_window import MainWindow


class _FakeSession:
    def __init__(self, config: SessionConfig, *, fail_on_logon: bool = False) -> None:
        self._config = config
        self._fail_on_logon = fail_on_logon
        self.state = SessionState.DISCONNECTED
        self.calls: list[str] = []
        self.close_reasons: list[str | None] = []
        self.sent_messages: list[object] = []
        self._next_seq_num = config.out_seq_num

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
        self.state = SessionState.ACTIVE

    def close(self, reason: str | None = None) -> None:
        self.calls.append("close")
        self.close_reasons.append(reason)
        self.state = SessionState.DISCONNECTED

    def next_out_seq_num(self) -> int:
        msg_seq_num = self._next_seq_num
        self._next_seq_num += 1
        return msg_seq_num

    def send(self, message: object) -> None:
        self.calls.append("send")
        self.sent_messages.append(message)


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
        "8=FIX.4.2|35=0|49=CLIENT|56=SERVER|34=1|52=20260504-12:30:45.000|"
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
