from __future__ import annotations

import logging
import socket
import threading
from datetime import datetime, timezone
from enum import Enum, auto

import simplefix  # type: ignore[import-untyped]

from src.config.session_config import SessionConfig

logger = logging.getLogger(__name__)

_LOGON_MSG_TYPE = "A"
_LOGOUT_MSG_TYPE = "5"
_RESET_SEQ_NUM_VALUES = {"At logon", "Always"}


class FIXSessionError(Exception):
    """Base exception for FIX session lifecycle failures."""


class SessionConnectionError(FIXSessionError):
    """Raised when the TCP session cannot connect or send data."""


class SessionStateError(FIXSessionError):
    """Raised when a session lifecycle method is called in an invalid state."""


class SessionState(Enum):
    """Explicit FIX session connection states for the V1 lifecycle."""

    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    LOGGING_ON = auto()
    ACTIVE = auto()
    LOGGING_OUT = auto()


class FIXSession:
    """Manage the V1 FIX session socket lifecycle for a single configuration."""

    def __init__(self, config: SessionConfig, connect_timeout: float = 10.0) -> None:
        self._config = config
        self._connect_timeout = connect_timeout
        self._lock = threading.Lock()
        self._state = SessionState.DISCONNECTED
        self._socket: socket.socket | None = None
        self._in_seq_num = config.in_seq_num
        self._out_seq_num = config.out_seq_num

    @property
    def config(self) -> SessionConfig:
        """Return the session configuration used by this session."""
        return self._config

    @property
    def state(self) -> SessionState:
        """Return the current session state."""
        with self._lock:
            return self._state

    @property
    def in_seq_num(self) -> int:
        """Return the next expected inbound sequence number."""
        with self._lock:
            return self._in_seq_num

    @property
    def out_seq_num(self) -> int:
        """Return the next outbound sequence number to be assigned."""
        with self._lock:
            return self._out_seq_num

    @property
    def is_connected(self) -> bool:
        """Return whether a live socket is currently attached."""
        with self._lock:
            return self._socket is not None

    def connect(self) -> None:
        """Open the TCP connection for this FIX session."""
        with self._lock:
            if self._socket is not None:
                raise SessionStateError("FIX session is already connected")
            self._transition_state_locked(SessionState.CONNECTING)

        try:
            session_socket = socket.create_connection(
                (self._config.host, self._config.port),
                timeout=self._connect_timeout,
            )
        except OSError as exc:
            with self._lock:
                self._transition_state_locked(SessionState.DISCONNECTED)
            raise SessionConnectionError(
                f"Unable to connect to {self._config.host}:{self._config.port}"
            ) from exc

        with self._lock:
            self._socket = session_socket
            self._transition_state_locked(SessionState.CONNECTED)

    def logon(self) -> None:
        """Send a FIX Logon message and mark the session active on success."""
        with self._lock:
            if self._socket is None or self._state != SessionState.CONNECTED:
                raise SessionStateError("FIX session must be connected before logon")
            self._transition_state_locked(SessionState.LOGGING_ON)
            logon_message = self._build_logon_message_locked()

        self._send_message(logon_message)

        with self._lock:
            if self._socket is not None:
                self._transition_state_locked(SessionState.ACTIVE)

    def logout(self, reason: str | None = None) -> None:
        """Send a FIX Logout message without closing the underlying socket."""
        with self._lock:
            if self._socket is None:
                raise SessionStateError("FIX session is not connected")
            if self._state not in {
                SessionState.CONNECTED,
                SessionState.LOGGING_ON,
                SessionState.ACTIVE,
            }:
                raise SessionStateError(
                    f"Cannot logout while session state is {self._state.name}"
                )
            self._transition_state_locked(SessionState.LOGGING_OUT)
            logout_message = self._build_logout_message_locked(reason)

        self._send_message(logout_message)

    def disconnect(self) -> None:
        """Close the TCP connection and transition to DISCONNECTED."""
        with self._lock:
            session_socket = self._socket
            self._socket = None
            self._transition_state_locked(SessionState.DISCONNECTED)

        if session_socket is None:
            return

        try:
            session_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            logger.debug("Socket shutdown ignored for FIX session", exc_info=True)

        try:
            session_socket.close()
        except OSError:
            logger.debug("Socket close ignored for FIX session", exc_info=True)

    def close(self, reason: str | None = "Client requested shutdown") -> None:
        """Gracefully close the session, sending Logout before disconnecting."""
        with self._lock:
            should_logout = self._socket is not None and self._state in {
                SessionState.CONNECTED,
                SessionState.LOGGING_ON,
                SessionState.ACTIVE,
            }

        try:
            if should_logout:
                self.logout(reason)
        finally:
            self.disconnect()

    def next_out_seq_num(self) -> int:
        """Reserve and return the next outbound sequence number."""
        with self._lock:
            MsgSeqNum = self._out_seq_num
            self._out_seq_num += 1
            return MsgSeqNum

    def send(self, message: simplefix.FixMessage) -> None:
        """Send an application FIX message while the session is active."""
        with self._lock:
            if self._state != SessionState.ACTIVE:
                raise SessionStateError(
                    "FIX session must be active before sending application messages"
                )

        self._send_message(message)

    def _send_message(self, message: simplefix.FixMessage) -> None:
        payload = message.encode()
        with self._lock:
            session_socket = self._socket

        if session_socket is None:
            raise SessionStateError("FIX session is not connected")

        try:
            session_socket.sendall(payload)
        except OSError as exc:
            self.disconnect()
            raise SessionConnectionError("Failed to send FIX message") from exc

    def _build_logon_message_locked(self) -> simplefix.FixMessage:
        message = self._build_admin_message_locked(_LOGON_MSG_TYPE)
        message.append_pair(98, "0")
        message.append_pair(108, str(self._config.heartbeat_interval))
        if self._config.reset_seq_nums in _RESET_SEQ_NUM_VALUES:
            message.append_pair(141, "Y")
        return message

    def _build_logout_message_locked(self, reason: str | None) -> simplefix.FixMessage:
        message = self._build_admin_message_locked(_LOGOUT_MSG_TYPE)
        if reason:
            message.append_pair(58, reason)
        return message

    def _build_admin_message_locked(self, msg_type: str) -> simplefix.FixMessage:
        message = simplefix.FixMessage()
        message.append_pair(8, self._config.fix_version)
        message.append_pair(35, msg_type)
        message.append_pair(49, self._config.sender_comp_id)
        message.append_pair(56, self._config.target_comp_id)
        message.append_pair(34, str(self._out_seq_num))
        message.append_pair(52, self._utc_timestamp())
        self._out_seq_num += 1
        return message

    def _transition_state_locked(self, new_state: SessionState) -> None:
        if self._state == new_state:
            return

        logger.debug(
            "FIX session %s->%s for %s->%s",
            self._state.name,
            new_state.name,
            self._config.sender_comp_id,
            self._config.target_comp_id,
        )
        self._state = new_state

    @staticmethod
    def _utc_timestamp() -> str:
        now = datetime.now(timezone.utc)
        return now.strftime("%Y%m%d-%H:%M:%S.%f")[:-3]


__all__ = [
    "FIXSession",
    "FIXSessionError",
    "SessionConnectionError",
    "SessionState",
    "SessionStateError",
]
