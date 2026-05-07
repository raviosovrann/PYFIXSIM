from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.ui.message_details_dialog import validate_fix_message_for_details_dialog

_TAG_NAMES: dict[str, str] = {
    "8": "BeginString",
    "9": "BodyLength",
    "10": "CheckSum",
    "11": "ClOrdID",
    "21": "HandlInst",
    "34": "MsgSeqNum",
    "35": "MsgType",
    "38": "OrderQty",
    "40": "OrdType",
    "44": "Price",
    "49": "SenderCompID",
    "52": "SendingTime",
    "54": "Side",
    "55": "Symbol",
    "56": "TargetCompID",
    "58": "Text",
    "59": "TimeInForce",
    "60": "TransactTime",
}
_DEFAULT_MESSAGE_DELIMITER = "|"
_FIX_MESSAGE_DELIMITER = "\x01"
_TRAILER_TAGS = frozenset({"10"})


@dataclass(frozen=True, slots=True)
class EditableFieldRow:
    """One structured FIX field displayed in the editable table view."""

    tag: str
    value: str


class TableViewEditor(QDialog):
    """Editable FIX tag grid used by the Send Message workspace."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Table View Editor")
        self.setObjectName("tableViewEditorDialog")
        self.resize(860, 520)
        self.setMinimumSize(620, 360)
        self._message_delimiter = _DEFAULT_MESSAGE_DELIMITER
        self._source_label = "Table View Editor"
        self._has_loaded_message = False
        self._is_updating_table = False

        self._summary_label = QLabel(self)
        self._summary_label.setObjectName("tableViewEditorSummaryLabel")
        self._summary_label.setWordWrap(True)

        self._tag_combo = QComboBox(self)
        self._tag_combo.setObjectName("tableViewEditorTagCombo")
        self._tag_combo.setEditable(True)
        self._tag_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for tag, name in sorted(_TAG_NAMES.items(), key=lambda item: int(item[0])):
            self._tag_combo.addItem(f"{tag} — {name}", userData=tag)

        self._value_edit = QLineEdit(self)
        self._value_edit.setObjectName("tableViewEditorValueEdit")
        self._value_edit.setPlaceholderText("Field value")

        self._add_tag_button = QPushButton("Add Tag", self)
        self._add_tag_button.setObjectName("tableViewEditorAddTagButton")

        self._remove_row_button = QPushButton("Delete Row", self)
        self._remove_row_button.setObjectName("tableViewEditorDeleteRowButton")

        self._table = QTableWidget(self)
        self._table.setObjectName("tableViewEditorTable")
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Tag", "Name", "Value"])
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )

        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._button_box.setObjectName("tableViewEditorButtonBox")
        save_button = self._button_box.button(QDialogButtonBox.StandardButton.Ok)
        if save_button is not None:
            save_button.setText("Save")

        self._build_ui()
        self._wire_signals()
        self.set_message_text(None)

    def table_widget(self) -> QTableWidget:
        """Return the editable tag grid used by the dialog."""
        return self._table

    def message_text(self) -> str:
        """Serialize table rows back into a raw FIX message."""
        fields = [f"{row.tag}={row.value}" for row in self._collect_rows() if row.tag]
        if not fields:
            return ""
        return self._message_delimiter.join(fields) + self._message_delimiter

    def set_message_text(
        self,
        raw_message: str | None,
        *,
        source_label: str = "Table View Editor",
    ) -> None:
        """Populate the editable grid from a raw FIX message."""
        self._message_delimiter = self._detect_delimiter(raw_message)
        self._source_label = source_label
        self._has_loaded_message = bool(raw_message and raw_message.strip())
        self._populate_table(self._build_rows(raw_message))
        self._update_summary_label()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        add_row_layout = QHBoxLayout()
        add_row_layout.setSpacing(8)
        add_row_layout.addWidget(QLabel("Tag:", self))
        add_row_layout.addWidget(self._tag_combo)
        add_row_layout.addWidget(QLabel("Value:", self))
        add_row_layout.addWidget(self._value_edit, 1)
        add_row_layout.addWidget(self._add_tag_button)
        add_row_layout.addWidget(self._remove_row_button)

        layout.addWidget(self._summary_label)
        layout.addLayout(add_row_layout)
        layout.addWidget(self._table, 1)
        layout.addWidget(self._button_box)

    def _wire_signals(self) -> None:
        self._add_tag_button.clicked.connect(self._on_add_tag_requested)
        self._remove_row_button.clicked.connect(self._on_remove_row_requested)
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)
        self._table.itemChanged.connect(self._on_table_item_changed)

    def _build_rows(self, raw_message: str | None) -> list[EditableFieldRow]:
        if not raw_message or not raw_message.strip():
            return self._placeholder_rows()

        rows: list[EditableFieldRow] = []
        for field in raw_message.split(self._message_delimiter):
            stripped_field = field.strip()
            if not stripped_field:
                continue
            if "=" not in stripped_field:
                continue
            tag, value = stripped_field.split("=", 1)
            normalized_tag = tag.strip()
            if not normalized_tag:
                continue
            rows.append(EditableFieldRow(tag=normalized_tag, value=value))

        return rows or self._placeholder_rows()

    def _placeholder_rows(self) -> list[EditableFieldRow]:
        return [
            EditableFieldRow("8", "FIX.4.4"),
            EditableFieldRow("9", "148"),
            EditableFieldRow("35", "D"),
            EditableFieldRow("34", "1"),
            EditableFieldRow("49", "CLIENT"),
            EditableFieldRow("52", "20260507-12:00:00.000"),
            EditableFieldRow("56", "BROKER"),
            EditableFieldRow("11", "ORDER_0001"),
            EditableFieldRow("55", "AAPL"),
            EditableFieldRow("54", "1"),
            EditableFieldRow("38", "100"),
            EditableFieldRow("40", "2"),
            EditableFieldRow("44", "25.50"),
            EditableFieldRow("60", "20260507-12:00:00.000"),
            EditableFieldRow("10", "123"),
        ]

    def _populate_table(self, rows: list[EditableFieldRow]) -> None:
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        for row in rows:
            self._insert_row(row)
        self._table.blockSignals(False)
        self._table.resizeRowsToContents()

    def _insert_row(
        self,
        row: EditableFieldRow,
        *,
        row_index: int | None = None,
    ) -> int:
        if row_index is None:
            row_index = self._table.rowCount()

        self._table.insertRow(row_index)
        self._table.setItem(row_index, 0, self._create_item(row.tag, editable=True))
        self._table.setItem(
            row_index,
            1,
            self._create_item(self._tag_name(row.tag), editable=False),
        )
        self._table.setItem(row_index, 2, self._create_item(row.value, editable=True))
        return row_index

    def _default_insert_row(self) -> int:
        for row_index in range(self._table.rowCount()):
            tag_item = self._table.item(row_index, 0)
            if tag_item is not None and tag_item.text().strip() in _TRAILER_TAGS:
                return row_index
        return self._table.rowCount()

    def _collect_rows(self) -> list[EditableFieldRow]:
        rows: list[EditableFieldRow] = []
        for row_index in range(self._table.rowCount()):
            tag_item = self._table.item(row_index, 0)
            value_item = self._table.item(row_index, 2)
            tag = tag_item.text().strip() if tag_item is not None else ""
            value = value_item.text() if value_item is not None else ""
            if not tag and value == "":
                continue
            rows.append(EditableFieldRow(tag=tag, value=value))
        return rows

    def _serializable_field_count(self) -> int:
        return sum(1 for row in self._collect_rows() if row.tag)

    def _selected_tag_value(self) -> str:
        text = self._tag_combo.currentText().strip()
        if text:
            return text.split()[0]

        tag_data = self._tag_combo.currentData()
        if isinstance(tag_data, str) and tag_data:
            return tag_data

        return ""

    def _detect_delimiter(self, raw_message: str | None) -> str:
        if raw_message and _FIX_MESSAGE_DELIMITER in raw_message:
            return _FIX_MESSAGE_DELIMITER
        return _DEFAULT_MESSAGE_DELIMITER

    def _tag_name(self, tag: str) -> str:
        return _TAG_NAMES.get(tag.strip(), "Custom") if tag.strip() else ""

    def _update_summary_label(self) -> None:
        if self._has_loaded_message:
            self._summary_label.setText(
                f"{self._source_label} — displaying {self._serializable_field_count()} editable field(s)"
            )
            return

        self._summary_label.setText(
            "Table View Editor — displaying placeholder FIX fields"
        )

    @Slot()
    def _on_add_tag_requested(self) -> None:
        tag = self._selected_tag_value().strip()
        value = self._value_edit.text()
        row_index = self._insert_row(
            EditableFieldRow(tag=tag, value=value),
            row_index=self._default_insert_row(),
        )
        self._table.setCurrentCell(row_index, 2)
        self._value_edit.clear()
        self._update_summary_label()

    @Slot()
    def _on_remove_row_requested(self) -> None:
        current_row = self._table.currentRow()
        if current_row < 0:
            current_row = self._table.rowCount() - 1
        if current_row < 0:
            return
        self._table.removeRow(current_row)
        self._update_summary_label()

    @Slot(QTableWidgetItem)
    def _on_table_item_changed(self, item: QTableWidgetItem) -> None:
        if self._is_updating_table:
            return

        self._is_updating_table = True
        try:
            if item.column() == 0:
                normalized_tag = item.text().strip()
                item.setText(normalized_tag)
                name_item = self._table.item(item.row(), 1)
                if name_item is not None:
                    name_item.setText(self._tag_name(normalized_tag))
                    name_item.setToolTip(self._tag_name(normalized_tag))
            else:
                item.setToolTip(item.text())
        finally:
            self._is_updating_table = False

        self._update_summary_label()
        self._table.resizeRowsToContents()

    @Slot()
    def accept(self) -> None:
        validation_error = validate_fix_message_for_details_dialog(self.message_text())
        if validation_error is not None:
            QMessageBox.warning(self, "Invalid FIX Message", validation_error)
            return
        super().accept()

    def _create_item(self, value: str, *, editable: bool) -> QTableWidgetItem:
        item = QTableWidgetItem(value)
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setToolTip(value)
        return item
