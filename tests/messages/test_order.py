from __future__ import annotations

import pytest
import simplefix  # type: ignore[import-untyped]

from src.config.session_config import SessionConfig
from src.messages.order import ExecutionReport, MessageValidationError, NewOrderSingle


def _build_session_config() -> SessionConfig:
    return SessionConfig(
        sender_comp_id="CLIENT",
        target_comp_id="SERVER",
        host="127.0.0.1",
        port=9876,
    )


def test_new_order_single_encodes_core_fix_tags() -> None:
    order = NewOrderSingle(
        ClOrdID="ORDER_1",
        Symbol="AAPL",
        Side="1",
        OrderQty=100,
        OrdType="2",
        Price=25.5,
        TimeInForce="0",
    )

    fix_message = order.to_fix_message(_build_session_config(), MsgSeqNum=7)
    encoded = bytes(fix_message.encode())

    assert b"35=D" in encoded
    assert b"49=CLIENT" in encoded
    assert b"56=SERVER" in encoded
    assert b"34=7" in encoded
    assert b"11=ORDER_1" in encoded
    assert b"21=1" in encoded
    assert b"55=AAPL" in encoded
    assert b"54=1" in encoded
    assert b"38=100" in encoded
    assert b"40=2" in encoded
    assert b"44=25.5" in encoded
    assert b"59=0" in encoded


def test_new_order_single_requires_price_for_limit_orders() -> None:
    order = NewOrderSingle(
        ClOrdID="ORDER_1",
        Symbol="AAPL",
        Side="1",
        OrderQty=100,
        OrdType="2",
    )

    with pytest.raises(MessageValidationError) as exc_info:
        order.to_fix_message(_build_session_config(), MsgSeqNum=1)

    assert exc_info.value.tag == 44


def test_execution_report_parses_core_fields() -> None:
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
    message.append_pair(32, "100")
    message.append_pair(31, "25.5")
    message.append_pair(60, "20260504-12:30:45.000")

    execution_report = ExecutionReport.from_fix_message(message)

    assert execution_report.OrderID == "BROKER_ORDER_1"
    assert execution_report.ExecID == "EXEC_1"
    assert execution_report.ExecType == "2"
    assert execution_report.OrdStatus == "2"
    assert execution_report.ClOrdID == "ORDER_1"
    assert execution_report.Symbol == "AAPL"
    assert execution_report.Side == "1"
    assert execution_report.OrderQty == 100
    assert execution_report.LeavesQty == 0
    assert execution_report.CumQty == 100
    assert execution_report.AvgPx == 25.5
    assert execution_report.LastQty == 100.0
    assert execution_report.LastPx == 25.5
    assert execution_report.TransactTime == "20260504-12:30:45.000"


def test_execution_report_raises_typed_error_for_missing_required_fields() -> None:
    message = simplefix.FixMessage()
    message.append_pair(8, "FIX.4.2")
    message.append_pair(35, "8")
    message.append_pair(37, "BROKER_ORDER_1")
    message.append_pair(150, "2")
    message.append_pair(39, "2")
    message.append_pair(11, "ORDER_1")
    message.append_pair(55, "AAPL")
    message.append_pair(54, "1")
    message.append_pair(151, "0")
    message.append_pair(14, "100")
    message.append_pair(6, "25.5")

    with pytest.raises(MessageValidationError) as exc_info:
        ExecutionReport.from_fix_message(message)

    assert exc_info.value.tag == 17
