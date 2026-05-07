from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol, TypeAlias, TypeVar

import simplefix  # type: ignore[import-untyped]

from src.config.session_config import SessionConfig
from src.engine.session import FIXSession, FIXSessionError, SessionState
from src.messages.order import ExecutionReport, MessageValidationError, NewOrderSingle

logger = logging.getLogger(__name__)

_INBOUND_DESCRIPTION_BY_MSG_TYPE = {
    "0": "Received Heartbeat",
    "1": "Received TestRequest",
    "5": "Received Logout",
    "A": "Received Logon",
}
_SESSION_MANAGED_TAGS = {8, 9, 10, 34, 49, 52, 56}


class FIXEngineServiceError(Exception):
    """Base exception for FIX engine service failures."""


class NoActiveSessionError(FIXEngineServiceError):
    """Raised when a session-dependent operation is requested with no active session."""


class MessageDirection(Enum):
    """Direction of a FIX message event emitted by the engine service."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"
    SYSTEM = "system"


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

    def next_out_seq_num(self) -> int: ...

    def register_inbound_message_handler(
        self,
        handler: Callable[[simplefix.FixMessage], None],
    ) -> None: ...

    def send(self, message: simplefix.FixMessage) -> None: ...

    def send_heartbeat(self, TestReqID: str | None = None) -> simplefix.FixMessage: ...


SessionFactory = Callable[[SessionConfig], SessionLifecycle]
StateChangeHandler = Callable[[SessionState], None]
MessageHandler = Callable[[EngineMessageEvent], None]
ErrorHandler = Callable[[Exception], None]
ExecutionReportHandler = Callable[[ExecutionReport], None]
HandlerPayload = TypeVar("HandlerPayload")
RawFixMessage: TypeAlias = simplefix.FixMessage | bytes | bytearray | memoryview | str


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
        self._system_message_handlers: list[MessageHandler] = []
        self._error_handlers: list[ErrorHandler] = []
        self._execution_report_handlers: list[ExecutionReportHandler] = []

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

    def register_system_message_handler(self, handler: MessageHandler) -> None:
        """Register a callback for system/lifecycle engine events."""
        with self._lock:
            self._system_message_handlers.append(handler)

    def register_error_handler(self, handler: ErrorHandler) -> None:
        """Register a callback for engine service errors."""
        with self._lock:
            self._error_handlers.append(handler)

    def register_execution_report_handler(
        self,
        handler: ExecutionReportHandler,
    ) -> None:
        """Register a callback for parsed execution reports."""
        with self._lock:
            self._execution_report_handlers.append(handler)

    def create_session(
        self,
        config: SessionConfig | Mapping[str, object],
    ) -> SessionLifecycle:
        """Create and store the active session without opening the network connection."""
        session_config = self._coerce_config(config)
        session = self._session_factory(session_config)
        self._attach_session_handlers(session)

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
        try:
            session = (
                self.create_session(config)
                if config is not None
                else self._require_active_session()
            )

            if session.state is SessionState.DISCONNECTED:
                session.connect()
                self._emit_state_change(session.state)
                self._emit_system_message(
                    session.config,
                    f"Connected to {session.config.host}:{session.config.port}",
                )

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
        try:
            session = self._require_active_session()
            should_emit_logout = session.state in {
                SessionState.CONNECTED,
                SessionState.LOGGING_ON,
                SessionState.ACTIVE,
            }

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
        self._emit_system_message(
            session.config,
            f"Disconnected from {session.config.host}:{session.config.port}",
        )

    def record_inbound_message(
        self,
        message: RawFixMessage,
        *,
        description: str = "Received inbound FIX message",
    ) -> EngineMessageEvent:
        """Emit an inbound message event for the active session."""
        try:
            session = self._require_active_session()
            event = self._build_message_event(
                session.config,
                MessageDirection.INBOUND,
                message=description,
                raw_message=self._normalize_raw_message(message),
            )
            self._emit_message(
                self._copy_message_handlers(self._inbound_message_handlers),
                event,
            )
            return event
        except FIXEngineServiceError as exc:
            self._emit_error(exc)
            raise

    def send_new_order_single(
        self,
        order: NewOrderSingle,
    ) -> EngineMessageEvent:
        """Encode, send, and emit an event for a NewOrderSingle."""
        try:
            session = self._require_active_session()
            if session.state is not SessionState.ACTIVE:
                error = FIXEngineServiceError(
                    "Active FIX session is required before sending NewOrderSingle"
                )
                self._emit_error(error)
                raise error

            fix_message = order.to_fix_message(
                session.config,
                MsgSeqNum=session.next_out_seq_num(),
            )
            session.send(fix_message)
        except (FIXEngineServiceError, FIXSessionError, MessageValidationError) as exc:
            self._emit_error(exc)
            raise

        return self._emit_outbound_message(
            session.config,
            f"NewOrderSingle 11={order.ClOrdID}",
            raw_message=self._encode_fix_message(fix_message),
        )

    def send_raw_message(self, message: RawFixMessage) -> EngineMessageEvent:
        """Send a raw FIX payload for the active session and emit an outbound event."""
        try:
            session = self._require_active_session()
            if session.state is not SessionState.ACTIVE:
                error = FIXEngineServiceError(
                    "Active FIX session is required before sending raw FIX messages"
                )
                self._emit_error(error)
                raise error

            fix_message = self._prepare_outbound_fix_message(
                session,
                self._coerce_fix_message(message),
            )
            session.send(fix_message)
        except (FIXEngineServiceError, FIXSessionError, MessageValidationError) as exc:
            self._emit_error(exc)
            raise

        return self._emit_outbound_message(
            session.config,
            self._describe_fix_message(fix_message),
            raw_message=self._encode_fix_message(fix_message),
        )

    def handle_execution_report(self, message: RawFixMessage) -> ExecutionReport:
        """Parse, emit, and return an inbound ExecutionReport."""
        try:
            session = self._require_active_session()
            fix_message = self._coerce_fix_message(message)
            execution_report = ExecutionReport.from_fix_message(fix_message)
        except (FIXEngineServiceError, FIXSessionError, MessageValidationError) as exc:
            self._emit_error(exc)
            raise

        event = self._build_message_event(
            session.config,
            MessageDirection.INBOUND,
            message=f"ExecutionReport 11={execution_report.ClOrdID}",
            raw_message=self._encode_fix_message(fix_message),
        )
        self._emit_message(
            self._copy_message_handlers(self._inbound_message_handlers),
            event,
        )
        self._emit_simple(
            self._copy_execution_report_handlers(self._execution_report_handlers),
            execution_report,
        )
        return execution_report

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

    def _attach_session_handlers(self, session: SessionLifecycle) -> None:
        session.register_inbound_message_handler(self._handle_session_inbound_message)

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

    def _emit_system_message(
        self,
        config: SessionConfig,
        message: str,
        *,
        raw_message: str | None = None,
    ) -> EngineMessageEvent:
        event = self._build_message_event(
            config,
            MessageDirection.SYSTEM,
            message=message,
            raw_message=raw_message,
        )
        self._emit_message(
            self._copy_message_handlers(self._system_message_handlers),
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

    def _copy_execution_report_handlers(
        self,
        handlers: list[ExecutionReportHandler],
    ) -> list[ExecutionReportHandler]:
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
        message: RawFixMessage,
    ) -> str:
        if isinstance(message, simplefix.FixMessage):
            return bytes(message.encode()).decode("utf-8", errors="replace")
        if isinstance(message, str):
            return message
        return bytes(message).decode("utf-8", errors="replace")

    def _handle_session_inbound_message(self, message: simplefix.FixMessage) -> None:
        msg_type = self._msg_type(message)

        if msg_type == "8":
            try:
                self.handle_execution_report(message)
            except (FIXEngineServiceError, FIXSessionError, MessageValidationError):
                return
            return

        if msg_type == "1":
            try:
                self.record_inbound_message(
                    message,
                    description=self._describe_inbound_message(message),
                )
                session = self._require_active_session()
                TestReqID = self._decode_optional_tag(message, 112)
                heartbeat = session.send_heartbeat(TestReqID or None)
            except (
                FIXEngineServiceError,
                FIXSessionError,
                MessageValidationError,
            ) as exc:
                self._emit_error(exc)
                return

            self._emit_outbound_message(
                session.config,
                "Sent Heartbeat",
                raw_message=self._encode_fix_message(heartbeat),
            )
            return

        try:
            self.record_inbound_message(
                message,
                description=self._describe_inbound_message(message),
            )
        except FIXEngineServiceError:
            return

    def _coerce_fix_message(self, message: RawFixMessage) -> simplefix.FixMessage:
        if isinstance(message, simplefix.FixMessage):
            return message

        fix_message = simplefix.FixMessage()
        normalized_text = self._normalize_raw_message(message).replace("|", "\x01")
        fields = [field for field in normalized_text.split("\x01") if field]
        if not fields:
            raise MessageValidationError(8, "unable to parse FIX message payload")

        for field in fields:
            if "=" not in field:
                raise MessageValidationError(8, f"invalid FIX field: {field!r}")

            raw_tag, value = field.split("=", 1)
            try:
                tag = int(raw_tag)
            except ValueError as exc:
                raise MessageValidationError(
                    8,
                    f"invalid FIX tag: {raw_tag!r}",
                ) from exc

            fix_message.append_pair(tag, value)

        return fix_message

    def _prepare_outbound_fix_message(
        self,
        session: SessionLifecycle,
        message: simplefix.FixMessage,
    ) -> simplefix.FixMessage:
        msg_type = self._msg_type(message)
        prepared_message = simplefix.FixMessage()
        prepared_message.append_pair(8, session.config.fix_version)
        prepared_message.append_pair(35, msg_type)
        prepared_message.append_pair(49, session.config.sender_comp_id)
        prepared_message.append_pair(56, session.config.target_comp_id)
        prepared_message.append_pair(34, str(session.next_out_seq_num()))
        prepared_message.append_pair(52, self._utc_timestamp())

        for raw_tag, raw_value in message.pairs:
            tag = int(raw_tag)
            if tag in _SESSION_MANAGED_TAGS or tag == 35:
                continue
            prepared_message.append_pair(tag, raw_value)

        return prepared_message

    def _encode_fix_message(self, message: simplefix.FixMessage) -> str:
        return self._normalize_raw_message(message.encode())

    def _describe_inbound_message(self, message: simplefix.FixMessage) -> str:
        return _INBOUND_DESCRIPTION_BY_MSG_TYPE.get(
            self._msg_type(message),
            f"Received FIX message 35={self._msg_type(message)}",
        )

    @staticmethod
    def _decode_optional_tag(message: simplefix.FixMessage, tag: int) -> str:
        raw_value = message.get(tag)
        if raw_value is None:
            return ""
        return bytes(raw_value).decode("utf-8", errors="replace")

    def _msg_type(self, message: simplefix.FixMessage) -> str:
        raw_msg_type = message.get(35)
        if raw_msg_type is None:
            raise MessageValidationError(35, "FIX message is missing MsgType")
        return bytes(raw_msg_type).decode("utf-8", errors="replace")

    @staticmethod
    def _utc_timestamp() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:-3]

    @staticmethod
    def _describe_fix_message(message: simplefix.FixMessage) -> str:
        raw_msg_type = message.get(35)
        if raw_msg_type is None:
            return "Sent FIX message"

        msg_type = bytes(raw_msg_type).decode("utf-8", errors="replace")
        return f"Sent FIX message 35={msg_type}"


__all__ = [
    "EngineMessageEvent",
    "FIXEngineService",
    "FIXEngineServiceError",
    "MessageDirection",
    "NoActiveSessionError",
    "SessionLifecycle",
]
