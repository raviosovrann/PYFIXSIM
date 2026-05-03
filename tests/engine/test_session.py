from __future__ import annotations

import socket

import pytest

from src.config.session_config import SessionConfig
from src.engine.session import FIXSession, SessionState, SessionStateError


class _FakeSocket:
    def __init__(self) -> None:
        self.sent_payloads: list[bytes] = []
        self.shutdown_called = False
        self.close_called = False

    def sendall(self, payload: bytes) -> None:
        self.sent_payloads.append(payload)

    def shutdown(self, how: int) -> None:
        assert how == socket.SHUT_RDWR
        self.shutdown_called = True

    def close(self) -> None:
        self.close_called = True


def _build_session_config() -> SessionConfig:
    return SessionConfig(
        sender_comp_id="CLIENT",
        target_comp_id="SERVER",
        host="127.0.0.1",
        port=9876,
    )


def test_connect_and_disconnect_transition_session_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_socket = _FakeSocket()
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: fake_socket,
    )
    session = FIXSession(_build_session_config())

    session.connect()

    assert session.state is SessionState.CONNECTED
    assert session.is_connected is True

    session.disconnect()

    assert session.state is SessionState.DISCONNECTED
    assert session.is_connected is False
    assert fake_socket.shutdown_called is True
    assert fake_socket.close_called is True


def test_logon_sends_fix_logon_message_and_activates_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_socket = _FakeSocket()
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: fake_socket,
    )
    session = FIXSession(_build_session_config())

    session.connect()
    session.logon()

    assert session.state is SessionState.ACTIVE
    assert session.out_seq_num == 2
    assert len(fake_socket.sent_payloads) == 1
    assert b"35=A" in fake_socket.sent_payloads[0]
    assert b"49=CLIENT" in fake_socket.sent_payloads[0]
    assert b"56=SERVER" in fake_socket.sent_payloads[0]
    assert b"34=1" in fake_socket.sent_payloads[0]
    assert b"98=0" in fake_socket.sent_payloads[0]
    assert b"108=30" in fake_socket.sent_payloads[0]


def test_logout_sends_fix_logout_message_and_sets_logging_out_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_socket = _FakeSocket()
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: fake_socket,
    )
    session = FIXSession(_build_session_config())

    session.connect()
    session.logon()
    session.logout("bye")

    assert session.state is SessionState.LOGGING_OUT
    assert session.out_seq_num == 3
    assert len(fake_socket.sent_payloads) == 2
    assert b"35=5" in fake_socket.sent_payloads[1]
    assert b"34=2" in fake_socket.sent_payloads[1]
    assert b"58=bye" in fake_socket.sent_payloads[1]


def test_close_sends_logout_before_disconnecting_active_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_socket = _FakeSocket()
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: fake_socket,
    )
    session = FIXSession(_build_session_config())

    session.connect()
    session.logon()
    session.close()

    assert session.state is SessionState.DISCONNECTED
    assert len(fake_socket.sent_payloads) == 2
    assert b"35=A" in fake_socket.sent_payloads[0]
    assert b"35=5" in fake_socket.sent_payloads[1]
    assert fake_socket.shutdown_called is True
    assert fake_socket.close_called is True


def test_logon_requires_connected_session() -> None:
    session = FIXSession(_build_session_config())

    with pytest.raises(SessionStateError):
        session.logon()
