from __future__ import annotations

import threading
import time

from src.config.session_config import SessionConfig
from src.engine.local_acceptor import LocalFIXAcceptor
from src.engine.service import EngineMessageEvent, FIXEngineService
from src.messages.order import ExecutionReport, NewOrderSingle


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
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if any("35=A" in message for message in acceptor.sent_messages):
                break

        acceptor.send_test_request("PING_1")

        assert heartbeat_sent.wait(2.0) is True

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

        assert report_received.wait(2.0) is True
        service.close_session("integration done")
    finally:
        acceptor.stop()

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if any("35=0" in message and "112=PING_1" in message for message in acceptor.received_messages):
            break

    assert len(execution_reports) == 1
    assert execution_reports[0].ClOrdID == "ORDER_1"
    assert execution_reports[0].OrdStatus == "2"
    assert any(event.message == "Received TestRequest" for event in inbound_events)
    assert any(event.message == "ExecutionReport 11=ORDER_1" for event in inbound_events)
    assert any(event.message == "Sent Heartbeat" for event in outbound_events)
    assert any(event.message == "NewOrderSingle 11=ORDER_1" for event in outbound_events)
    assert any(event.message.startswith("Connected to 127.0.0.1:") for event in system_events)
    assert any(event.message.startswith("Disconnected from 127.0.0.1:") for event in system_events)
    assert any("35=A" in message for message in acceptor.received_messages)
    assert any("35=A" in message for message in acceptor.sent_messages)
    assert any("35=1" in message and "112=PING_1" in message for message in acceptor.sent_messages)
    assert any("35=0" in message and "112=PING_1" in message for message in acceptor.received_messages)
    assert any("35=D" in message for message in acceptor.received_messages)
    assert any("35=5" in message for message in acceptor.received_messages)
    assert any("35=5" in message for message in acceptor.sent_messages)
    assert any("35=8" in message for message in acceptor.sent_messages)