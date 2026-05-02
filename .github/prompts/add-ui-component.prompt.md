---
description: "Scaffold a new UI component or view in src/ui/."
---

Create a new UI component named `$componentName` in `src/ui/`.

- Use PySide6 (`Signal`, `@Slot`, `QWidget` subclasses)
- Keep all event handlers free of direct FIX engine calls — emit signals instead
- Include a `__init__` with type-hinted parameters
- Follow the project's widget-per-file convention
- Add the component to the appropriate parent view if specified: `$parentView`
