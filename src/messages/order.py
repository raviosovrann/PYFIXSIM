from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import simplefix  # type: ignore[import-untyped]

from src.config.session_config import SessionConfig

_NEW_ORDER_SINGLE_MSG_TYPE = "D"
_EXECUTION_REPORT_MSG_TYPE = "8"
_DEFAULT_HANDL_INST = "1"
_LIMIT_ORD_TYPE = "2"


class MessageError(Exception):
    """Base exception for FIX application message errors."""


class MessageValidationError(MessageError):
    """Raised when a FIX field is missing or invalid."""

    def __init__(self, tag: int, reason: str) -> None:
        super().__init__(f"Tag {tag}: {reason}")
        self.tag = tag
        self.reason = reason


def _utc_timestamp() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%d-%H:%M:%S.%f")[:-3]


def _require_text(value: object, *, tag: int) -> str:
    if value is None:
        raise MessageValidationError(tag, "value is required")

    text = str(value).strip()
    if not text:
        raise MessageValidationError(tag, "value is required")
    return text


def _optional_text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _positive_int(value: object, *, tag: int) -> int:
    if isinstance(value, bool):
        raise MessageValidationError(tag, f"expected integer, got {value!r}")

    if isinstance(value, int):
        int_value = value
    else:
        try:
            int_value = int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise MessageValidationError(
                tag,
                f"expected integer, got {value!r}",
            ) from exc

    if int_value <= 0:
        raise MessageValidationError(tag, "must be greater than zero")
    return int_value


def _non_negative_int(value: object, *, tag: int) -> int:
    if isinstance(value, bool):
        raise MessageValidationError(tag, f"expected integer, got {value!r}")

    if isinstance(value, int):
        int_value = value
    else:
        try:
            int_value = int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise MessageValidationError(
                tag,
                f"expected integer, got {value!r}",
            ) from exc

    if int_value < 0:
        raise MessageValidationError(tag, "must be zero or greater")
    return int_value


def _optional_float(value: object | None, *, tag: int) -> float | None:
    if value is None or str(value).strip() == "":
        return None

    if isinstance(value, bool):
        raise MessageValidationError(tag, f"expected decimal, got {value!r}")

    try:
        float_value = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise MessageValidationError(tag, f"expected decimal, got {value!r}") from exc

    return float_value


def _required_float(value: object, *, tag: int) -> float:
    float_value = _optional_float(value, tag=tag)
    if float_value is None:
        raise MessageValidationError(tag, "value is required")
    return float_value


def _format_decimal(value: float) -> str:
    return format(value, "f").rstrip("0").rstrip(".") or "0"


def _decode_required_field(message: simplefix.FixMessage, tag: int) -> str:
    raw_value = message.get(tag)
    if raw_value is None:
        raise MessageValidationError(tag, "field is required")
    return bytes(raw_value).decode("utf-8", errors="replace").strip()


def _decode_optional_field(message: simplefix.FixMessage, tag: int) -> str:
    raw_value = message.get(tag)
    if raw_value is None:
        return ""
    return bytes(raw_value).decode("utf-8", errors="replace").strip()


@dataclass(slots=True)
class NewOrderSingle:
    """FIX 4.2 NewOrderSingle (35=D) application message."""

    ClOrdID: str
    Symbol: str
    Side: str
    OrderQty: int
    OrdType: str
    Price: float | None = None
    HandlInst: str = _DEFAULT_HANDL_INST
    Account: str = ""
    TimeInForce: str = ""
    Text: str = ""
    TransactTime: str | None = None

    def __post_init__(self) -> None:
        self.ClOrdID = _require_text(self.ClOrdID, tag=11)
        self.Symbol = _require_text(self.Symbol, tag=55)
        self.Side = _require_text(self.Side, tag=54)
        self.OrderQty = _positive_int(self.OrderQty, tag=38)
        self.OrdType = _require_text(self.OrdType, tag=40)
        self.Price = _optional_float(self.Price, tag=44)
        self.HandlInst = _require_text(self.HandlInst, tag=21)
        self.Account = _optional_text(self.Account)
        self.TimeInForce = _optional_text(self.TimeInForce)
        self.Text = _optional_text(self.Text)
        self.TransactTime = _optional_text(self.TransactTime) or _utc_timestamp()

    def validate(self) -> None:
        """Validate required FIX fields before encoding the message."""
        _require_text(self.ClOrdID, tag=11)
        _require_text(self.Symbol, tag=55)
        _require_text(self.Side, tag=54)
        _positive_int(self.OrderQty, tag=38)
        _require_text(self.OrdType, tag=40)
        _require_text(self.HandlInst, tag=21)
        _require_text(self.TransactTime, tag=60)

        if self.OrdType == _LIMIT_ORD_TYPE and self.Price is None:
            raise MessageValidationError(44, "Price is required for limit orders")

        if self.Price is not None and self.Price <= 0:
            raise MessageValidationError(44, "Price must be greater than zero")

    def to_fix_message(
        self,
        config: SessionConfig,
        MsgSeqNum: int,
    ) -> simplefix.FixMessage:
        """Encode the order as a FIX 4.2 NewOrderSingle message."""
        self.validate()
        message = simplefix.FixMessage()
        message.append_pair(8, config.fix_version)
        message.append_pair(35, _NEW_ORDER_SINGLE_MSG_TYPE)
        message.append_pair(49, config.sender_comp_id)
        message.append_pair(56, config.target_comp_id)
        message.append_pair(34, str(MsgSeqNum))
        message.append_pair(52, _utc_timestamp())
        message.append_pair(11, self.ClOrdID)
        message.append_pair(21, self.HandlInst)
        if self.Account:
            message.append_pair(1, self.Account)
        message.append_pair(55, self.Symbol)
        message.append_pair(54, self.Side)
        message.append_pair(60, self.TransactTime)
        message.append_pair(38, str(self.OrderQty))
        message.append_pair(40, self.OrdType)
        if self.TimeInForce:
            message.append_pair(59, self.TimeInForce)
        if self.Price is not None:
            message.append_pair(44, _format_decimal(self.Price))
        if self.Text:
            message.append_pair(58, self.Text)
        return message


