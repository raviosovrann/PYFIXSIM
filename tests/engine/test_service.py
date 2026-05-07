from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from typing import cast

import pytest
import simplefix  # type: ignore[import-untyped]

from src.config.session_config import SessionConfig
from src.engine.service import (
    EngineMessageEvent,
    FIXEngineService,
    MessageDirection,
)
from src.engine.session import SessionConnectionError, SessionState
from src.messages.order import ExecutionReport, MessageValidationError, NewOrderSingle


class _FakeSession:
    def __init__(self, config: SessionConfig, *, fail_on_logon: bool = False) -> None:
        self._config = config
        self._fail_on_logon = fail_on_logon
        self.state = SessionState.DISCONNECTED
        self.calls: list[str] = []
        self.close_reasons: list[str | None] = []
        self.sent_messages: list[simplefix.FixMessage] = []
        self._next_seq_num = config.out_seq_num
        self._inbound_handlers: list[Callable[[simplefix.FixMessage], None]] = []

    @property
    def config(self) -> SessionConfig:
        return self._config

    def connect(self) -> None:
        self.calls.append("connect")
        self.state = SessionState.CONNECTED

    def logon(self) -> simplefix.FixMessage:
        self.calls.append("logon")
        if self._fail_on_logon:
            raise SessionConnectionError("logon failed")
        logon = simplefix.FixMessage()
        logon.append_pair(8, self._config.fix_version)
        logon.append_pair(35, "A")
        logon.append_pair(49, self._config.sender_comp_id)
        logon.append_pair(56, self._config.target_comp_id)
        logon.append_pair(34, str(self._next_seq_num))
        logon.append_pair(
            52,
            datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:-3],
        )
        logon.append_pair(98, "0")
        logon.append_pair(108, str(self._config.heartbeat_interval))
        self._next_seq_num += 1
        self.state = SessionState.ACTIVE
        return logon

    def close(self, reason: str | None = None) -> None:
        self.calls.append("close")
        self.close_reasons.append(reason)
        self.state = SessionState.DISCONNECTED

    def next_out_seq_num(self) -> int:
        MsgSeqNum = self._next_seq_num
        self._next_seq_num += 1
        return MsgSeqNum

    def register_inbound_message_handler(
        self,
        handler: Callable[[simplefix.FixMessage], None],
    ) -> None:
        self._inbound_handlers.append(handler)

    def send(self, message: simplefix.FixMessage) -> None:
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
        heartbeat.append_pair(
            52,
            datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:-3],
        )
        if TestReqID:
            heartbeat.append_pair(112, TestReqID)
        self.sent_messages.append(heartbeat)
        return heartbeat

    def emit_inbound_message(self, message: simplefix.FixMessage) -> None:
        for handler in list(self._inbound_handlers):
            handler(message)


def _build_session_config() -> SessionConfig:
    return SessionConfig(
        sender_comp_id="CLIENT",
        target_comp_id="SERVER",
        host="127.0.0.1",
        port=9876,
    )


def test_create_session_stores_active_session_and_emits_initial_state() -> None:
    observed_states: list[SessionState] = []
    service = FIXEngineService(session_factory=_FakeSession)
    service.register_state_change_handler(observed_states.append)

    session = service.create_session(_build_session_config())

    assert service.active_session is session
    assert service.active_config == _build_session_config()
    assert observed_states == [SessionState.DISCONNECTED]


def test_open_session_accepts_mapping_and_emits_state_and_outbound_hooks() -> None:
    observed_states: list[SessionState] = []
    outbound_events: list[EngineMessageEvent] = []
    system_events: list[EngineMessageEvent] = []
    service = FIXEngineService(session_factory=_FakeSession)
    service.register_state_change_handler(observed_states.append)
    service.register_outbound_message_handler(outbound_events.append)
    service.register_system_message_handler(system_events.append)

    session = cast(
        _FakeSession,
        service.open_session(_build_session_config().to_dict()),
    )

    assert session.calls == ["connect", "logon"]
    assert observed_states == [
        SessionState.DISCONNECTED,
        SessionState.CONNECTED,
        SessionState.ACTIVE,
    ]
    assert len(outbound_events) == 1
    assert outbound_events[0].direction is MessageDirection.OUTBOUND
    assert outbound_events[0].session_id == "CLIENT->SERVER"
    assert outbound_events[0].message == "Sent Logon"
    assert outbound_events[0].raw_message is not None
    assert "35=A" in outbound_events[0].raw_message
    assert "49=CLIENT" in outbound_events[0].raw_message
    assert "56=SERVER" in outbound_events[0].raw_message
    assert len(system_events) == 1
    assert system_events[0].direction is MessageDirection.SYSTEM
    assert system_events[0].message == "Connected to 127.0.0.1:9876"


