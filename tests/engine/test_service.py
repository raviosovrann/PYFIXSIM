from __future__ import annotations

from typing import cast

from src.config.session_config import SessionConfig
from src.engine.service import (
    EngineMessageEvent,
    FIXEngineService,
    MessageDirection,
)
from src.engine.session import SessionConnectionError, SessionState


class _FakeSession:
    def __init__(self, config: SessionConfig, *, fail_on_logon: bool = False) -> None:
        self._config = config
        self._fail_on_logon = fail_on_logon
        self.state = SessionState.DISCONNECTED
        self.calls: list[str] = []
        self.close_reasons: list[str | None] = []

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
    service = FIXEngineService(session_factory=_FakeSession)
    service.register_state_change_handler(observed_states.append)
    service.register_outbound_message_handler(outbound_events.append)

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
    assert outbound_events[0].raw_message == "35=A"


def test_close_session_emits_logout_and_disconnected_state() -> None:
    observed_states: list[SessionState] = []
    outbound_events: list[EngineMessageEvent] = []
    service = FIXEngineService(session_factory=_FakeSession)
    service.register_state_change_handler(observed_states.append)
    service.register_outbound_message_handler(outbound_events.append)

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
