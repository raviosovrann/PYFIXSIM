from __future__ import annotations

import argparse
import logging
import socket
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final

import simplefix  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

_DEFAULT_HOST: Final[str] = "127.0.0.1"
_DEFAULT_PORT: Final[int] = 9878
_DEFAULT_FIX_VERSION: Final[str] = "FIX.4.2"
_DEFAULT_HEARTBEAT_INTERVAL: Final[int] = 30
_SOCKET_TIMEOUT: Final[float] = 0.1
_THREAD_JOIN_TIMEOUT: Final[float] = 0.2
_RECV_BUFFER_SIZE: Final[int] = 4096


class LocalFIXAcceptorError(Exception):
    """Raised when the local acceptor cannot be started or managed."""


@dataclass(frozen=True, slots=True)
class _ClientSessionIdentity:
    """Minimal session details needed for proactive outbound acceptor messages."""

    fix_version: str
    sender_comp_id: str
    target_comp_id: str


class LocalFIXAcceptor:
    """Minimal threaded FIX acceptor for local happy-path development and tests."""

    def __init__(
        self,
        host: str = _DEFAULT_HOST,
        port: int = _DEFAULT_PORT,
        *,
        fix_version: str = _DEFAULT_FIX_VERSION,
        heartbeat_interval: int = _DEFAULT_HEARTBEAT_INTERVAL,
    ) -> None:
        self._host = host
        self._port = port
        self._fix_version = fix_version
        self._heartbeat_interval = heartbeat_interval
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._listener: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None
        self._client_threads: list[threading.Thread] = []
        self._client_sockets: list[socket.socket] = []
        self._client_sessions: dict[int, _ClientSessionIdentity] = {}
        self._bound_port = port
        self._out_seq_num = 1
        self._exec_id = 1
        self._received_messages: list[str] = []
        self._sent_messages: list[str] = []

    @property
    def bound_port(self) -> int:
        """Return the actual bound TCP port, including ephemeral-port assignments."""
        with self._lock:
            return self._bound_port

    @property
    def received_messages(self) -> list[str]:
        """Return a snapshot of raw FIX messages received by the acceptor."""
        with self._lock:
            return list(self._received_messages)

    @property
    def sent_messages(self) -> list[str]:
        """Return a snapshot of raw FIX messages emitted by the acceptor."""
        with self._lock:
            return list(self._sent_messages)

    def start(self) -> None:
        """Start the listener and begin accepting client FIX sessions."""
        with self._lock:
            if self._listener is not None:
                raise LocalFIXAcceptorError("Local FIX acceptor is already running")

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            listener.bind((self._host, self._port))
            listener.listen()
            listener.settimeout(_SOCKET_TIMEOUT)
        except OSError as exc:
            listener.close()
            raise LocalFIXAcceptorError(
                f"Unable to bind local FIX acceptor on {self._host}:{self._port}"
            ) from exc

        accept_thread = threading.Thread(
            target=self._accept_loop,
            name="local-fix-acceptor",
            daemon=True,
        )
        with self._lock:
            self._listener = listener
            self._bound_port = int(listener.getsockname()[1])
            self._stop_event.clear()
            self._accept_thread = accept_thread
            self._out_seq_num = 1
            self._exec_id = 1

        accept_thread.start()
        logger.info(
            "Local FIX acceptor listening on %s:%s",
            self._host,
            self.bound_port,
        )

    def stop(self) -> None:
        """Stop the listener and close all client connections."""
        with self._lock:
            listener = self._listener
            accept_thread = self._accept_thread
            client_sockets = list(self._client_sockets)
            client_threads = list(self._client_threads)
            self._listener = None
            self._accept_thread = None

        self._stop_event.set()

        if listener is not None:
            try:
                listener.close()
            except OSError:
                logger.debug("Ignoring listener close failure", exc_info=True)

        for client_socket in client_sockets:
            try:
                client_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                logger.debug("Ignoring client shutdown failure", exc_info=True)
            try:
                client_socket.close()
            except OSError:
                logger.debug("Ignoring client close failure", exc_info=True)

        if (
            accept_thread is not None
            and accept_thread is not threading.current_thread()
        ):
            accept_thread.join(timeout=_THREAD_JOIN_TIMEOUT)

        for thread in client_threads:
            if thread is not threading.current_thread():
                thread.join(timeout=_THREAD_JOIN_TIMEOUT)

        with self._lock:
            self._client_sockets.clear()
            self._client_threads.clear()
            self._client_sessions.clear()

    def send_test_request(self, TestReqID: str = "PING_1") -> None:
        """Send a TestRequest to all connected client sessions."""
        self._broadcast_admin_message("1", TestReqID=TestReqID)

    def _accept_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                listener = self._listener

            if listener is None:
                return

            try:
                client_socket, _client_address = listener.accept()
                client_socket.settimeout(_SOCKET_TIMEOUT)
            except socket.timeout:
                continue
            except OSError:
                if not self._stop_event.is_set():
                    logger.debug(
                        "Local FIX acceptor accept loop stopped", exc_info=True
                    )
                return

            client_thread = threading.Thread(
                target=self._handle_client,
                args=(client_socket,),
                name="local-fix-client",
                daemon=True,
            )
            with self._lock:
                self._client_sockets.append(client_socket)
                self._client_threads.append(client_thread)
            client_thread.start()

    def _handle_client(self, client_socket: socket.socket) -> None:
        parser = simplefix.FixParser()

        try:
            with client_socket:
                while not self._stop_event.is_set():
                    try:
                        payload = client_socket.recv(_RECV_BUFFER_SIZE)
                    except socket.timeout:
                        continue
                    except OSError:
                        if not self._stop_event.is_set():
                            logger.debug(
                                "Local FIX acceptor client loop stopped",
                                exc_info=True,
                            )
                        return

                    if not payload:
                        return

                    parser.append_buffer(payload)
                    while (message := parser.get_message()) is not None:
                        self._record_message(self._received_messages, message)
                        should_close = self._handle_inbound_message(
                            client_socket,
                            message,
                        )
                        if should_close:
                            return
        finally:
            with self._lock:
                self._client_sockets = [
                    existing
                    for existing in self._client_sockets
                    if existing is not client_socket
                ]
                self._client_sessions.pop(id(client_socket), None)

    def _broadcast_admin_message(
        self,
        msg_type: str,
        *,
        TestReqID: str | None = None,
    ) -> None:
        with self._lock:
            client_sockets = list(self._client_sockets)

        if not client_sockets:
            raise LocalFIXAcceptorError("No connected FIX client is available")

        for client_socket in client_sockets:
            message = self._build_proactive_admin_message(client_socket, msg_type)
            if TestReqID:
                message.append_pair(112, TestReqID)
            self._send(client_socket, message)

    def _handle_inbound_message(
        self,
        client_socket: socket.socket,
        message: simplefix.FixMessage,
    ) -> bool:
        msg_type = self._required_tag(message, 35)

        if msg_type == "A":
            self._remember_client_session(client_socket, message)
            self._send(client_socket, self._build_logon_response(message))
            return False

        if msg_type == "0":
            return False

        if msg_type == "1":
            self._send(client_socket, self._build_heartbeat_response(message))
            return False

        if msg_type == "5":
            self._send(client_socket, self._build_logout_response(message))
            return True

        if msg_type == "D":
            self._send(client_socket, self._build_execution_report(message))
            return False

        logger.debug("Ignoring unsupported inbound MsgType=%s", msg_type)
        return False

    def _send(
        self, client_socket: socket.socket, message: simplefix.FixMessage
    ) -> None:
        payload = message.encode()
        self._record_message(self._sent_messages, message)
        try:
            client_socket.sendall(payload)
        except OSError:
            logger.debug("Local FIX acceptor send failed", exc_info=True)

    def _build_logon_response(
        self, inbound_message: simplefix.FixMessage
    ) -> simplefix.FixMessage:
        response = self._build_admin_message("A", inbound_message)
        response.append_pair(98, "0")
        response.append_pair(
            108,
            self._optional_tag(inbound_message, 108) or str(self._heartbeat_interval),
        )
        if self._optional_tag(inbound_message, 141) == "Y":
            response.append_pair(141, "Y")
        return response

    def _build_heartbeat_response(
        self,
        inbound_message: simplefix.FixMessage,
    ) -> simplefix.FixMessage:
        response = self._build_admin_message("0", inbound_message)
        TestReqID = self._optional_tag(inbound_message, 112)
        if TestReqID:
            response.append_pair(112, TestReqID)
        return response

    def _build_logout_response(
        self, inbound_message: simplefix.FixMessage
    ) -> simplefix.FixMessage:
        response = self._build_admin_message("5", inbound_message)
        response.append_pair(58, "Local FIX acceptor closing session")
        return response

    def _build_execution_report(
        self,
        inbound_message: simplefix.FixMessage,
    ) -> simplefix.FixMessage:
        response = self._build_application_message("8", inbound_message)
        ClOrdID = self._required_tag(inbound_message, 11)
        Symbol = self._required_tag(inbound_message, 55)
        Side = self._required_tag(inbound_message, 54)
        OrderQty = self._required_tag(inbound_message, 38)
        Price = self._optional_tag(inbound_message, 44) or "0"

        response.append_pair(37, f"LOCAL_ORDER_{ClOrdID}")
        response.append_pair(17, f"EXEC_{self._next_exec_id()}")
        response.append_pair(150, "2")
        response.append_pair(39, "2")
        response.append_pair(11, ClOrdID)
        response.append_pair(55, Symbol)
        response.append_pair(54, Side)
        response.append_pair(38, OrderQty)
        response.append_pair(151, "0")
        response.append_pair(14, OrderQty)
        response.append_pair(6, Price)
        response.append_pair(32, OrderQty)
        response.append_pair(31, Price)
        response.append_pair(60, self._utc_timestamp())
        response.append_pair(58, "Accepted by local FIX acceptor")
        return response

    def _build_admin_message(
        self,
        msg_type: str,
        inbound_message: simplefix.FixMessage,
    ) -> simplefix.FixMessage:
        message = self._build_application_message(msg_type, inbound_message)
        return message

    def _build_proactive_admin_message(
        self,
        client_socket: socket.socket,
        msg_type: str,
    ) -> simplefix.FixMessage:
        session_identity = self._client_session_identity(client_socket)
        message = simplefix.FixMessage()
        message.append_pair(8, session_identity.fix_version)
        message.append_pair(35, msg_type)
        message.append_pair(49, session_identity.sender_comp_id)
        message.append_pair(56, session_identity.target_comp_id)
        message.append_pair(34, str(self._next_out_seq_num()))
        message.append_pair(52, self._utc_timestamp())
        return message

    def _build_application_message(
        self,
        msg_type: str,
        inbound_message: simplefix.FixMessage,
    ) -> simplefix.FixMessage:
        message = simplefix.FixMessage()
        message.append_pair(
            8, self._optional_tag(inbound_message, 8) or self._fix_version
        )
        message.append_pair(35, msg_type)
        message.append_pair(49, self._required_tag(inbound_message, 56))
        message.append_pair(56, self._required_tag(inbound_message, 49))
        message.append_pair(34, str(self._next_out_seq_num()))
        message.append_pair(52, self._utc_timestamp())
        return message

    def _record_message(
        self,
        destination: list[str],
        message: simplefix.FixMessage,
    ) -> None:
        raw_message = bytes(message.encode()).decode("utf-8", errors="replace")
        with self._lock:
            destination.append(raw_message)

    def _next_out_seq_num(self) -> int:
        with self._lock:
            MsgSeqNum = self._out_seq_num
            self._out_seq_num += 1
            return MsgSeqNum

    def _next_exec_id(self) -> int:
        with self._lock:
            exec_id = self._exec_id
            self._exec_id += 1
            return exec_id

    def _remember_client_session(
        self,
        client_socket: socket.socket,
        message: simplefix.FixMessage,
    ) -> None:
        session_identity = _ClientSessionIdentity(
            fix_version=self._optional_tag(message, 8) or self._fix_version,
            sender_comp_id=self._required_tag(message, 56),
            target_comp_id=self._required_tag(message, 49),
        )
        with self._lock:
            self._client_sessions[id(client_socket)] = session_identity

    def _client_session_identity(
        self,
        client_socket: socket.socket,
    ) -> _ClientSessionIdentity:
        with self._lock:
            session_identity = self._client_sessions.get(id(client_socket))

        if session_identity is None:
            raise LocalFIXAcceptorError(
                "Connected FIX client has not completed logon yet"
            )

        return session_identity

    @staticmethod
    def _required_tag(message: simplefix.FixMessage, tag: int) -> str:
        raw_value = message.get(tag)
        if raw_value is None:
            raise LocalFIXAcceptorError(
                f"Inbound FIX message is missing required tag {tag}"
            )
        return bytes(raw_value).decode("utf-8", errors="replace")

    @staticmethod
    def _optional_tag(message: simplefix.FixMessage, tag: int) -> str:
        raw_value = message.get(tag)
        if raw_value is None:
            return ""
        return bytes(raw_value).decode("utf-8", errors="replace")

    @staticmethod
    def _utc_timestamp() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:-3]


def main() -> int:
    """Run the lightweight local FIX acceptor until interrupted."""
    parser = argparse.ArgumentParser(
        description="Run the FIXSIM local happy-path FIX acceptor",
    )
    parser.add_argument("--host", default=_DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=_DEFAULT_PORT)
    parser.add_argument("--fix-version", default=_DEFAULT_FIX_VERSION)
    parser.add_argument(
        "--heartbeat-interval",
        type=int,
        default=_DEFAULT_HEARTBEAT_INTERVAL,
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    acceptor = LocalFIXAcceptor(
        host=args.host,
        port=args.port,
        fix_version=args.fix_version,
        heartbeat_interval=args.heartbeat_interval,
    )
    acceptor.start()
    try:
        while True:
            acceptor._stop_event.wait(1.0)
            if acceptor._stop_event.is_set():
                return 0
    except KeyboardInterrupt:
        logger.info("Stopping local FIX acceptor")
        return 0
    finally:
        acceptor.stop()


if __name__ == "__main__":
    raise SystemExit(main())
