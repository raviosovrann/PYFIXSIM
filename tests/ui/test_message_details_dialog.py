from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLabel, QTableWidget

from src.ui.message_details_dialog import MessageDetailsDialog
from src.ui.theme import get_app_stylesheet


def test_message_details_dialog_shows_placeholder_rows(qapp: QApplication) -> None:
    dialog = MessageDetailsDialog()
    dialog.show()
    qapp.processEvents()

    summary_label = dialog.findChild(QLabel, "messageDetailsSummaryLabel")
    table = dialog.findChild(QTableWidget, "messageDetailsTable")

    assert summary_label is not None
    assert table is not None
    assert "placeholder FIX fields" in summary_label.text()
    assert table.rowCount() >= 3

    tag_item = table.item(0, 0)
    name_item = table.item(0, 1)
    assert tag_item is not None
    assert name_item is not None
    assert tag_item.text() == "8"
    assert name_item.text() == "BeginString"

    dialog.close()


def test_message_details_dialog_parses_only_fields_present_in_message(
    qapp: QApplication,
) -> None:
    dialog = MessageDetailsDialog()
    dialog.set_message_text(
        "35=D|11=ORDER_42|58=" + "X" * 120,
        source_label="Current FIX message",
    )
    dialog.show()
    qapp.processEvents()

    summary_label = dialog.findChild(QLabel, "messageDetailsSummaryLabel")
    table = dialog.findChild(QTableWidget, "messageDetailsTable")

    assert summary_label is not None
    assert table is not None
    assert "Current FIX message" in summary_label.text()

    tags: list[str] = []
    value_column_texts: list[str] = []
    for row in range(table.rowCount()):
        tag_item = table.item(row, 0)
        value_item = table.item(row, 2)
        assert tag_item is not None
        assert value_item is not None
        tags.append(tag_item.text())
        value_column_texts.append(value_item.text())

    assert tags == ["35", "11", "58"]

    assert "ORDER_42" in value_column_texts
    assert "X" * 120 in value_column_texts

    dialog.close()


def test_message_details_dialog_preserves_unparsed_raw_message(
    qapp: QApplication,
) -> None:
    dialog = MessageDetailsDialog()
    dialog.set_message_text("this is not a FIX message", source_label="Current FIX message")
    dialog.show()
    qapp.processEvents()

    table = dialog.findChild(QTableWidget, "messageDetailsTable")
    assert table is not None
    assert table.rowCount() == 1

    tag_item = table.item(0, 0)
    name_item = table.item(0, 1)
    value_item = table.item(0, 2)
    assert tag_item is not None
    assert name_item is not None
    assert value_item is not None
    assert tag_item.text() == ""
    assert name_item.text() == "Raw message"
    assert value_item.text() == "this is not a FIX message"

    dialog.close()


def test_message_details_dialog_uses_dark_alternating_row_colors(
    qapp: QApplication,
) -> None:
    previous_stylesheet = qapp.styleSheet()
    dialog = MessageDetailsDialog()

    qapp.setStyleSheet(get_app_stylesheet())
    dialog.show()
    qapp.processEvents()

    table = dialog.findChild(QTableWidget, "messageDetailsTable")
    assert table is not None

    first_item = table.item(0, 2)
    second_item = table.item(1, 2)
    assert first_item is not None
    assert second_item is not None

    first_rect = table.visualItemRect(first_item)
    second_rect = table.visualItemRect(second_item)
    image = table.viewport().grab().toImage()

    first_color = image.pixelColor(max(first_rect.left() + 4, first_rect.right() - 12), first_rect.center().y())
    second_color = image.pixelColor(max(second_rect.left() + 4, second_rect.right() - 12), second_rect.center().y())

    assert _is_dark(first_color)
    assert _is_dark(second_color)
    assert first_color != second_color

    dialog.close()
    qapp.setStyleSheet(previous_stylesheet)


def _is_dark(color: QColor) -> bool:
    return color.lightness() < 80