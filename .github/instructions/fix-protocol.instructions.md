---
description: "Use when constructing, parsing, or validating FIX protocol messages. Covers FIX 4.2–5.0 tag names, required/optional fields, message types (D, 8, 35, etc.), session-level vs. application-level messages, and quickfix data dictionary usage."
applyTo: "src/messages/**/*.py"
---

# FIX Protocol Conventions

- Always use standard FIX tag names as variable/attribute names (e.g., `ClOrdID`, `Symbol`, `OrdType`)
- Reference `src/config/` data dictionaries for required and optional fields per message type
- Validate required fields before sending; raise a descriptive error if a required field is missing
- Use FIX version-specific message type constants (e.g., `fix.MsgType_NewOrderSingle`)
- Document the FIX version targeted by each message class
