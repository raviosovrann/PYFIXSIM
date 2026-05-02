---
description: "Use when writing or modifying Python UI code in src/ui/ with PySide6. Covers widget creation, layout management, signal/slot patterns, and keeping UI handlers free of direct FIX engine calls."
applyTo: "src/ui/**/*.py"
---

# Python UI Guidelines

- Use PySide6 signals and slots (`Signal`, `@Slot`) for event handling; never call FIX engine methods directly from a UI handler
- Emit signals or call a controller/service layer to bridge UI ↔ engine
- Keep each widget class in its own file under `src/ui/`
- Use type hints for all method signatures
- Follow PEP 8; max line length 99 characters
