from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
)

from src.ui.order_panel import SendMessageTab


def test_send_message_tab_exposes_manual_send_controls(qapp: QApplication) -> None:
    tab = SendMessageTab()
    tab.show()
    qapp.processEvents()

    session_combo = tab.findChild(QComboBox, "sendMessageSessionCombo")
    editor = tab.findChild(QPlainTextEdit, "sendMessageEditor")
    autoincrement_edit = tab.findChild(QLineEdit, "sendMessageAutoincrementEdit")
    search_edit = tab.findChild(QLineEdit, "sendMessageSearchEdit")

    assert session_combo is not None
    assert editor is not None
    assert autoincrement_edit is not None
    assert search_edit is not None

    tab.set_available_sessions(["CLIENT_A->BROKER_A", "DROP_COPY->OPS"])
    qapp.processEvents()

    assert session_combo.count() == 3
    assert session_combo.itemText(1) == "CLIENT_A->BROKER_A"
    assert autoincrement_edit.text() == "35 11 60"
    assert editor.isReadOnly() is False
    assert editor.toPlainText() == ""

    QTest.keyClicks(search_edit, "ClOrdID")
    qapp.processEvents()
    assert search_edit.text() == "ClOrdID"

    tab.close()


def test_send_message_tab_search_moves_editor_selection_to_match(
    qapp: QApplication,
) -> None:
    tab = SendMessageTab()
    tab.show()
    qapp.processEvents()

    search_edit = tab.findChild(QLineEdit, "sendMessageSearchEdit")
    editor = tab.findChild(QPlainTextEdit, "sendMessageEditor")

    assert search_edit is not None
    assert editor is not None

    search_values: list[str] = []
    tab.search_text_changed.connect(search_values.append)

    tab.set_message_text(
        "8=FIX.4.4|35=D|49=CLIENT_A|56=BROKER_A|11=ORDER_1|\n"
        "8=FIX.4.4|35=F|49=CLIENT_A|56=BROKER_A|11=ORDER_2|"
    )

    QTest.keyClicks(search_edit, "ORDER_2")
    qapp.processEvents()

    assert search_values == ["O", "OR", "ORD", "ORDE", "ORDER", "ORDER_", "ORDER_2"]
    assert editor.textCursor().selectedText() == "ORDER_2"

    tab.close()


def test_send_message_tab_buttons_and_editor_actions_emit_expected_signals(
    qapp: QApplication,
) -> None:
    tab = SendMessageTab()
    tab.show()
    qapp.processEvents()

    send_all_calls: list[bool] = []
    send_selected_calls: list[bool] = []
    send_current_calls: list[bool] = []
    reset_calls: list[bool] = []
    record_calls: list[bool] = []
    load_calls: list[bool] = []
    save_calls: list[bool] = []
    edit_calls: list[bool] = []
    insert_calls: list[bool] = []
    word_wrap_values: list[bool] = []

    tab.send_all_requested.connect(lambda: send_all_calls.append(True))
    tab.send_selected_requested.connect(lambda: send_selected_calls.append(True))
    tab.send_current_and_next_requested.connect(lambda: send_current_calls.append(True))
    tab.reset_requested.connect(lambda: reset_calls.append(True))
    tab.record_test_scenario_requested.connect(lambda: record_calls.append(True))
    tab.load_requested.connect(lambda: load_calls.append(True))
    tab.save_requested.connect(lambda: save_calls.append(True))
    tab.edit_requested.connect(lambda: edit_calls.append(True))
    tab.insert_soh_requested.connect(lambda: insert_calls.append(True))
    tab.word_wrap_toggled.connect(word_wrap_values.append)

    for object_name, signal_calls in (
        ("sendAllButton", send_all_calls),
        ("sendSelectedButton", send_selected_calls),
        ("sendCurrentAndNextButton", send_current_calls),
        ("sendMessageResetButton", reset_calls),
        ("recordTestScenarioButton", record_calls),
    ):
        button = tab.findChild(QPushButton, object_name)
        assert button is not None
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        qapp.processEvents()
        assert signal_calls == [True]

    editor = tab.findChild(QPlainTextEdit, "sendMessageEditor")
    assert editor is not None
    tab.set_message_text("8=FIX.4.4")
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)

    load_action = tab.findChild(QAction, "sendMessageLoadAction")
    save_action = tab.findChild(QAction, "sendMessageSaveAction")
    edit_action = tab.findChild(QAction, "sendMessageEditAction")
    insert_soh_action = tab.findChild(QAction, "sendMessageInsertSohAction")
    word_wrap_action = tab.findChild(QAction, "sendMessageWordWrapAction")

    assert load_action is not None
    assert save_action is not None
    assert edit_action is not None
    assert insert_soh_action is not None
    assert word_wrap_action is not None

    load_action.trigger()
    save_action.trigger()
    edit_action.trigger()
    insert_soh_action.trigger()
    word_wrap_action.trigger()
    qapp.processEvents()

    assert load_calls == [True]
    assert save_calls == [True]
    assert edit_calls == [True]
    assert insert_calls == [True]
    assert word_wrap_values == [True]
    assert editor.toPlainText().endswith("\x01")
    assert editor.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth

    tab.close()


def test_send_message_tab_returns_message_blocks_and_can_focus_editor(
    qapp: QApplication,
) -> None:
    tab = SendMessageTab()
    tab.show()
    qapp.processEvents()

    editor = tab.findChild(QPlainTextEdit, "sendMessageEditor")
    assert editor is not None

    tab.set_message_text("8=FIX.4.4|35=D|11=ORDER_1|\n\n" "8=FIX.4.4|35=F|11=ORDER_2|")
    tab.focus_editor()
    qapp.processEvents()

    assert tab.all_message_blocks() == [
        "8=FIX.4.4|35=D|11=ORDER_1|",
        "8=FIX.4.4|35=F|11=ORDER_2|",
    ]
    assert editor.hasFocus() is True

    tab.close()


def test_send_message_tab_replaces_only_the_current_message_block(
    qapp: QApplication,
) -> None:
    tab = SendMessageTab()
    tab.show()
    qapp.processEvents()

    editor = tab.findChild(QPlainTextEdit, "sendMessageEditor")
    assert editor is not None

    tab.set_message_text(
        "8=FIX.4.4|35=D|11=ORDER_1|\n8=FIX.4.4|35=F|11=ORDER_2|"
    )
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.Start)
    cursor.movePosition(cursor.MoveOperation.Down)
    editor.setTextCursor(cursor)

    tab.replace_current_message_block("8=FIX.4.4|35=F|11=ORDER_99|")
    qapp.processEvents()

    assert tab.message_text() == (
        "8=FIX.4.4|35=D|11=ORDER_1|\n8=FIX.4.4|35=F|11=ORDER_99|"
    )

    tab.close()


def test_send_message_tab_replaces_nearest_message_when_cursor_is_on_trailing_blank_line(
    qapp: QApplication,
) -> None:
    tab = SendMessageTab()
    tab.show()
    qapp.processEvents()

    editor = tab.findChild(QPlainTextEdit, "sendMessageEditor")
    assert editor is not None

    tab.set_message_text("8=FIX.4.4|35=D|11=ORDER_1|\n")
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)

    tab.replace_current_message_block("8=FIX.4.4|35=D|11=ORDER_99|")
    qapp.processEvents()

    assert tab.message_text() == "8=FIX.4.4|35=D|11=ORDER_99|\n"

    tab.close()
