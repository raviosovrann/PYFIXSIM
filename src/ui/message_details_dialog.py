from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
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


@dataclass(frozen=True, slots=True)
class MessageFieldRow:
    """One row displayed in the structured FIX message details table."""

    tag: str
    name: str
    value: str


class MessageDetailsDialog(QDialog):
    """Read-only FIX message inspector rendered as a tag/name/value table."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Message Details")
        self.setObjectName("messageDetailsDialog")
        self.resize(760, 440)
        self.setMinimumSize(520, 320)

        self._summary_label = QLabel(self)
        self._summary_label.setObjectName("messageDetailsSummaryLabel")
        self._summary_label.setWordWrap(True)

        self._table = QTableWidget(self)
        self._table.setObjectName("messageDetailsTable")
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Tag", "Name", "Value"])
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
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
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )

        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok,
            parent=self,
        )
        self._button_box.setObjectName("messageDetailsButtonBox")

        self._build_ui()
        self._wire_signals()
        self.set_message_text(None)

    def table_widget(self) -> QTableWidget:
        """Return the read-only details table used by the dialog."""
        return self._table

    def set_message_text(
        self,
        raw_message: str | None,
        *,
        source_label: str = "Message Details",
    ) -> None:
        """Populate the dialog from a raw FIX message or a placeholder sample."""
        rows = self._build_rows(raw_message)
        summary = (
            f"{source_label} — displaying {len(rows)} field(s)"
            if raw_message
            else "Message Details — displaying placeholder FIX fields"
        )
        self._summary_label.setText(summary)
        self._populate_table(rows)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(self._summary_label)
        layout.addWidget(self._table, 1)
        layout.addWidget(self._button_box)

    def _wire_signals(self) -> None:
        self._button_box.accepted.connect(self.accept)

    def _build_rows(self, raw_message: str | None) -> list[MessageFieldRow]:
        if not raw_message or not raw_message.strip():
            return self._placeholder_rows()

        rows: list[MessageFieldRow] = []
        normalized_message = raw_message.replace("\x01", "|")
        for field in normalized_message.split("|"):
            stripped_field = field.strip()
            if not stripped_field:
                continue
            if "=" not in stripped_field:
                logger.debug(
                    "Skipping malformed FIX field in MessageDetailsDialog: %s",
                    stripped_field,
                )
                continue

            tag, value = stripped_field.split("=", 1)
            rows.append(
                MessageFieldRow(
                    tag=tag,
                    name=_TAG_NAMES.get(tag, "Unknown"),
                    value=value,
                )
            )

        if not rows:
            return self._placeholder_rows()

        return self._ensure_admin_rows(rows)

    def _ensure_admin_rows(self, rows: list[MessageFieldRow]) -> list[MessageFieldRow]:
        tags = {row.tag for row in rows}
        normalized_rows = list(rows)

        if "8" not in tags:
            normalized_rows.insert(0, MessageFieldRow("8", _TAG_NAMES["8"], ""))

        if "9" not in tags:
            insert_index = 1 if normalized_rows and normalized_rows[0].tag == "8" else 0
            normalized_rows.insert(
                insert_index,
                MessageFieldRow("9", _TAG_NAMES["9"], ""),
            )

        if "10" not in tags:
            normalized_rows.append(MessageFieldRow("10", _TAG_NAMES["10"], ""))

        return normalized_rows

    def _placeholder_rows(self) -> list[MessageFieldRow]:
        return [
            MessageFieldRow("8", _TAG_NAMES["8"], "FIX.4.4"),
            MessageFieldRow("9", _TAG_NAMES["9"], "112"),
            MessageFieldRow("35", _TAG_NAMES["35"], "D"),
            MessageFieldRow("49", _TAG_NAMES["49"], "CLIENT"),
            MessageFieldRow("56", _TAG_NAMES["56"], "BROKER"),
            MessageFieldRow("11", _TAG_NAMES["11"], "ORDER_0001"),
            MessageFieldRow("55", _TAG_NAMES["55"], "AAPL"),
            MessageFieldRow("54", _TAG_NAMES["54"], "1"),
            MessageFieldRow("38", _TAG_NAMES["38"], "100"),
            MessageFieldRow("44", _TAG_NAMES["44"], "25.50"),
            MessageFieldRow("10", _TAG_NAMES["10"], "123"),
        ]

    def _populate_table(self, rows: list[MessageFieldRow]) -> None:
        self._table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            self._table.setItem(row_index, 0, self._create_item(row.tag))
            self._table.setItem(row_index, 1, self._create_item(row.name))
            self._table.setItem(row_index, 2, self._create_item(row.value))

        self._table.resizeRowsToContents()

    @Slot()
    def accept(self) -> None:
        super().accept()

    def _create_item(self, value: str) -> QTableWidgetItem:
        item = QTableWidgetItem(value)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setToolTip(value)
        return item
