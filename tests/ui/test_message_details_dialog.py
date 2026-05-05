from __future__ import annotations

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


def test_message_details_dialog_parses_message_and_keeps_admin_rows(
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

    assert tags[0] == "8"
    assert "9" in tags
    assert "35" in tags
    assert "11" in tags
    assert tags[-1] == "10"

    assert "ORDER_42" in value_column_texts
    assert "X" * 120 in value_column_texts

    dialog.close()


def test_app_stylesheet_defines_dark_item_view_alternating_rows() -> None:
    stylesheet = get_app_stylesheet()

    assert "QAbstractItemView" in stylesheet
    assert "alternate-background-color: #101419;" in stylesheet
    assert "gridline-color: #343a40;" in stylesheet
    assert "QHeaderView::section" in stylesheet