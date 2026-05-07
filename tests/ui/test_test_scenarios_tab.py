from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QTableWidget

from src.ui.test_scenarios_tab import TestScenariosTab


def test_test_scenarios_tab_exposes_placeholder_rows_and_create_button(
    qapp: QApplication,
) -> None:
    tab = TestScenariosTab()
    tab.show()
    qapp.processEvents()

    table = tab.findChild(QTableWidget, "testScenariosTable")
    create_button = tab.findChild(QPushButton, "createTestScenarioButton")

    assert table is not None
    assert create_button is not None
    assert create_button.text() == "Create Test Scenario"
    assert table.columnCount() == 4
    assert table.rowCount() == 2
    header_action = table.horizontalHeaderItem(0)
    header_name = table.horizontalHeaderItem(1)
    first_name_item = table.item(0, 1)
    first_detail_item = table.item(0, 3)
    assert header_action is not None
    assert header_name is not None
    assert first_name_item is not None
    assert first_detail_item is not None
    assert header_action.text() == "Action"
    assert header_name.text() == "Test Scenario Name"
    assert first_name_item.text() == "Order happy path"
    assert first_detail_item.text() == "Not Started"

    tab.close()


def test_test_scenarios_tab_emits_create_and_run_signals(qapp: QApplication) -> None:
    tab = TestScenariosTab()
    tab.show()
    qapp.processEvents()

    create_calls: list[bool] = []
    run_calls: list[str] = []

    tab.create_requested.connect(lambda: create_calls.append(True))
    tab.scenario_run_requested.connect(run_calls.append)

    create_button = tab.findChild(QPushButton, "createTestScenarioButton")
    run_button = tab.findChild(QPushButton, "testScenarioRunButton0")

    assert create_button is not None
    assert run_button is not None

    QTest.mouseClick(create_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(run_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert create_calls == [True]
    assert run_calls == ["Order happy path"]

    tab.close()
