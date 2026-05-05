from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QLabel,
    QListWidget,
)

from src.ui.session_widget import (
    SessionListEntry,
    SessionListWidget,
    _SessionRowWidget,
    build_placeholder_sessions,
)


def _find_action(widget: SessionListWidget, object_name: str) -> QAction:
    action = widget.findChild(QAction, object_name)
    assert action is not None
    return action


def test_session_list_widget_supports_multiline_selection_and_context_actions(
    qapp: QApplication,
) -> None:
    widget = SessionListWidget()
    widget.show()
    qapp.processEvents()

    widget.set_sessions(build_placeholder_sessions())
    qapp.processEvents()

    list_widget = widget.findChild(QListWidget, "sessionList")
    assert list_widget is not None
    assert list_widget.count() >= 1
    assert (
        list_widget.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection
    )

    selected_ids: list[list[str]] = []
    widget.selection_changed.connect(selected_ids.append)

    first_item = list_widget.item(0)
    first_item.setSelected(True)
    qapp.processEvents()

    assert selected_ids
    assert widget.selected_session_ids() == [first_item.data(Qt.ItemDataRole.UserRole)]

    row_widget = list_widget.itemWidget(first_item)
    assert row_widget is not None

    secondary_label = row_widget.findChild(QLabel, "sessionRowSecondaryLabel")
    assert secondary_label is not None
    assert secondary_label.isVisible() is True

    widget.set_multiline_mode(False)
    qapp.processEvents()
    assert widget.is_multiline_mode() is False
    assert secondary_label.isVisible() is False

    start_calls: list[bool] = []
    widget.start_requested.connect(lambda: start_calls.append(True))

    start_action = widget.findChild(QAction, "sessionStartAction")
    assert start_action is not None
    start_action.trigger()
    qapp.processEvents()

    assert start_calls == [True]

    refresh_action = widget.findChild(QAction, "sessionRefreshAction")
    assert refresh_action is not None
    assert refresh_action.text() == "Refresh list"

    widget.close()


def test_session_list_widget_exposes_state_indicators_and_clearable_multi_selection(
    qapp: QApplication,
) -> None:
    widget = SessionListWidget()
    widget.show()
    qapp.processEvents()

    widget.set_sessions(build_placeholder_sessions())
    qapp.processEvents()

    list_widget = widget.findChild(QListWidget, "sessionList")
    assert list_widget is not None
    assert list_widget.count() == 3

    first_item = list_widget.item(0)
    second_item = list_widget.item(1)
    third_item = list_widget.item(2)

    first_row = list_widget.itemWidget(first_item)
    second_row = list_widget.itemWidget(second_item)
    third_row = list_widget.itemWidget(third_item)
    assert first_row is not None
    assert second_row is not None
    assert third_row is not None

    first_indicator = first_row.findChild(QLabel, "sessionRowIndicator")
    second_indicator = second_row.findChild(QLabel, "sessionRowIndicator")
    third_indicator = third_row.findChild(QLabel, "sessionRowIndicator")

    assert first_indicator is not None
    assert second_indicator is not None
    assert third_indicator is not None
    assert first_indicator.property("sessionIndicator") == "waiting"
    assert second_indicator.property("sessionIndicator") == "connected"
    assert third_indicator.property("sessionIndicator") == "error"

    emitted_selection_ids: list[list[str]] = []
    widget.selection_changed.connect(emitted_selection_ids.append)

    first_item.setSelected(True)
    second_item.setSelected(True)
    qapp.processEvents()

    assert widget.selected_session_ids() == [
        first_item.data(Qt.ItemDataRole.UserRole),
        second_item.data(Qt.ItemDataRole.UserRole),
    ]
    assert emitted_selection_ids[-1] == widget.selected_session_ids()

    list_widget.clearSelection()
    qapp.processEvents()

    assert widget.selected_session_ids() == []
    assert emitted_selection_ids[-1] == []

    widget.close()


def test_session_list_widget_emits_all_non_modal_action_signals(
    qapp: QApplication,
) -> None:
    widget = SessionListWidget()
    widget.show()
    qapp.processEvents()

    widget.set_sessions(build_placeholder_sessions())
    qapp.processEvents()

    refresh_calls: list[bool] = []
    start_calls: list[bool] = []
    stop_calls: list[bool] = []
    restart_calls: list[bool] = []
    show_calls: list[bool] = []
    close_calls: list[bool] = []

    widget.refresh_requested.connect(lambda: refresh_calls.append(True))
    widget.start_requested.connect(lambda: start_calls.append(True))
    widget.stop_requested.connect(lambda: stop_calls.append(True))
    widget.restart_requested.connect(lambda: restart_calls.append(True))
    widget.show_session_messages_requested.connect(lambda: show_calls.append(True))
    widget.close_session_requested.connect(lambda: close_calls.append(True))

    _find_action(widget, "sessionRefreshAction").trigger()
    _find_action(widget, "sessionStartAction").trigger()
    _find_action(widget, "sessionStopAction").trigger()
    _find_action(widget, "sessionRestartAction").trigger()
    _find_action(widget, "sessionShowMessagesAction").trigger()
    _find_action(widget, "sessionCloseAction").trigger()
    qapp.processEvents()

    assert refresh_calls == [True]
    assert start_calls == [True]
    assert stop_calls == [True]
    assert restart_calls == [True]
    assert show_calls == [True]
    assert close_calls == [True]

    widget.close()


def test_session_row_widget_recovers_cached_labels_after_python_attribute_loss(
    qapp: QApplication,
) -> None:
    row_widget = _SessionRowWidget()
    row_widget.show()
    qapp.processEvents()

    del row_widget._indicator_label
    del row_widget._primary_label
    del row_widget._secondary_label

    row_widget.set_entry(
        SessionListEntry(
            session_id="BUY_SIDE->SELL_SIDE",
            fix_version="FIX.4.4",
            role="Initiator",
            sender_comp_id="BUY_SIDE",
            target_comp_id="SELL_SIDE",
            lifecycle_state="CONNECTED",
            host="127.0.0.1",
            port=9878,
            in_seq_num=2,
            out_seq_num=3,
            state_category="connected",
        ),
        multiline=True,
    )
    qapp.processEvents()

    indicator_label = row_widget.findChild(QLabel, "sessionRowIndicator")
    primary_label = row_widget.findChild(QLabel, "sessionRowPrimaryLabel")
    secondary_label = row_widget.findChild(QLabel, "sessionRowSecondaryLabel")

    assert indicator_label is not None
    assert primary_label is not None
    assert secondary_label is not None
    assert indicator_label.property("sessionIndicator") == "connected"
    assert "BUY_SIDE -> SELL_SIDE" in primary_label.text()
    assert secondary_label.text() == "CONNECTED | 127.0.0.1:9878 | In:2 Out:3"

    row_widget.close()
