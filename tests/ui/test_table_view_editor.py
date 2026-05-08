from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton, QTableWidget

from src.ui.table_view_editor import TableViewEditor


def test_table_view_editor_shows_tag_name_value_columns(qapp: QApplication) -> None:
    dialog = TableViewEditor()
    dialog.set_message_text(
        "8=FIX.4.4\x019=148\x0135=D\x0134=1\x0149=CLIENT\x0152=20260507-12:00:00.000"
        "\x0156=BROKER\x0111=ORDER_42\x0155=AAPL\x0154=1\x0138=100\x0140=2"
        "\x0144=25.50\x0160=20260507-12:00:00.000\x0110=123\x01",
        source_label="Current FIX message",
    )
    dialog.show()
    qapp.processEvents()

    table = dialog.findChild(QTableWidget, "tableViewEditorTable")
    assert table is not None
    assert table.columnCount() == 3
    header_tag = table.horizontalHeaderItem(0)
    header_name = table.horizontalHeaderItem(1)
    header_value = table.horizontalHeaderItem(2)
    assert header_tag is not None
    assert header_name is not None
    assert header_value is not None
    assert header_tag.text() == "Tag"
    assert header_name.text() == "Name"
    assert header_value.text() == "Value"

    tag_item = table.item(0, 0)
    name_item = table.item(0, 1)
    value_item = table.item(0, 2)
    assert tag_item is not None
    assert name_item is not None
    assert value_item is not None
    assert tag_item.text() == "8"
    assert name_item.text() == "BeginString"
    assert value_item.text() == "FIX.4.4"

    dialog.close()


def test_table_view_editor_updates_message_and_allows_add_delete(qapp: QApplication) -> None:
    dialog = TableViewEditor()
    dialog.set_message_text(
        "8=FIX.4.4\x019=148\x0135=D\x0134=1\x0149=CLIENT\x0152=20260507-12:00:00.000"
        "\x0156=BROKER\x0111=ORDER_42\x0155=AAPL\x0154=1\x0138=100\x0140=2"
        "\x0144=25.50\x0160=20260507-12:00:00.000\x0110=123\x01",
        source_label="Current FIX message",
    )
    dialog.show()
    qapp.processEvents()

    table = dialog.findChild(QTableWidget, "tableViewEditorTable")
    tag_combo = dialog.findChild(QComboBox, "tableViewEditorTagCombo")
    value_edit = dialog.findChild(QLineEdit, "tableViewEditorValueEdit")
    add_button = dialog.findChild(QPushButton, "tableViewEditorAddTagButton")
    delete_button = dialog.findChild(QPushButton, "tableViewEditorDeleteRowButton")

    assert table is not None
    assert tag_combo is not None
    assert value_edit is not None
    assert add_button is not None
    assert delete_button is not None

    cl_ord_id_item = table.item(7, 2)
    assert cl_ord_id_item is not None
    cl_ord_id_item.setText("ORDER_99")
    qapp.processEvents()

    assert "11=ORDER_99" in dialog.message_text()

    initial_row_count = table.rowCount()
    tag_combo.setCurrentText("58")
    QTest.keyClicks(value_edit, "Desk note")
    QTest.mouseClick(add_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert table.rowCount() == initial_row_count + 1
    assert "58=Desk note" in dialog.message_text()

    table.selectRow(table.rowCount() - 2)
    QTest.mouseClick(delete_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert table.rowCount() == initial_row_count

    dialog.close()
