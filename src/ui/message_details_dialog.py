from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

_TAG_NAMES: dict[str, str] = {
    "8": "BeginString",
    "9": "BodyLength",
    "10": "CheckSum",
    "11": "ClOrdID",
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
    "60": "TransactTime",
}
_DEFAULT_MESSAGE_DELIMITER = "|"
_TRAILER_TAGS = frozenset({"10"})
_REQUIRED_EDIT_TAGS: tuple[str, ...] = (
    "8",
    "9",
    "34",
    "35",
    "49",
    "52",
    "56",
    "60",
    "10",
)
_REQUIRED_EDIT_TAGS_TEXT = ", ".join(_REQUIRED_EDIT_TAGS[:-1]) + ", and 10"


def validate_fix_message_for_details_dialog(raw_message: str | None) -> str | None:
    """Return a user-facing error when a raw message is not safe for structured editing."""
    if raw_message is None:
        return "Structured editor requires a complete FIX message."

    normalized_message = raw_message.replace("\x01", _DEFAULT_MESSAGE_DELIMITER).strip()
    if (
        len(normalized_message) <= 1
        or _DEFAULT_MESSAGE_DELIMITER not in normalized_message
    ):
        return "Structured editor requires a complete FIX message."

    fields = [
        field.strip()
        for field in normalized_message.split(_DEFAULT_MESSAGE_DELIMITER)
        if field.strip()
    ]
    if not fields:
        return "Structured editor requires a complete FIX message."

    present_required_tags: set[str] = set()
    for field in fields:
        if "=" not in field:
            return "Structured editor requires populated numeric tag=value FIX fields."

        tag, value = field.split("=", 1)
        normalized_tag = tag.strip()
        normalized_value = value.strip()
        if not normalized_tag or not normalized_tag.isdigit() or not normalized_value:
            return "Structured editor requires populated numeric tag=value FIX fields."

        if normalized_tag in _REQUIRED_EDIT_TAGS:
            present_required_tags.add(normalized_tag)

    missing_tags = [
        tag for tag in _REQUIRED_EDIT_TAGS if tag not in present_required_tags
    ]
    if missing_tags:
        return (
            "Structured editor requires FIX tags "
            f"{_REQUIRED_EDIT_TAGS_TEXT} with values."
        )

    return None


@dataclass(frozen=True, slots=True)
class MessageFieldRow:
    """One row displayed in the structured FIX message details table."""

    tag: str
    value: str