@dataclass(slots=True)
class ExecutionReport:
    """FIX 4.2 ExecutionReport (35=8) parser result for V1 UI/backend flows."""

    OrderID: str
    ExecID: str
    ExecType: str
    OrdStatus: str
    ClOrdID: str
    Symbol: str
    Side: str
    LeavesQty: int
    CumQty: int
    AvgPx: float
    OrderQty: int | None = None
    LastQty: float | None = None
    LastPx: float | None = None
    TransactTime: str = ""
    Text: str = ""

    def __post_init__(self) -> None:
        self.OrderID = _require_text(self.OrderID, tag=37)
        self.ExecID = _require_text(self.ExecID, tag=17)
        self.ExecType = _require_text(self.ExecType, tag=150)
        self.OrdStatus = _require_text(self.OrdStatus, tag=39)
        self.ClOrdID = _require_text(self.ClOrdID, tag=11)
        self.Symbol = _require_text(self.Symbol, tag=55)
        self.Side = _require_text(self.Side, tag=54)
        self.LeavesQty = _non_negative_int(self.LeavesQty, tag=151)
        self.CumQty = _non_negative_int(self.CumQty, tag=14)
        self.AvgPx = _required_float(self.AvgPx, tag=6)
        self.OrderQty = (
            _positive_int(self.OrderQty, tag=38) if self.OrderQty is not None else None
        )
        self.LastQty = _optional_float(self.LastQty, tag=32)
        self.LastPx = _optional_float(self.LastPx, tag=31)
        self.TransactTime = _optional_text(self.TransactTime)
        self.Text = _optional_text(self.Text)

    @classmethod
    def from_fix_message(cls, message: simplefix.FixMessage) -> "ExecutionReport":
        """Parse core ExecutionReport fields from a FIX 4.2 message."""
        msg_type = _decode_required_field(message, 35)
        if msg_type != _EXECUTION_REPORT_MSG_TYPE:
            raise MessageValidationError(35, "expected ExecutionReport message type 8")

        order_qty_text = _decode_optional_field(message, 38)
        last_qty_text = _decode_optional_field(message, 32)
        last_px_text = _decode_optional_field(message, 31)

        return cls(
            OrderID=_decode_required_field(message, 37),
            ExecID=_decode_required_field(message, 17),
            ExecType=_decode_required_field(message, 150),
            OrdStatus=_decode_required_field(message, 39),
            ClOrdID=_decode_required_field(message, 11),
            Symbol=_decode_required_field(message, 55),
            Side=_decode_required_field(message, 54),
            LeavesQty=_non_negative_int(_decode_required_field(message, 151), tag=151),
            CumQty=_non_negative_int(_decode_required_field(message, 14), tag=14),
            AvgPx=_required_float(_decode_required_field(message, 6), tag=6),
            OrderQty=(
                _positive_int(order_qty_text, tag=38) if order_qty_text else None
            ),
            LastQty=_optional_float(last_qty_text, tag=32),
            LastPx=_optional_float(last_px_text, tag=31),
            TransactTime=_decode_optional_field(message, 60),
            Text=_decode_optional_field(message, 58),
        )


__all__ = [
    "ExecutionReport",
    "MessageError",
    "MessageValidationError",
    "NewOrderSingle",
]