def test_close_session_emits_logout_and_disconnected_state() -> None:
    observed_states: list[SessionState] = []
    outbound_events: list[EngineMessageEvent] = []
    system_events: list[EngineMessageEvent] = []
    service = FIXEngineService(session_factory=_FakeSession)
    service.register_state_change_handler(observed_states.append)
    service.register_outbound_message_handler(outbound_events.append)
    service.register_system_message_handler(system_events.append)

    session = cast(
        _FakeSession,
        service.open_session(_build_session_config()),
    )
    observed_states.clear()
    outbound_events.clear()

    service.close_session("bye")

    assert service.active_session is session
    assert session.close_reasons == ["bye"]
    assert session.calls == ["connect", "logon", "close"]
    assert observed_states == [SessionState.DISCONNECTED]
    assert len(outbound_events) == 1
    assert outbound_events[0].direction is MessageDirection.OUTBOUND
    assert outbound_events[0].message == "Sent Logout"
    assert outbound_events[0].raw_message == "35=5"
    assert len(system_events) == 2
    assert system_events[-1].message == "Disconnected from 127.0.0.1:9876"


def test_record_inbound_message_emits_event_for_active_session() -> None:
    inbound_events: list[EngineMessageEvent] = []
    service = FIXEngineService(session_factory=_FakeSession)
    service.register_inbound_message_handler(inbound_events.append)
    service.create_session(_build_session_config())

    event = service.record_inbound_message(b"8=FIX.4.2\x0135=8\x01")

    assert event.direction is MessageDirection.INBOUND
    assert event.session_id == "CLIENT->SERVER"
    assert event.message == "Received inbound FIX message"
    assert event.raw_message == "8=FIX.4.2\x0135=8\x01"
    assert inbound_events == [event]


def test_open_session_emits_error_hook_and_reraises_failures() -> None:
    observed_errors: list[Exception] = []

    def _factory(config: SessionConfig) -> _FakeSession:
        return _FakeSession(config, fail_on_logon=True)

    service = FIXEngineService(session_factory=_factory)
    service.register_error_handler(observed_errors.append)

    try:
        service.open_session(_build_session_config())
    except SessionConnectionError as error:
        assert str(error) == "logon failed"
    else:
        raise AssertionError("Expected SessionConnectionError")

    assert len(observed_errors) == 1
    assert isinstance(observed_errors[0], SessionConnectionError)


def test_send_new_order_single_sends_message_and_emits_outbound_event() -> None:
    outbound_events: list[EngineMessageEvent] = []
    service = FIXEngineService(session_factory=_FakeSession)
    service.register_outbound_message_handler(outbound_events.append)

    session = cast(
        _FakeSession,
        service.open_session(_build_session_config()),
    )

    event = service.send_new_order_single(
        NewOrderSingle(
            ClOrdID="ORDER_1",
            Symbol="AAPL",
            Side="1",
            OrderQty=100,
            OrdType="2",
            Price=25.5,
        )
    )

    assert session.calls == ["connect", "logon", "send"]
    assert len(session.sent_messages) == 1
    assert b"35=D" in bytes(session.sent_messages[0].encode())
    assert b"11=ORDER_1" in bytes(session.sent_messages[0].encode())
    assert event.direction is MessageDirection.OUTBOUND
    assert event.message == "NewOrderSingle 11=ORDER_1"
    assert event.raw_message is not None
    assert "35=D" in event.raw_message
    assert outbound_events[-1] == event


def test_handle_execution_report_emits_inbound_event_and_report_hook() -> None:
    inbound_events: list[EngineMessageEvent] = []
    execution_reports: list[ExecutionReport] = []
    service = FIXEngineService(session_factory=_FakeSession)
    service.register_inbound_message_handler(inbound_events.append)
    service.register_execution_report_handler(execution_reports.append)
    service.open_session(_build_session_config())

    message = simplefix.FixMessage()
    message.append_pair(8, "FIX.4.2")
    message.append_pair(35, "8")
    message.append_pair(37, "BROKER_ORDER_1")
    message.append_pair(17, "EXEC_1")
    message.append_pair(150, "2")
    message.append_pair(39, "2")
    message.append_pair(11, "ORDER_1")
    message.append_pair(55, "AAPL")
    message.append_pair(54, "1")
    message.append_pair(38, "100")
    message.append_pair(151, "0")
    message.append_pair(14, "100")
    message.append_pair(6, "25.5")

    report = service.handle_execution_report(message)

    assert report.ClOrdID == "ORDER_1"
    assert report.OrderID == "BROKER_ORDER_1"
    assert len(inbound_events) == 1
    assert inbound_events[0].direction is MessageDirection.INBOUND
    assert inbound_events[0].message == "ExecutionReport 11=ORDER_1"
    assert inbound_events[0].raw_message is not None
    assert "35=8" in inbound_events[0].raw_message
    assert execution_reports == [report]


