from __future__ import annotations

TAG_NAMES: dict[str, str] = {
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

DEFAULT_MESSAGE_DELIMITER = "|"
FIX_MESSAGE_DELIMITER = "\x01"
TRAILER_TAGS: frozenset[str] = frozenset({"10"})


def contains_fix_message_delimiter(raw_message: str) -> bool:
    """Return whether the FIX SOH delimiter is present in the raw message."""
    return FIX_MESSAGE_DELIMITER in raw_message


def contains_pipe_delimiter(raw_message: str) -> bool:
    """Return whether the display-friendly pipe delimiter is present."""
    return DEFAULT_MESSAGE_DELIMITER in raw_message