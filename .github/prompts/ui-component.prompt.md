---
description: "Build or extend a UI component for the FIX Client Simulator. Use this prompt to implement, continue, or review any widget, dialog, or panel in src/ui/."
agent: "python-ui-developer"
---

# Build UI Component — FIXSIM

## Before you write a single line

1. Read `ui-requirements.md` — it is the sole source of truth for what to build,
   how each component should look, and what fields/buttons/behaviours it needs.
2. Open `.github/instructions/python-ui.instructions.md` and find the **first
   unchecked item** in the Build Order list — that is your current task unless
   the user has specified otherwise.
3. Read the target file (e.g. `src/ui/main_window.py`) to understand current
   state before touching it.

## Current task

Implement or extend: **${componentName}**

Relevant section in `ui-requirements.md`: **${requirementsSection}**

Target file: **${targetFile}**

If `${componentName}` is not specified, pick the first unchecked step from the
build order in `python-ui.instructions.md`, infer the owning file from the File
ownership table there, and begin there without asking the user for the file
path unless the ownership mapping is missing or ambiguous.

## How to implement

1. Subclass the correct Qt base (`QWidget`, `QDialog`, `QMainWindow`, …).
2. Declare all outbound signals at class level using `Signal(type)`.
3. Build the full layout inside `__init__` using `QFormLayout`, `QVBoxLayout`,
   `QHBoxLayout`, or `QSplitter` as appropriate — no inline layout logic outside
   `__init__`.
4. Connect internal widget signals to private `_on_*` methods and decorate each
   with `@Slot`.
5. `_on_*` methods must only **emit signals** or **call `AppController`** — never
   call the FIX engine directly.
6. Wire the new component into its parent widget or register it in
   `src/ui/controller.py`.
7. Apply the dark theme colours from `ui-requirements.md` section 1 via
   `src/ui/theme.py` — do not hardcode hex values in widget files.

## Done checklist

Before marking the build-order item as complete:

- [ ] Every acceptance bullet under the current numbered step in
   `python-ui.instructions.md` is satisfied
- [ ] All public methods and `__init__` have full type hints
- [ ] No direct engine calls inside any slot or handler
- [ ] Labels, button text, and tab names match `ui-requirements.md` wording
- [ ] Layout is compact and resize-safe; no large empty gaps caused by bad stretch
- [ ] Component is visible and functional via `python src/main.py`
- [ ] Dark theme colours applied (no hardcoded hex in the widget file)
- [ ] Outbound signals are documented with a one-line comment
- [ ] Placeholder/mock state is used where backend behavior is not implemented yet
- [ ] Widget wired into parent or `AppController`
- [ ] Build-order checkbox in `python-ui.instructions.md` marked `[x]`

If the agent cannot run the UI locally, it may ask the human user to verify the
implementation. Once the user explicitly confirms that it works, that approval
counts as permission to mark the checklist item complete, provided the written
acceptance bullets also appear satisfied.