class MessageDetailsDialog(QDialog):
    """Structured FIX message editor rendered as a compact tag/value table."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Message Details")
        self.setObjectName("messageDetailsDialog")
        self.resize(760, 440)
        self.setMinimumSize(520, 320)
        self._is_updating_table = False
        self._has_loaded_message = False
        self._message_delimiter = _DEFAULT_MESSAGE_DELIMITER
        self._source_label = "Message Details"

        self._summary_label = QLabel(self)
        self._summary_label.setObjectName("messageDetailsSummaryLabel")
        self._summary_label.setWordWrap(True)

        self._add_tag_button = QPushButton("Add Tag", self)
        self._add_tag_button.setObjectName("messageDetailsAddTagButton")

        self._remove_row_button = QPushButton("Delete Tag", self)
        self._remove_row_button.setObjectName("messageDetailsRemoveRowButton")

        self._table = QTableWidget(self)
        self._table.setObjectName("messageDetailsTable")
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Tag", "Value"])
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setWordWrap(False)
        self._table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )

        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._button_box.setObjectName("messageDetailsButtonBox")
        save_button = self._button_box.button(QDialogButtonBox.StandardButton.Ok)
        if save_button is not None:
            save_button.setText("Save")

        self._build_ui()
        self._wire_signals()
        self.set_message_text(None)

    def table_widget(self) -> QTableWidget:
        """Return the editable details table used by the dialog."""
        return self._table

    def message_text(self) -> str:
        """Serialize the current table rows back into a FIX-like raw message."""
        rows = self._collect_rows()
        if self._is_raw_message_rows(rows):
            return rows[0].value.strip()

        fields = [f"{row.tag}={row.value}" for row in rows if row.tag]
        if not fields:
            return ""
        return self._message_delimiter.join(fields) + self._message_delimiter

    def set_message_text(
        self,
        raw_message: str | None,
        *,
        source_label: str = "Message Details",
    ) -> None:
        """Populate the dialog from a raw FIX message or a placeholder sample."""
        self._message_delimiter = self._detect_delimiter(raw_message)
        self._has_loaded_message = bool(raw_message and raw_message.strip())
        self._source_label = source_label
        rows = self._build_rows(raw_message)
        self._populate_table(rows)
        self._update_summary_label()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        actions_layout.addWidget(self._add_tag_button)
        actions_layout.addWidget(self._remove_row_button)
        actions_layout.addStretch(1)

        layout.addWidget(self._summary_label)
        layout.addLayout(actions_layout)
        layout.addWidget(self._table, 1)
        layout.addWidget(self._button_box)

    def _wire_signals(self) -> None:
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)
        self._add_tag_button.clicked.connect(self._on_add_tag_requested)
        self._remove_row_button.clicked.connect(self._on_remove_row_requested)
        self._table.itemChanged.connect(self._on_table_item_changed)

    def _build_rows(self, raw_message: str | None) -> list[MessageFieldRow]:
        if not raw_message or not raw_message.strip():
            return self._placeholder_rows()

        rows: list[MessageFieldRow] = []
        for field in raw_message.split(self._message_delimiter):
            stripped_field = field.strip()
            if not stripped_field:
                continue
            if "=" not in stripped_field:
                logger.debug(
                    "Falling back to raw message view due to malformed FIX field: %s",
                    stripped_field,
                )
                return self._raw_message_rows(raw_message)

            tag, value = stripped_field.split("=", 1)
            normalized_tag = tag.strip()
            if not normalized_tag or not value.strip():
                logger.debug(
                    "Falling back to raw message view due to incomplete FIX field: %s",
                    stripped_field,
                )
                return self._raw_message_rows(raw_message)

            rows.append(MessageFieldRow(tag=normalized_tag, value=value))

        if not rows:
            return self._raw_message_rows(raw_message)

        return rows

    def _placeholder_rows(self) -> list[MessageFieldRow]:
        return [
            MessageFieldRow("8", "FIX.4.4"),
            MessageFieldRow("9", "112"),
            MessageFieldRow("35", "D"),
            MessageFieldRow("49", "CLIENT"),
            MessageFieldRow("56", "BROKER"),
            MessageFieldRow("11", "ORDER_0001"),
            MessageFieldRow("55", "AAPL"),
            MessageFieldRow("54", "1"),
            MessageFieldRow("38", "100"),
            MessageFieldRow("44", "25.50"),
            MessageFieldRow("10", "123"),
        ]

    def _populate_table(self, rows: list[MessageFieldRow]) -> None:
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        for row in rows:
            self._insert_row(row)
        self._table.blockSignals(False)

        self._table.resizeRowsToContents()

    def _collect_rows(self) -> list[MessageFieldRow]:
        rows: list[MessageFieldRow] = []
        for row_index in range(self._table.rowCount()):
            tag_item = self._table.item(row_index, 0)
            value_item = self._table.item(row_index, 1)

            tag = tag_item.text().strip() if tag_item is not None else ""
            value = value_item.text() if value_item is not None else ""

            if not tag and value == "":
                continue

            rows.append(MessageFieldRow(tag=tag, value=value))

        return rows

    def _insert_row(self, row: MessageFieldRow, *, row_index: int | None = None) -> int:
        if row_index is None:
            row_index = self._table.rowCount()

        self._table.insertRow(row_index)
        self._table.setItem(
            row_index,
            0,
            self._create_item(
                row.tag,
                editable=True,
                tooltip=self._tag_tooltip(row.tag),
            ),
        )
        self._table.setItem(row_index, 1, self._create_item(row.value, editable=True))
        return row_index

    def _default_insert_row(self) -> int:
        for row_index in range(self._table.rowCount()):
            tag_item = self._table.item(row_index, 0)
            if tag_item is None:
                continue
            if tag_item.text().strip() in _TRAILER_TAGS:
                return row_index
        return self._table.rowCount()

    def _detect_delimiter(self, raw_message: str | None) -> str:
        if raw_message and "\x01" in raw_message:
            return "\x01"
        return _DEFAULT_MESSAGE_DELIMITER

    def _is_raw_message_rows(self, rows: list[MessageFieldRow]) -> bool:
        return len(rows) == 1 and rows[0].tag == ""

    def _raw_message_rows(self, raw_message: str) -> list[MessageFieldRow]:
        return [MessageFieldRow(tag="", value=raw_message.strip())]

    def _serializable_field_count(self) -> int:
        rows = self._collect_rows()
        if self._is_raw_message_rows(rows):
            return 1 if rows[0].value else 0
        return sum(1 for row in rows if row.tag)

    def _tag_tooltip(self, tag: str) -> str:
        normalized_tag = tag.strip()
        if not normalized_tag:
            return "Enter a FIX tag number"

        tag_name = _TAG_NAMES.get(normalized_tag)
        if tag_name is None:
            return normalized_tag
        return f"{normalized_tag} — {tag_name}"

    def _update_summary_label(self) -> None:
        if self._has_loaded_message:
            self._summary_label.setText(
                f"{self._source_label} — displaying {self._serializable_field_count()} field(s)"
            )
            return

        self._summary_label.setText(
            "Message Details — displaying placeholder FIX fields"
        )

    @Slot()
    def _on_add_tag_requested(self) -> None:
        row_index = self._insert_row(
            MessageFieldRow(tag="", value=""),
            row_index=self._default_insert_row(),
        )
        self._table.setCurrentCell(row_index, 0)
        target_item = self._table.item(row_index, 0)
        if target_item is not None:
            self._table.editItem(target_item)
        self._table.resizeRowsToContents()
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
                item.setToolTip(self._tag_tooltip(normalized_tag))
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

    def _create_item(
        self,
        value: str,
        *,
        editable: bool,
        tooltip: str | None = None,
    ) -> QTableWidgetItem:
        item = QTableWidgetItem(value)
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setToolTip(tooltip if tooltip is not None else value)
        return item