def test_handle_execution_report_emits_error_hook_for_invalid_payload() -> None:
    observed_errors: list[Exception] = []
    service = FIXEngineService(session_factory=_FakeSession)
    service.register_error_handler(observed_errors.append)
    service.open_session(_build_session_config())

    with pytest.raises(MessageValidationError) as exc_info:
        service.handle_execution_report("8=FIX.4.2|35=D|11=ORDER_1|")

    assert exc_info.value.tag == 35
    assert len(observed_errors) == 1
    assert isinstance(observed_errors[0], MessageValidationError)


def test_send_raw_message_sends_generic_fix_payload_and_emits_outbound_event() -> None:
    outbound_events: list[EngineMessageEvent] = []
    service = FIXEngineService(session_factory=_FakeSession)
    service.register_outbound_message_handler(outbound_events.append)
    session = cast(_FakeSession, service.open_session(_build_session_config()))

    event = service.send_raw_message(
        "8=FIX.4.2|35=0|49=CLIENT|56=SERVER|34=2|52=20260504-12:30:45.000|"
    )

    assert session.calls == ["connect", "logon", "send"]
    assert len(session.sent_messages) == 1
    assert b"35=0" in bytes(session.sent_messages[0].encode())
    assert b"49=CLIENT" in bytes(session.sent_messages[0].encode())
    assert b"56=SERVER" in bytes(session.sent_messages[0].encode())
    assert b"34=2" in bytes(session.sent_messages[0].encode())
    assert event.message == "Sent FIX message 35=0"
    assert event.raw_message is not None
    assert "35=0" in event.raw_message
    assert outbound_events[-1] == event


def test_session_callback_routes_execution_reports_through_service_hooks() -> None:
    inbound_events: list[EngineMessageEvent] = []
    execution_reports: list[ExecutionReport] = []
    service = FIXEngineService(session_factory=_FakeSession)
    service.register_inbound_message_handler(inbound_events.append)
    service.register_execution_report_handler(execution_reports.append)
    session = cast(_FakeSession, service.open_session(_build_session_config()))

    message = simplefix.FixMessage()
    message.append_pair(8, "FIX.4.2")
    message.append_pair(35, "8")
    message.append_pair(37, "BROKER_ORDER_2")
    message.append_pair(17, "EXEC_2")
    message.append_pair(150, "2")
    message.append_pair(39, "2")
    message.append_pair(11, "ORDER_2")
    message.append_pair(55, "MSFT")
    message.append_pair(54, "1")
    message.append_pair(38, "50")
    message.append_pair(151, "0")
    message.append_pair(14, "50")
    message.append_pair(6, "10.5")

    session.emit_inbound_message(message)

    assert len(inbound_events) == 1
    assert inbound_events[0].message == "ExecutionReport 11=ORDER_2"
    assert len(execution_reports) == 1
    assert execution_reports[0].ClOrdID == "ORDER_2"


def test_session_callback_replies_to_test_request_with_heartbeat() -> None:
    inbound_events: list[EngineMessageEvent] = []
    outbound_events: list[EngineMessageEvent] = []
    service = FIXEngineService(session_factory=_FakeSession)
    service.register_inbound_message_handler(inbound_events.append)
    service.register_outbound_message_handler(outbound_events.append)
    session = cast(_FakeSession, service.open_session(_build_session_config()))

    message = simplefix.FixMessage()
    message.append_pair(8, "FIX.4.2")
    message.append_pair(35, "1")
    message.append_pair(49, "SERVER")
    message.append_pair(56, "CLIENT")
    message.append_pair(34, "7")
    message.append_pair(52, "20260506-12:30:45.000")
    message.append_pair(112, "PING_1")

    session.emit_inbound_message(message)

    assert inbound_events[-1].message == "Received TestRequest"
    assert outbound_events[-1].message == "Sent Heartbeat"
    assert session.calls[-1] == "heartbeat"
    assert b"112=PING_1" in bytes(session.sent_messages[-1].encode())
