---
description: "Use when writing or modifying Python UI code in src/ui/ with PySide6. Covers widget creation, layout management, signal/slot patterns, and keeping UI handlers free of direct FIX engine calls."
applyTo: "src/ui/**/*.py"
---

# Python UI Guidelines

## Source of truth

All UI requirements — layout, components, dialogs, color palette, field specs,
and MVP scope — are defined in `ui-requirements.md` at the repo root.
**Read it before starting any implementation task.**
Section 17 of that file defines the MVP build priority (Must / Should / Could).

## File ownership

Each file under `src/ui/` owns exactly one primary component:

| File | Component | Status |
|------|-----------|--------|
| `src/ui/main_window.py` | `MainWindow` — `QMainWindow` shell, menu bar, splitters, status bar | ☑ complete |
| `src/ui/session_widget.py` | `SessionListWidget` — left-pane session list, status indicators, context menu | ☑ complete |
| `src/ui/order_panel.py` | `SendMessageTab` + `ReplayTab` — right-panel tabbed workspace | ☐ not started |
| `src/ui/message_log.py` | `EventsViewer` — lower log panel, colour coding, filter bar, split/grid modes | ☐ not started |
| `src/ui/controller.py` | `AppController` — wires all widget signals to `FIXEngineService` | ☐ not started |

Dialogs live in their own files created alongside the above:

| File | Component |
|------|-----------|
| `src/ui/create_session_dialog.py` | `CreateSessionDialog` |
| `src/ui/message_details_dialog.py` | `MessageDetailsDialog` |
| `src/ui/table_view_editor.py` | `TableViewEditor` (F4) |
| `src/ui/test_scenarios_tab.py` | `TestScenariosTab` |

## Default targeting rule

When the user asks to build "the next UI item", "continue the checklist", or
names a component without naming a file, do **not** ask where to write code if
the mapping is already present in the File ownership table above.

Resolve the target automatically:

- `MainWindow` → `src/ui/main_window.py`
- `SessionListWidget` → `src/ui/session_widget.py`
- `SendMessageTab` / `ReplayTab` → `src/ui/order_panel.py`
- `EventsViewer` → `src/ui/message_log.py`
- `AppController` → `src/ui/controller.py`
- dialogs / auxiliary widgets → their dedicated dialog files listed above

Only ask the user for a target file if the ownership table is missing an entry
or the request explicitly conflicts with the default mapping.

## Build order (MVP first)

Work through this list top to bottom. Mark a step done only when the widget
renders correctly in a running `python src/main.py` **and** every acceptance
bullet under that step is satisfied.

If the agent cannot run the UI locally, or if the user validates the UI in
their own environment first, the user's explicit confirmation that the
implementation works counts as approval to mark that checklist item complete.
When relying on user approval, keep the acceptance bullets honest — do not mark
an item done unless the implementation appears to satisfy the written criteria.

- [x] 1. `MainWindow` — application shell
  - `QMainWindow` with window title, sensible minimum size, and central widget
  - menu bar contains `Session`, `Message`, `Events Viewer`, `Options`, `Help`
  - primary layout uses splitters: left session pane, right tab workspace,
    lower events viewer
  - tab workspace includes `Send Message`, `Replay`, `Test Scenarios`
  - status bar shows placeholder application/session state text
- [x] 2. `SessionListWidget` — session list pane
  - shows one visible list control for sessions in the left pane
  - each row supports compact multiline summary text
  - row visual includes a state indicator for waiting/connected/error
  - right-click menu includes `Refresh`, `Start`, `Stop`, `Restart`,
    `Show session messages`, `Close session`
  - selection change emits a signal for the controller / parent widget
- [x] 3. `CreateSessionDialog` — FIX session dialog
  - left column includes required FIX fields from `ui-requirements.md`
  - session type uses `Initiator` / `Acceptor` radio buttons
  - right column contains extended properties area with disabled/hidden
    optional controls until enabled
  - includes `Use Extended properties`, `Show session messages`, and
    `Use SSL` toggles
  - includes `OK` / `Cancel`; required numeric fields validate cleanly
- [x] 4. `SendMessageTab` — manual send workspace
  - editable `QPlainTextEdit` for raw FIX text / arbitrary Kafka text
  - controls for session selector, rate, send count
  - buttons for `Send all`, `Send current and go Next`, `Reset`,
    `Record Test Scenario`
  - autoincrement tags field visible below the editor
  - editor exposes context-menu hooks for load / save / edit / insert `<SOH>`
- [x] 5. `EventsViewer` — lower log panel
  - default view shows a scrolling log area for events/messages
  - colour coding distinguishes incoming, outgoing, and console/system entries
  - bottom controls include timestamp/header-trailer/application/session toggles
  - includes `Incoming`, `Outgoing`, `Console` filters and free-text filter box
  - supports clear + auto-scroll actions, even if first version is stubbed
- [ ] 6. `AppController` — first UI wiring pass
  - receives session-create requests from dialog and send requests from tabs
  - owns signal wiring between widgets and future `FIXEngineService`
  - contains no widget layout code
  - uses placeholder / stub handlers if engine service is still empty
  - updates status bar and selected-session context through signals
- [ ] 7. `MessageDetailsDialog` — FIX message inspector
  - read-only table with `Tag`, `Name`, `Value` columns
  - supports opening from events viewer selection / future hook
  - window has `OK` close action
  - handles long values without breaking layout
  - safe to populate with mock data in first version
- [ ] 8. `ReplayTab` — replay controls
  - file picker / path field for replay log file
  - controls for sequence range, rate, send count, optional timestamps toggle
  - buttons for `Play`, `Pause`, `Stop`, `Next`
  - speed control present
  - lower edge integrates with events viewer / status updates via signals
- [ ] 9. `TableViewEditor` — editable tag grid
  - table supports tag rows with add / remove actions
  - columns show tag number, human-readable name, value
  - opening via F4 / context-menu hook from send editor is wired or stubbed
  - saving pushes reconstructed message back into `SendMessageTab`
  - repeating-group support may be simplified in v1 but structure must allow it
- [ ] 10. `TestScenariosTab` — scenario runner surface
  - table includes `Action`, `Test Scenario Name`, `Session`, `Details`
  - top-level button for `Create Test Scenario`
  - row action supports placeholder `Run`, later `Cancel` / `Continue`
  - designer dialog / hook is stubbed or wired for future expansion
  - empty-state text or placeholder data makes the tab visually testable

## Signal contract (non-negotiable)

- UI handlers **never** call the FIX engine directly.
- Every user action emits a `Signal` or calls a method on `AppController`.
- Cross-thread engine → UI updates go through `EngineAdapter(QObject)` with
  automatic queued connections (see `python-ui-developer` agent for the pattern).
- Decorate every slot with `@Slot`.

## Coding rules

- PySide6 `Signal` / `@Slot` — not `pyqtSignal` / `pyqtSlot`
- Full type hints on all public methods and `__init__` signatures
- PEP 8; max line length 99 characters
- One primary widget class per file
- Prefer `QSplitter`, `QTabWidget`, `QTableView`, `QPlainTextEdit`, `QDialog` — no QML
- `logging.getLogger(__name__)` everywhere — never `print()`
- Dark theme: apply the colour palette from section 1 of `ui-requirements.md`
  via a centralised QSS stylesheet at `src/ui/theme.py`
