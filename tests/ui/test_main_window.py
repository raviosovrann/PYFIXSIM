from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QLineEdit,
    QListWidget,
    QMenu,
    QPushButton,
)

from src.config.session_config import SessionConfig, save_config
from src.ui.create_session_dialog import CreateSessionDialog
from src.ui.main_window import MainWindow


def _find_menu_action(window: MainWindow, menu_title: str, action_text: str) -> QAction:
    for top_level_action in window.menuBar().actions():
        if top_level_action.text() != menu_title:
            continue

        menu = top_level_action.menu()
        if not isinstance(menu, QMenu):
            break

        for action in menu.actions():
            if action.text() == action_text:
                return action

    raise AssertionError(f"Action {action_text!r} was not found in menu {menu_title!r}")


def _create_config_file(
    tmp_path: Path,
    *,
    sender_comp_id: str = "CLIENT",
    target_comp_id: str = "SERVER",
    host: str = "127.0.0.1",
    port: int = 9876,
) -> Path:
    return save_config(
        SessionConfig(
            sender_comp_id=sender_comp_id,
            target_comp_id=target_comp_id,
            host=host,
            port=port,
        ),
        tmp_path / "session.cfg",
    )


def test_main_window_widget_interactions(qapp: QApplication, tmp_path: Path) -> None:
    window = MainWindow(config_path=_create_config_file(tmp_path))
    window.show()
    qapp.processEvents()

    assert window.windowTitle() == "FIXSIM — FIX Client Simulator"
    assert window.centralWidget() is not None

    menu_titles = [action.text() for action in window.menuBar().actions()]
    assert menu_titles == ["Session", "Message", "Events Viewer", "Options", "Help"]

    assert _find_menu_action(window, "Message", "Create").text() == "Create"
    assert _find_menu_action(window, "Message", "Load").text() == "Load"
    assert _find_menu_action(window, "Message", "Save").text() == "Save"
    assert _find_menu_action(window, "Message", "Edit").text() == "Edit"
    assert _find_menu_action(window, "Message", "Send batch").text() == "Send batch"

    tab_titles = [
        window.workspace_tabs.tabText(index)
        for index in range(window.workspace_tabs.count())
    ]
    assert tab_titles == ["Send Message", "Replay", "Test Scenarios"]

    replay_browse_button = window.findChild(QPushButton, "replayBrowseButton")
    create_test_scenario_button = window.findChild(
        QPushButton,
        "createTestScenarioButton",
    )
    assert replay_browse_button is not None
    assert create_test_scenario_button is not None

    assert window.application_state_label.text() == "Application: Ready"
    assert window.session_state_label.text() == "Session: No session selected"
    assert window.statusBar().currentMessage() == "FIX Client Simulator is ready"

    timestamp_checkbox = window.findChild(QCheckBox, "eventsViewerTimestampCheckbox")
    assert timestamp_checkbox is not None
    assert timestamp_checkbox.isChecked() is True

    QTest.mouseClick(timestamp_checkbox, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert timestamp_checkbox.isChecked() is False

    QTest.mouseClick(timestamp_checkbox, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert timestamp_checkbox.isChecked() is True

    QTest.keyClicks(window.filter_events_edit, "ExecReport")
    qapp.processEvents()
    assert window.filter_events_edit.text() == "ExecReport"

    window.close()


def test_main_window_updates_session_state_and_menu_driven_behaviour(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    window = MainWindow(config_path=_create_config_file(tmp_path))
    window.show()
    qapp.processEvents()

    list_widget = window.findChild(QListWidget, "sessionList")
    assert list_widget is not None

    window.upsert_session_from_config(
        SessionConfig(
            sender_comp_id="SECONDARY",
            target_comp_id="BROKER_2",
            host="127.0.0.1",
            port=9879,
        ),
        lifecycle_state="WAITING",
        state_category="waiting",
        select=False,
    )
    qapp.processEvents()

    first_item = list_widget.item(0)
    second_item = list_widget.item(1)

    first_item.setSelected(True)
    qapp.processEvents()
    assert window.session_state_label.text() == "Session: CLIENT->SERVER"

    second_item.setSelected(True)
    qapp.processEvents()
    assert window.session_state_label.text() == "Session: CLIENT->SERVER (+1 more)"

    list_widget.clearSelection()
    qapp.processEvents()
    assert window.session_state_label.text() == "Session: No session selected"

    multiline_action = _find_menu_action(
        window,
        "Options",
        "Multiline session information",
    )
    assert multiline_action.isChecked() is True
    multiline_action.trigger()
    qapp.processEvents()
    assert window.session_list_widget.is_multiline_mode() is False
    assert multiline_action.isChecked() is False

    multiline_action.trigger()
    qapp.processEvents()
    assert window.session_list_widget.is_multiline_mode() is True
    assert multiline_action.isChecked() is True

    clear_events_calls: list[bool] = []
    refresh_calls: list[bool] = []
    auto_scroll_values: list[bool] = []

    window.clear_events_requested.connect(lambda: clear_events_calls.append(True))
    window.refresh_sessions_requested.connect(lambda: refresh_calls.append(True))
    window.auto_scroll_toggled.connect(auto_scroll_values.append)

    refresh_action = _find_menu_action(window, "Session", "Refresh")
    refresh_action.trigger()
    qapp.processEvents()
    assert refresh_calls == [True]

    clear_action = _find_menu_action(window, "Events Viewer", "Clear event viewer")
    clear_action.trigger()
    qapp.processEvents()
    assert clear_events_calls == [True]
    assert window.events_viewer.toPlainText() == ""

    auto_scroll_action = _find_menu_action(window, "Events Viewer", "Auto scroll")
    assert auto_scroll_action.isChecked() is True
    auto_scroll_action.trigger()
    qapp.processEvents()
    assert auto_scroll_values == [False]
    assert auto_scroll_action.isChecked() is False
    assert window.events_viewer_panel.is_auto_scroll_enabled() is False

    window.close()


def test_main_window_opens_create_session_dialog_and_adds_session(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    window = MainWindow(config_path=_create_config_file(tmp_path))
    window.show()
    qapp.processEvents()

    list_widget = window.findChild(QListWidget, "sessionList")
    assert list_widget is not None
    initial_count = list_widget.count()

    create_session_action = _find_menu_action(
        window, "Session", "Create new FIX Session..."
    )
    create_session_action.trigger()
    qapp.processEvents()

    dialog = window.findChild(CreateSessionDialog)
    assert dialog is not None
    assert dialog.isVisible() is True

    sender_comp_id_edit = dialog.findChild(QLineEdit, "senderCompIdEdit")
    target_comp_id_edit = dialog.findChild(QLineEdit, "targetCompIdEdit")
    remote_host_edit = dialog.findChild(QLineEdit, "remoteHostEdit")
    button_box = dialog.findChild(QDialogButtonBox, "createSessionDialogButtonBox")
    session_combo = window.findChild(QComboBox, "sendMessageSessionCombo")

    assert sender_comp_id_edit is not None
    assert target_comp_id_edit is not None
    assert remote_host_edit is not None
    assert button_box is not None
    assert session_combo is not None
    assert remote_host_edit.text() == "127.0.0.1"

    QTest.keyClicks(sender_comp_id_edit, "ALGO_DESK")
    QTest.keyClicks(target_comp_id_edit, "EXEC_BROKER")
    remote_host_edit.clear()
    QTest.keyClicks(remote_host_edit, "10.0.0.55")
    qapp.processEvents()

    ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
    assert ok_button is not None

    QTest.mouseClick(ok_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert list_widget.count() == initial_count + 1
    assert window.session_state_label.text() == "Session: ALGO_DESK->EXEC_BROKER"
    assert window.application_state_label.text() == "Application: Session created"
    assert "New session was created" in window.statusBar().currentMessage()
    assert (
        "New session was created: ALGO_DESK->EXEC_BROKER"
        in window.events_viewer.toPlainText()
    )
    assert session_combo.currentText() == "ALGO_DESK->EXEC_BROKER"

    window.close()
