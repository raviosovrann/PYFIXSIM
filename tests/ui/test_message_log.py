from __future__ import annotations

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox, QLineEdit

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


def test_events_viewer_auto_scroll_keeps_horizontal_position_on_long_lines(
    qapp: QApplication,
) -> None:
    widget = EventsViewer()
    widget.resize(480, 240)
    widget.show()
    qapp.processEvents()

    long_line = "[outgoing] Original Message: " + ("8=FIX.4.2\x01" * 80)
    widget.append_event(long_line)
    qapp.processEvents()

    horizontal_scroll_bar = widget.log_view().horizontalScrollBar()
    vertical_scroll_bar = widget.log_view().verticalScrollBar()

    horizontal_scroll_bar.setValue(horizontal_scroll_bar.minimum())
    qapp.processEvents()

    widget.append_event(long_line)
    qapp.processEvents()

    assert horizontal_scroll_bar.value() == horizontal_scroll_bar.minimum()
    assert vertical_scroll_bar.value() == vertical_scroll_bar.maximum()

    widget.close()
