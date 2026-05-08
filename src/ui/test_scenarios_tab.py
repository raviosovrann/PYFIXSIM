from __future__ import annotations

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class TestScenariosTab(QWidget):
    """Top-level scenario runner surface with placeholder run actions."""

    __test__ = False

    create_requested = Signal()  # emitted when the user requests a new scenario
    scenario_run_requested = Signal(str)  # emitted when the user requests running a scenario

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._table = QTableWidget(self)
        self._table.setObjectName("testScenariosTable")
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(
            ["Action", "Test Scenario Name", "Session", "Details"]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setAlternatingRowColors(True)

        self._create_button = QPushButton("Create Test Scenario", self)
        self._create_button.setObjectName("createTestScenarioButton")

        self._build_ui()
        self._wire_signals()
        self._seed_placeholder_rows()

    def table_widget(self) -> QTableWidget:
        """Return the scenarios table shown in the tab."""
        return self._table

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        button_column = QVBoxLayout()
        button_column.setSpacing(6)
        button_column.addWidget(self._create_button)
        button_column.addStretch(1)

        root.addWidget(self._table, 1)
        root.addLayout(button_column)

    def _wire_signals(self) -> None:
        self._create_button.clicked.connect(self.create_requested)

    def _seed_placeholder_rows(self) -> None:
        self._add_scenario_row(
            scenario_name="Order happy path",
            session_name="CLIENT->SERVER",
            details="Not Started",
        )
        self._add_scenario_row(
            scenario_name="Replay smoke test",
            session_name="CLIENT->SERVER",
            details="Recorded placeholder scenario",
        )

    def _add_scenario_row(
        self,
        *,
        scenario_name: str,
        session_name: str,
        details: str,
    ) -> None:
        row_index = self._table.rowCount()
        self._table.insertRow(row_index)

        run_button = QPushButton("Run", self)
        run_button.setObjectName(f"testScenarioRunButton{row_index}")
        run_button.clicked.connect(
            lambda _checked=False, name=scenario_name: self._emit_run_requested(name)
        )

        self._table.setCellWidget(row_index, 0, run_button)
        self._table.setItem(row_index, 1, QTableWidgetItem(scenario_name))
        self._table.setItem(row_index, 2, QTableWidgetItem(session_name))
        self._table.setItem(row_index, 3, QTableWidgetItem(details))

    @Slot(str)
    def _emit_run_requested(self, scenario_name: str) -> None:
        self.scenario_run_requested.emit(scenario_name)
