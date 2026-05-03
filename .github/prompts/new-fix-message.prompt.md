---
description: "Scaffold a new FIX application-level message class in src/messages/."
---

Create a new FIX message class for the message type `$messageType` (e.g., NewOrderSingle, ExecutionReport).

- Place the file in `src/messages/`
- Use standard FIX tag names as attributes (`ClOrdID`, `Symbol`, etc.)
- Include required fields for this message type according to the FIX spec
- Add a `to_fix_message()` method returning a `quickfix.Message`
- Add a `from_fix_message(msg)` class method for parsing
- Include type hints and a brief docstring describing the message type
