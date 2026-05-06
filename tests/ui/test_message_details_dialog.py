from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QTableWidget,
)

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
    value_item = table.item(0, 1)
    assert tag_item is not None
    assert value_item is not None
    assert tag_item.text() == "8"
    assert tag_item.toolTip() == "8 — BeginString"
    assert value_item.text() == "FIX.4.4"

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
        value_item = table.item(row, 1)
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
    value_item = table.item(0, 1)
    assert tag_item is not None
    assert value_item is not None
    assert tag_item.text() == ""
    assert value_item.text() == "this is not a FIX message"

    dialog.close()


def test_message_details_dialog_falls_back_to_raw_message_when_field_is_malformed(
    qapp: QApplication,
) -> None:
    raw_message = "35=D|BADFIELD|11=ORDER_42|"

    dialog = MessageDetailsDialog()
    dialog.set_message_text(raw_message, source_label="Current FIX message")
    dialog.show()
    qapp.processEvents()

    table = dialog.findChild(QTableWidget, "messageDetailsTable")
    assert table is not None
    assert table.rowCount() == 1

    tag_item = table.item(0, 0)
    value_item = table.item(0, 1)
    assert tag_item is not None
    assert value_item is not None
    assert tag_item.text() == ""
    assert value_item.text() == raw_message
    assert dialog.message_text() == raw_message

    dialog.close()


def test_message_details_dialog_allows_inline_fix_edits_and_rebuilds_message(
    qapp: QApplication,
) -> None:
    dialog = MessageDetailsDialog()
    dialog.set_message_text(
        "35=D|11=ORDER_42|58=Initial note",
        source_label="Current FIX message",
    )
    dialog.show()
    qapp.processEvents()

    table = dialog.findChild(QTableWidget, "messageDetailsTable")
    assert table is not None

    tag_item = table.item(1, 0)
    value_item = table.item(1, 1)

    assert tag_item is not None
    assert value_item is not None
    assert bool(tag_item.flags() & Qt.ItemFlag.ItemIsEditable) is True
    assert bool(value_item.flags() & Qt.ItemFlag.ItemIsEditable) is True

    value_item.setText("ORDER_99")
    qapp.processEvents()

    assert dialog.message_text() == "35=D|11=ORDER_99|58=Initial note|"

    dialog.close()


def test_message_details_dialog_preserves_original_soh_delimiter_after_edit(
    qapp: QApplication,
) -> None:
    dialog = MessageDetailsDialog()
    dialog.set_message_text(
        "8=FIX.4.4\x019=148\x0135=D\x0134=1080\x0149=TESTBUY1\x0152=20180920-18:14:19.508"
        "\x0156=TESTSELL1\x0111=636730640278898634\x0115=USD\x0121=2\x0138=7000"
        "\x0140=1\x0154=1\x0155=MSFT\x0160=20180920-18:14:19.492\x0110=092\x01",
        source_label="Current FIX message",
    )
    dialog.show()
    qapp.processEvents()

    table = dialog.findChild(QTableWidget, "messageDetailsTable")
    assert table is not None

    for row in range(table.rowCount()):
        tag_item = table.item(row, 0)
        value_item = table.item(row, 1)
        if tag_item is None or value_item is None:
            continue
        if tag_item.text() == "55":
            value_item.setText("AAPL")
            break

    qapp.processEvents()

    updated_message = dialog.message_text()
    updated_fields = [field for field in updated_message.split("\x01") if field]

    assert "|" not in updated_message
    assert updated_fields[-1] == "10=092"
    assert "55=AAPL" in updated_fields

    dialog.close()


def test_message_details_dialog_adds_blank_rows_before_checksum_and_removes_rows(
    qapp: QApplication,
) -> None:
    dialog = MessageDetailsDialog()
    dialog.set_message_text(
        "8=FIX.4.4|35=D|10=092|",
        source_label="Current FIX message",
    )
    dialog.show()
    qapp.processEvents()

    table = dialog.findChild(QTableWidget, "messageDetailsTable")
    add_button = dialog.findChild(QPushButton, "messageDetailsAddTagButton")
    remove_button = dialog.findChild(QPushButton, "messageDetailsRemoveRowButton")

    assert table is not None
    assert add_button is not None
    assert remove_button is not None
    assert add_button.text() == "Add Tag"
    assert remove_button.text() == "Delete Tag"

    initial_row_count = table.rowCount()
    QTest.mouseClick(add_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert table.rowCount() == initial_row_count + 1
    inserted_row = initial_row_count - 1
    inserted_tag_item = table.item(inserted_row, 0)
    inserted_value_item = table.item(inserted_row, 1)

    assert inserted_tag_item is not None
    assert inserted_value_item is not None
    assert inserted_tag_item.text() == ""
    assert inserted_value_item.text() == ""
    last_tag_item = table.item(table.rowCount() - 1, 0)
    assert last_tag_item is not None
    assert last_tag_item.text() == "10"

    table.selectRow(inserted_row)
    QTest.mouseClick(remove_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert table.rowCount() == initial_row_count

    dialog.close()


def test_message_details_dialog_summary_ignores_blank_inserted_rows(
    qapp: QApplication,
) -> None:
    dialog = MessageDetailsDialog()
    dialog.set_message_text(
        "35=D|11=ORDER_42|",
        source_label="Current FIX message",
    )
    dialog.show()
    qapp.processEvents()

    summary_label = dialog.findChild(QLabel, "messageDetailsSummaryLabel")
    add_button = dialog.findChild(QPushButton, "messageDetailsAddTagButton")
    assert summary_label is not None
    assert add_button is not None
    assert "2 field(s)" in summary_label.text()

    QTest.mouseClick(add_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert "2 field(s)" in summary_label.text()

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

    first_item = table.item(0, 1)
    second_item = table.item(1, 1)
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