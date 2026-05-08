from __future__ import annotations

import threading
import time
from collections.abc import Callable

from src.config.session_config import SessionConfig
from src.engine.local_acceptor import LocalFIXAcceptor
from src.engine.service import EngineMessageEvent, FIXEngineService
from src.messages.order import ExecutionReport, NewOrderSingle


_WAIT_TIMEOUT = 1.0
_POLL_INTERVAL = 0.01


def _wait_until(predicate: Callable[[], bool], timeout: float = _WAIT_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(_POLL_INTERVAL)
    return predicate()


def test_local_fix_acceptor_supports_happy_path_order_flow() -> None:
    acceptor = LocalFIXAcceptor(port=0)
    acceptor.start()

    execution_reports: list[ExecutionReport] = []
    inbound_events: list[EngineMessageEvent] = []
    outbound_events: list[EngineMessageEvent] = []
    system_events: list[EngineMessageEvent] = []
    report_received = threading.Event()
    heartbeat_sent = threading.Event()
    service = FIXEngineService()

    def _capture_execution_report(report: ExecutionReport) -> None:
        execution_reports.append(report)
        report_received.set()

    service.register_execution_report_handler(_capture_execution_report)
    service.register_inbound_message_handler(inbound_events.append)

    def _capture_outbound_event(event: EngineMessageEvent) -> None:
        outbound_events.append(event)
        if event.message == "Sent Heartbeat":
            heartbeat_sent.set()

    service.register_outbound_message_handler(_capture_outbound_event)
    service.register_system_message_handler(system_events.append)

    try:
        service.open_session(
            SessionConfig(
                sender_comp_id="CLIENT",
                target_comp_id="SERVER",
                host="127.0.0.1",
                port=acceptor.bound_port,
            )
        )
        assert _wait_until(
            lambda: any("35=A" in message for message in acceptor.sent_messages)
        )

        acceptor.send_test_request("PING_1")

        assert heartbeat_sent.wait(_WAIT_TIMEOUT) is True

        service.send_new_order_single(
            NewOrderSingle(
                ClOrdID="ORDER_1",
                Symbol="AAPL",
                Side="1",
                OrderQty=100,
                OrdType="2",
                Price=25.5,
            )
        )

        assert report_received.wait(_WAIT_TIMEOUT) is True
        service.close_session("integration done")
    finally:
        acceptor.stop()

    assert _wait_until(
        lambda: any(
            "35=0" in message and "112=PING_1" in message
            for message in acceptor.received_messages
        )
    )

    assert len(execution_reports) == 1
    assert execution_reports[0].ClOrdID == "ORDER_1"
    assert execution_reports[0].OrdStatus == "2"
    assert any(event.message == "Received TestRequest" for event in inbound_events)
    assert any(
        event.message == "ExecutionReport 11=ORDER_1" for event in inbound_events
    )
    assert any(event.message == "Sent Heartbeat" for event in outbound_events)
    assert any(
        event.message == "NewOrderSingle 11=ORDER_1" for event in outbound_events
    )
    assert any(
        event.message.startswith("Connected to 127.0.0.1:") for event in system_events
    )
    assert any(
        event.message.startswith("Disconnected from 127.0.0.1:")
        for event in system_events
    )
    assert any("35=A" in message for message in acceptor.received_messages)
    assert any("35=A" in message for message in acceptor.sent_messages)
    assert any(
        "35=1" in message and "112=PING_1" in message
        for message in acceptor.sent_messages
    )
    assert any(
        "35=0" in message and "112=PING_1" in message
        for message in acceptor.received_messages
    )
    assert any("35=D" in message for message in acceptor.received_messages)
    assert any("35=5" in message for message in acceptor.received_messages)
    assert any("35=5" in message for message in acceptor.sent_messages)
    assert any("35=8" in message for message in acceptor.sent_messages)


def test_local_fix_acceptor_and_service_exchange_periodic_heartbeats() -> None:
    acceptor = LocalFIXAcceptor(port=0, heartbeat_interval=1)
    acceptor.start()

    inbound_events: list[EngineMessageEvent] = []
    outbound_events: list[EngineMessageEvent] = []
    service = FIXEngineService()
    service.register_inbound_message_handler(inbound_events.append)
    service.register_outbound_message_handler(outbound_events.append)

    try:
        service.open_session(
            SessionConfig(
                sender_comp_id="CLIENT",
                target_comp_id="SERVER",
                host="127.0.0.1",
                port=acceptor.bound_port,
                heartbeat_interval=1,
            )
        )

        assert _wait_until(
            lambda: any(event.message == "Sent Heartbeat" for event in outbound_events),
            timeout=2.5,
        )
        assert _wait_until(
            lambda: any(
                event.message == "Received Heartbeat" for event in inbound_events
            ),
            timeout=2.5,
        )
    finally:
        service.close_session("heartbeat integration done")
        acceptor.stop()

    assert any("35=0" in message for message in acceptor.received_messages)
    assert any("35=0" in message for message in acceptor.sent_messages)
    