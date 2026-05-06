from __future__ import annotations

import socket
import threading

import pytest
import simplefix  # type: ignore[import-untyped]

from src.config.session_config import SessionConfig
from src.engine.session import FIXSession, SessionState, SessionStateError


class _FakeSocket:
    def __init__(self, recv_payloads: list[bytes] | None = None) -> None:
        self.sent_payloads: list[bytes] = []
        self.shutdown_called = False
        self.close_called = False
        self.timeout: float | None = None
        self._recv_payloads = list(recv_payloads or [])
        self._lock = threading.Lock()

    def sendall(self, payload: bytes) -> None:
        self.sent_payloads.append(payload)

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def recv(self, _buffer_size: int) -> bytes:
        with self._lock:
            if self.close_called:
                return b""
            if self._recv_payloads:
                return self._recv_payloads.pop(0)
        raise socket.timeout()

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


def test_send_requires_active_session_and_uses_reserved_sequence_number(
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

    MsgSeqNum = session.next_out_seq_num()
    message = simplefix.FixMessage()
    message.append_pair(8, "FIX.4.2")
    message.append_pair(35, "D")
    message.append_pair(34, str(MsgSeqNum))

    session.send(message)

    assert MsgSeqNum == 2
    assert session.out_seq_num == 3
    assert len(fake_socket.sent_payloads) == 2
    assert b"35=D" in fake_socket.sent_payloads[1]


def test_receive_loop_dispatches_inbound_messages_and_updates_sequence_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inbound_message_received = threading.Event()
    observed_messages: list[simplefix.FixMessage] = []
    fake_socket = _FakeSocket(
        recv_payloads=[
            b"8=FIX.4.2\x019=52\x0135=0\x0134=2\x0149=SERVER\x0156=CLIENT\x0152=20260506-12:30:45.000\x0110=000\x01"
        ]
    )
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: fake_socket,
    )
    session = FIXSession(_build_session_config())
    session.register_inbound_message_handler(
        lambda message: (observed_messages.append(message), inbound_message_received.set())
    )

    session.connect()

    assert inbound_message_received.wait(1.0) is True
    assert len(observed_messages) == 1
    assert observed_messages[0].get(35) == b"0"
    assert session.in_seq_num == 3

    session.disconnect()
