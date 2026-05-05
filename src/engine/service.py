from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol, TypeVar

from src.config.session_config import SessionConfig
from src.engine.session import FIXSession, FIXSessionError, SessionState

logger = logging.getLogger(__name__)


class FIXEngineServiceError(Exception):
    """Base exception for FIX engine service failures."""


class NoActiveSessionError(FIXEngineServiceError):
    """Raised when a session-dependent operation is requested with no active session."""


class MessageDirection(Enum):
    """Direction of a FIX message event emitted by the engine service."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


@dataclass(frozen=True, slots=True)
class EngineMessageEvent:
    """Backend message event that can be forwarded to the UI layer."""

    timestamp: datetime
    session_id: str
    direction: MessageDirection
    message: str
    raw_message: str | None = None


class SessionLifecycle(Protocol):
    """Minimal session lifecycle contract required by FIXEngineService."""

    @property
    def config(self) -> SessionConfig: ...

    @property
    def state(self) -> SessionState: ...

    def connect(self) -> None: ...

    def logon(self) -> None: ...

    def close(self, reason: str | None = None) -> None: ...


SessionFactory = Callable[[SessionConfig], SessionLifecycle]
StateChangeHandler = Callable[[SessionState], None]
MessageHandler = Callable[[EngineMessageEvent], None]
ErrorHandler = Callable[[Exception], None]
HandlerPayload = TypeVar("HandlerPayload")


class FIXEngineService:
    """UI-facing backend API for managing the active FIX session and engine hooks."""

    def __init__(self, session_factory: SessionFactory = FIXSession) -> None:
        self._session_factory = session_factory
        self._lock = threading.Lock()
        self._active_config: SessionConfig | None = None
        self._active_session: SessionLifecycle | None = None
        self._state_change_handlers: list[StateChangeHandler] = []
        self._inbound_message_handlers: list[MessageHandler] = []
        self._outbound_message_handlers: list[MessageHandler] = []
        self._error_handlers: list[ErrorHandler] = []

    @property
    def active_config(self) -> SessionConfig | None:
        """Return the active session configuration, if one has been created."""
        with self._lock:
            return self._active_config

    @property
    def active_session(self) -> SessionLifecycle | None:
        """Return the active FIX session instance, if one has been created."""
        with self._lock:
            return self._active_session

    def register_state_change_handler(self, handler: StateChangeHandler) -> None:
        """Register a callback for session state changes."""
        with self._lock:
            self._state_change_handlers.append(handler)

    def register_inbound_message_handler(self, handler: MessageHandler) -> None:
        """Register a callback for inbound message events."""
        with self._lock:
            self._inbound_message_handlers.append(handler)

    def register_outbound_message_handler(self, handler: MessageHandler) -> None:
        """Register a callback for outbound message events."""
        with self._lock:
            self._outbound_message_handlers.append(handler)

    def register_error_handler(self, handler: ErrorHandler) -> None:
        """Register a callback for engine service errors."""
        with self._lock:
            self._error_handlers.append(handler)

    def create_session(
        self,
        config: SessionConfig | Mapping[str, object],
    ) -> SessionLifecycle:
        """Create and store the active session without opening the network connection."""
        session_config = self._coerce_config(config)
        session = self._session_factory(session_config)

        with self._lock:
            self._active_config = session_config
            self._active_session = session

        self._emit_state_change(session.state)
        return session

    def open_session(
        self,
        config: SessionConfig | Mapping[str, object] | None = None,
    ) -> SessionLifecycle:
        """Create or reuse the active session, then connect and log on it."""
        session = (
            self.create_session(config)
            if config is not None
            else self._require_active_session()
        )

        try:
            if session.state is SessionState.DISCONNECTED:
                session.connect()
                self._emit_state_change(session.state)

            if session.state is SessionState.CONNECTED:
                session.logon()
                self._emit_outbound_message(
                    session.config,
                    "Sent Logon",
                    raw_message="35=A",
                )
                self._emit_state_change(session.state)

            if session.state is not SessionState.ACTIVE:
                raise FIXEngineServiceError(
                    "Session failed to reach ACTIVE state, "
                    f"current state is {session.state.name}"
                )
        except (FIXEngineServiceError, FIXSessionError) as exc:
            self._emit_error(exc)
            raise

        return session

    def close_session(self, reason: str | None = "Client requested shutdown") -> None:
        """Gracefully close the active session, emitting logout and state hooks."""
        session = self._require_active_session()
        should_emit_logout = session.state in {
            SessionState.CONNECTED,
            SessionState.LOGGING_ON,
            SessionState.ACTIVE,
        }

        try:
            session.close(reason)
        except (FIXEngineServiceError, FIXSessionError) as exc:
            self._emit_error(exc)
            raise

        if should_emit_logout:
            self._emit_outbound_message(
                session.config,
                "Sent Logout",
                raw_message="35=5",
            )
        self._emit_state_change(session.state)

    def record_inbound_message(
        self,
        message: bytes | bytearray | memoryview | str,
    ) -> EngineMessageEvent:
        """Emit an inbound message event for the active session."""
        session = self._require_active_session()
        event = self._build_message_event(
            session.config,
            MessageDirection.INBOUND,
            message="Received inbound FIX message",
            raw_message=self._normalize_raw_message(message),
        )
        self._emit_message(
            self._copy_message_handlers(self._inbound_message_handlers),
            event,
        )
        return event

    def _require_active_session(self) -> SessionLifecycle:
        with self._lock:
            session = self._active_session

        if session is None:
            raise NoActiveSessionError("No active FIX session is available")

        return session

    @staticmethod
    def _coerce_config(config: SessionConfig | Mapping[str, object]) -> SessionConfig:
        if isinstance(config, SessionConfig):
            return config
        return SessionConfig.from_dict(config)

    def _emit_state_change(self, state: SessionState) -> None:
        self._emit_simple(
            self._copy_state_handlers(self._state_change_handlers),
            state,
        )

    def _emit_outbound_message(
        self,
        config: SessionConfig,
        message: str,
        *,
        raw_message: str | None = None,
    ) -> EngineMessageEvent:
        event = self._build_message_event(
            config,
            MessageDirection.OUTBOUND,
            message=message,
            raw_message=raw_message,
        )
        self._emit_message(
            self._copy_message_handlers(self._outbound_message_handlers),
            event,
        )
        return event

    def _emit_error(self, error: Exception) -> None:
        self._emit_simple(
            self._copy_error_handlers(self._error_handlers),
            error,
        )

    def _copy_state_handlers(
        self,
        handlers: list[StateChangeHandler],
    ) -> list[StateChangeHandler]:
        with self._lock:
            return list(handlers)

    def _copy_message_handlers(
        self,
        handlers: list[MessageHandler],
    ) -> list[MessageHandler]:
        with self._lock:
            return list(handlers)

    def _copy_error_handlers(
        self,
        handlers: list[ErrorHandler],
    ) -> list[ErrorHandler]:
        with self._lock:
            return list(handlers)

    @staticmethod
    def _emit_simple(
        handlers: list[Callable[[HandlerPayload], None]],
        payload: HandlerPayload,
    ) -> None:
        for handler in handlers:
            try:
                handler(payload)
            except Exception:
                logger.exception("FIX engine service callback failed")

    @staticmethod
    def _emit_message(
        handlers: list[MessageHandler],
        event: EngineMessageEvent,
    ) -> None:
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("FIX engine service message callback failed")

    def _build_message_event(
        self,
        config: SessionConfig,
        direction: MessageDirection,
        *,
        message: str,
        raw_message: str | None,
    ) -> EngineMessageEvent:
        return EngineMessageEvent(
            timestamp=datetime.now(timezone.utc),
            session_id=self._session_id(config),
            direction=direction,
            message=message,
            raw_message=raw_message,
        )

    @staticmethod
    def _session_id(config: SessionConfig) -> str:
        return f"{config.sender_comp_id}->{config.target_comp_id}"

    @staticmethod
    def _normalize_raw_message(
        message: bytes | bytearray | memoryview | str,
    ) -> str:
        if isinstance(message, str):
            return message
        return bytes(message).decode("utf-8", errors="replace")


__all__ = [
    "EngineMessageEvent",
    "FIXEngineService",
    "FIXEngineServiceError",
    "MessageDirection",
    "NoActiveSessionError",
    "SessionLifecycle",
]
