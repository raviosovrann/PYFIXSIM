from __future__ import annotations

from src.messages.order import ExecutionReport
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox, QLineEdit, QTableWidget

from src.ui.message_log import EventsViewer


def test_events_viewer_appends_and_clears_entries(qapp: QApplication) -> None:
    widget = EventsViewer()
    widget.show()
    qapp.processEvents()

    widget.append_event("[console] FIX Client Simulator is ready.")
    widget.append_event("[outgoing] NewOrderSingle 11=ORDER_1")
    widget.append_event("[incoming] ExecutionReport 11=ORDER_1")
    qapp.processEvents()

    visible_text = widget.toPlainText()
    assert "FIX Client Simulator is ready." in visible_text
    assert "NewOrderSingle 11=ORDER_1" in visible_text
    assert "ExecutionReport 11=ORDER_1" in visible_text
    assert widget.is_auto_scroll_enabled() is True

    widget.clear_events()
    qapp.processEvents()
    assert widget.toPlainText() == ""

    widget.close()


def test_events_viewer_filters_categories_and_text(qapp: QApplication) -> None:
    widget = EventsViewer()
    widget.show()
    qapp.processEvents()

    widget.append_event("[console] Session bootstrapped")
    widget.append_event("[outgoing] NewOrderSingle 11=ORDER_1")
    widget.append_event("[incoming] ExecutionReport 11=ORDER_2")
    qapp.processEvents()

    outgoing_checkbox = widget.findChild(QCheckBox, "eventsViewerOutgoingCheckbox")
    filter_edit = widget.filter_line_edit()

    assert outgoing_checkbox is not None
    assert isinstance(filter_edit, QLineEdit)

    outgoing_checkbox.click()
    qapp.processEvents()
    assert "NewOrderSingle 11=ORDER_1" not in widget.toPlainText()
    assert "ExecutionReport 11=ORDER_2" in widget.toPlainText()

    QTest.keyClicks(filter_edit, "ORDER_2")
    qapp.processEvents()
    assert "Session bootstrapped" not in widget.toPlainText()
    assert "ExecutionReport 11=ORDER_2" in widget.toPlainText()

    widget.close()


def test_events_viewer_timestamp_toggle_changes_rendered_lines(
    qapp: QApplication,
) -> None:
    widget = EventsViewer()
    widget.show()
    qapp.processEvents()

    widget.append_event("[console] Test line")
    qapp.processEvents()
    assert widget.toPlainText().startswith("[")

    timestamp_checkbox = widget.findChild(QCheckBox, "eventsViewerTimestampCheckbox")
    assert timestamp_checkbox is not None

    timestamp_checkbox.click()
    qapp.processEvents()
    assert widget.toPlainText() == "[console] Test line"

    widget.close()


def test_events_viewer_records_execution_reports_in_structured_table(
    qapp: QApplication,
) -> None:
    widget = EventsViewer()
    widget.show()
    qapp.processEvents()

    widget.append_execution_report(
        ExecutionReport(
            OrderID="BROKER_ORDER_1",
            ExecID="EXEC_1",
            ExecType="2",
            OrdStatus="2",
            ClOrdID="ORDER_1",
            Symbol="AAPL",
            Side="1",
            LeavesQty=0,
            CumQty=100,
            AvgPx=25.5,
            OrderQty=100,
            LastQty=100,
            LastPx=25.5,
            TransactTime="20260506-12:30:45.000",
            Text="Accepted by local FIX acceptor",
        )
    )
    qapp.processEvents()

    table = widget.findChild(QTableWidget, "executionReportTable")
    assert table is not None
    assert table.rowCount() == 1
    cl_ord_id_item = table.item(0, 1)
    symbol_item = table.item(0, 2)
    avg_px_item = table.item(0, 6)

    assert cl_ord_id_item is not None
    assert cl_ord_id_item.text() == "ORDER_1"
    assert symbol_item is not None
    assert symbol_item.text() == "AAPL"
    assert avg_px_item is not None
    assert avg_px_item.text() == "25.5"

    widget.clear_events()
    qapp.processEvents()
    assert table.rowCount() == 0

    widget.close()
