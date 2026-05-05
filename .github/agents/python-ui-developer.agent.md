---
description: "Use when building or modifying UI components, views, dialogs, or layouts in src/ui/ using PySide6. Handles UI event bindings, widget styling, and keeping UI logic decoupled from FIX engine logic."
tools: [vscode/getProjectSetupInfo, vscode/installExtension, vscode/memory, vscode/newWorkspace, vscode/resolveMemoryFileUri, vscode/runCommand, vscode/vscodeAPI, vscode/extensions, vscode/askQuestions, execute/runNotebookCell, execute/getTerminalOutput, execute/killTerminal, execute/sendToTerminal, execute/createAndRunTask, execute/runInTerminal, execute/runTests, read/getNotebookSummary, read/problems, read/readFile, read/viewImage, read/readNotebookCellOutput, read/terminalSelection, read/terminalLastCommand, agent/runSubagent, edit/createDirectory, edit/createFile, edit/createJupyterNotebook, edit/editFiles, edit/editNotebook, edit/rename, search/changes, search/codebase, search/fileSearch, search/listDirectory, search/textSearch, search/searchSubagent, search/usages, web/fetch, web/githubRepo, web/githubTextSearch, github/add_comment_to_pending_review, github/add_issue_comment, github/add_reply_to_pull_request_comment, github/assign_copilot_to_issue, github/create_branch, github/create_or_update_file, github/create_pull_request, github/create_pull_request_with_copilot, github/create_repository, github/delete_file, github/fork_repository, github/get_commit, github/get_copilot_job_status, github/get_file_contents, github/get_label, github/get_latest_release, github/get_me, github/get_release_by_tag, github/get_tag, github/get_team_members, github/get_teams, github/issue_read, github/issue_write, github/list_branches, github/list_commits, github/list_issue_types, github/list_issues, github/list_pull_requests, github/list_releases, github/list_tags, github/merge_pull_request, github/pull_request_read, github/pull_request_review_write, github/push_files, github/request_copilot_review, github/run_secret_scanning, github/search_code, github/search_issues, github/search_pull_requests, github/search_repositories, github/search_users, github/sub_issue_write, github/update_pull_request, github/update_pull_request_branch, browser/openBrowserPage, browser/readPage, browser/screenshotPage, browser/navigatePage, browser/clickElement, browser/dragElement, browser/hoverElement, browser/typeInPage, browser/runPlaywrightCode, browser/handleDialog, pylance-mcp-server/pylanceDocString, pylance-mcp-server/pylanceDocuments, pylance-mcp-server/pylanceFileSyntaxErrors, pylance-mcp-server/pylanceImports, pylance-mcp-server/pylanceInstalledTopLevelModules, pylance-mcp-server/pylanceInvokeRefactoring, pylance-mcp-server/pylancePythonEnvironments, pylance-mcp-server/pylanceRunCodeSnippet, pylance-mcp-server/pylanceSettings, pylance-mcp-server/pylanceSyntaxErrors, pylance-mcp-server/pylanceUpdatePythonEnvironment, pylance-mcp-server/pylanceWorkspaceRoots, pylance-mcp-server/pylanceWorkspaceUserFiles, vscode.mermaid-chat-features/renderMermaidDiagram, github.vscode-pull-request-github/issue_fetch, github.vscode-pull-request-github/labels_fetch, github.vscode-pull-request-github/notification_fetch, github.vscode-pull-request-github/doSearch, github.vscode-pull-request-github/activePullRequest, github.vscode-pull-request-github/pullRequestStatusChecks, github.vscode-pull-request-github/openPullRequest, github.vscode-pull-request-github/create_pull_request, github.vscode-pull-request-github/resolveReviewThread, ms-python.python/getPythonEnvironmentInfo, ms-python.python/getPythonExecutableCommand, ms-python.python/installPythonPackage, ms-python.python/configurePythonEnvironment, todo]
model: [GPT-5.4, Claude Sonnet 4.6]
---

# Python Desktop UI Patterns — FIX Client Simulator

PySide6 patterns and best practices for building the FIXSIM desktop UI under `src/ui/`. All patterns enforce strict separation between UI and FIX engine logic.

## When to Activate

- Building or modifying widgets, views, and dialogs in `src/ui/`
- Connecting UI events to engine actions via signals/slots
- Displaying live FIX session state, order blotter, or message logs
- Implementing order entry forms with validation
- Running background tasks (session connect, message polling) without freezing the UI
- Styling and laying out PySide6 widgets
- Adding keyboard shortcuts or accessibility support

## Core Rule

> **Never call the FIX engine directly from a UI handler.**
> UI slots emit signals or call a controller/service interface. The engine lives in `src/engine/` and knows nothing about widgets.

---

## Widget Composition Patterns

### Single-Responsibility Widget

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Signal

class SessionStatusWidget(QWidget):
    """Displays the current FIX session state and emits connect/disconnect requests."""

    connect_requested = Signal()
    disconnect_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status_label = QLabel("DISCONNECTED")
        self._connect_btn = QPushButton("Connect")
        self._disconnect_btn = QPushButton("Disconnect")

        self._connect_btn.clicked.connect(self.connect_requested)
        self._disconnect_btn.clicked.connect(self.disconnect_requested)

        layout = QVBoxLayout(self)
        layout.addWidget(self._status_label)
        layout.addWidget(self._connect_btn)
        layout.addWidget(self._disconnect_btn)

    def set_status(self, status: str) -> None:
        """Called by the controller when session state changes."""
        self._status_label.setText(status)
```

### Composite Widget (Composition Over Inheritance)

```python
from PySide6.QtWidgets import QGroupBox, QFormLayout, QLineEdit, QComboBox

class OrderEntryPanel(QGroupBox):
    """Composite widget combining all order entry fields."""

    order_submitted = Signal(dict)   # emits validated field dict to controller

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("New Order", parent)
        self._symbol = QLineEdit()
        self._side = QComboBox()
        self._side.addItems(["Buy", "Sell"])
        self._qty = QLineEdit()
        self._price = QLineEdit()
        self._submit_btn = QPushButton("Send Order")

        self._submit_btn.clicked.connect(self._on_submit)

        layout = QFormLayout(self)
        layout.addRow("Symbol:", self._symbol)
        layout.addRow("Side:", self._side)
        layout.addRow("Quantity:", self._qty)
        layout.addRow("Price:", self._price)
        layout.addWidget(self._submit_btn)

    def _on_submit(self) -> None:
        """Validate locally then emit — never call engine directly."""
        data = self._collect_fields()
        if data:
            self.order_submitted.emit(data)

    def _collect_fields(self) -> dict | None:
        try:
            return {
                "Symbol": self._symbol.text().strip(),
                "Side": "1" if self._side.currentText() == "Buy" else "2",
                "OrderQty": int(self._qty.text()),
                "Price": float(self._price.text()) if self._price.text() else None,
            }
        except ValueError:
            self._show_validation_error()
            return None

    def _show_validation_error(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "Validation Error", "Check quantity and price fields.")
```

### Reusable Dialog

```python
from PySide6.QtWidgets import QDialog, QDialogButtonBox

class SessionConfigDialog(QDialog):
    """Modal dialog for editing FIX session configuration."""

    def __init__(self, config: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Session Configuration")
        self._host = QLineEdit(config.get("host", ""))
        self._port = QLineEdit(str(config.get("port", 9876)))
        self._sender = QLineEdit(config.get("SenderCompID", ""))
        self._target = QLineEdit(config.get("TargetCompID", ""))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QFormLayout(self)
        layout.addRow("Host:", self._host)
        layout.addRow("Port:", self._port)
        layout.addRow("SenderCompID:", self._sender)
        layout.addRow("TargetCompID:", self._target)
        layout.addWidget(buttons)

    def get_config(self) -> dict:
        return {
            "host": self._host.text(),
            "port": int(self._port.text()),
            "SenderCompID": self._sender.text(),
            "TargetCompID": self._target.text(),
        }
```

---

## Signal / Slot Patterns

### Controller Bridges UI ↔ Engine

```python
# src/ui/controller.py
from PySide6.QtCore import QObject, Slot
from src.engine.service import FIXEngineService
from src.ui.main_window import MainWindow

class AppController(QObject):
    """Wires MainWindow signals to FIXEngineService calls."""

    def __init__(self, window: MainWindow, engine: FIXEngineService) -> None:
        super().__init__()
        self._window = window
        self._engine = engine

        # UI → engine
        window.session_panel.connect_requested.connect(self._on_connect)
        window.order_panel.order_submitted.connect(self._on_order_submitted)

        # engine → UI  (engine emits Qt signals on its own QObject)
        engine.session_state_changed.connect(window.session_panel.set_status)
        engine.execution_report_received.connect(window.blotter.add_execution)

    @Slot()
    def _on_connect(self) -> None:
        self._engine.connect()

    @Slot(dict)
    def _on_order_submitted(self, order: dict) -> None:
        self._engine.send_new_order_single(order)
```

### Thread-Safe Engine → UI Updates

```python
# Engine lives on a background thread; must post to UI thread via queued connection.
from PySide6.QtCore import QObject, Signal, Qt

class EngineAdapter(QObject):
    """Qt-signal bridge between the FIX engine thread and the UI thread."""

    session_state_changed = Signal(str)         # e.g. "ACTIVE"
    execution_report_received = Signal(dict)    # ExecReport fields

    # Called from the engine thread — Qt delivers it on the UI thread
    # because the connection type is AutoConnection (queued across threads).
    def on_session_state(self, state: str) -> None:
        self.session_state_changed.emit(state)

    def on_execution_report(self, fields: dict) -> None:
        self.execution_report_received.emit(fields)
```

---

## Model-View Patterns

### QAbstractTableModel for Message Log

```python
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import QTableView

COLUMNS = ["Time", "Dir", "MsgType", "SeqNum", "Raw"]

class MessageLogModel(QAbstractTableModel):
    """Table model backed by a list of FIX message records."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        row = self._rows[index.row()]
        return row.get(COLUMNS[index.column()], "")

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def append_message(self, record: dict) -> None:
        row = len(self._rows)
        self.beginInsertRows(QModelIndex(), row, row)
        self._rows.append(record)
        self.endInsertRows()

    def clear(self) -> None:
        self.beginResetModel()
        self._rows.clear()
        self.endResetModel()
```

---

## Background Task Patterns

### QThread for Long-Running Engine Tasks

```python
from PySide6.QtCore import QThread, Signal

class SessionWorker(QThread):
    """Run the FIX session connect + read loop off the UI thread."""

    state_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, engine: FIXEngineService) -> None:
        super().__init__()
        self._engine = engine

    def run(self) -> None:
        try:
            self._engine.connect()
            self.state_changed.emit("ACTIVE")
            self._engine.run_receive_loop()   # blocks until disconnect
        except OSError as exc:
            self.error_occurred.emit(str(exc))
        finally:
            self.state_changed.emit("DISCONNECTED")

# Usage in controller
worker = SessionWorker(engine)
worker.state_changed.connect(window.session_panel.set_status)
worker.error_occurred.connect(window.show_error)
worker.start()
```

### QTimer for Periodic UI Refresh

```python
from PySide6.QtCore import QTimer

class OrderBlotterWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = MessageLogModel()
        self._view = QTableView()
        self._view.setModel(self._model)

        # Refresh pending-order highlights every second
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1000)
        self._refresh_timer.timeout.connect(self._refresh_highlights)
        self._refresh_timer.start()

    def _refresh_highlights(self) -> None:
        # Update row colours for stale orders without rebuilding the model
        self._model.layoutChanged.emit()
```

---

## Form Validation Patterns

### QValidator for FIX Field Inputs

```python
from PySide6.QtGui import QValidator, QIntValidator, QDoubleValidator
from PySide6.QtWidgets import QLineEdit

class SymbolValidator(QValidator):
    """Accept only uppercase alphanumeric ticker symbols (max 10 chars)."""

    def validate(self, input_str: str, pos: int) -> tuple[QValidator.State, str, int]:
        cleaned = input_str.upper()
        if all(c.isalnum() or c in (".", "/") for c in cleaned) and len(cleaned) <= 10:
            return QValidator.State.Acceptable, cleaned, pos
        if cleaned == "":
            return QValidator.State.Intermediate, cleaned, pos
        return QValidator.State.Invalid, input_str, pos

# Apply validators at widget creation time
symbol_edit = QLineEdit()
symbol_edit.setValidator(SymbolValidator())

qty_edit = QLineEdit()
qty_edit.setValidator(QIntValidator(1, 10_000_000))

price_edit = QLineEdit()
price_edit.setValidator(QDoubleValidator(0.0001, 999_999.0, 4))
```

---

## Layout Patterns

### Responsive Layout with Splitters

```python
from PySide6.QtWidgets import QMainWindow, QSplitter, QWidget
from PySide6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FIXSIM — FIX Client Simulator")
        self.resize(1280, 800)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: session + order entry
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.session_panel = SessionStatusWidget()
        self.order_panel = OrderEntryPanel()
        left_layout.addWidget(self.session_panel)
        left_layout.addWidget(self.order_panel)
        left_layout.addStretch()

        # Right panel: message log
        self.blotter = OrderBlotterWidget()

        splitter.addWidget(left)
        splitter.addWidget(self.blotter)
        splitter.setSizes([380, 900])

        self.setCentralWidget(splitter)
```

---

## Error & Status Feedback Patterns

```python
from PySide6.QtWidgets import QStatusBar, QMessageBox

class MainWindow(QMainWindow):

    def show_error(self, message: str) -> None:
        """Non-blocking status bar error — does not freeze the UI."""
        self.statusBar().showMessage(f"Error: {message}", 5000)

    def show_critical(self, title: str, message: str) -> None:
        """Blocking modal — use only for unrecoverable errors."""
        QMessageBox.critical(self, title, message)
```

---

## Keyboard Shortcuts & Accessibility

```python
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication

class MainWindow(QMainWindow):
    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+N"), self, self.order_panel.focus_symbol)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)
        QShortcut(QKeySequence("F5"),     self, self.session_panel.connect_requested)

    def _setup_accessibility(self) -> None:
        self.session_panel.setAccessibleName("Session Status Panel")
        self.order_panel.setAccessibleName("Order Entry Form")
        self.blotter.setAccessibleName("Message Blotter")
```

---

## Anti-Patterns to Avoid

```python
# BAD: calling engine directly from a UI slot
def _on_buy_clicked(self):
    self._session.send(NewOrderSingle(...))   # NEVER — UI must not touch engine

# GOOD: emit a signal, let the controller wire it to the engine
def _on_buy_clicked(self):
    self.order_submitted.emit(self._collect_fields())

# BAD: blocking the UI thread with network I/O
def _on_connect(self):
    self._engine.connect()   # blocks UI for seconds if server is slow

# GOOD: move blocking work to QThread
def _on_connect(self):
    self._worker = SessionWorker(self._engine)
    self._worker.state_changed.connect(self.session_panel.set_status)
    self._worker.start()

# BAD: updating a widget from a non-UI thread
def engine_callback(state):
    label.setText(state)     # crash or corruption — not thread-safe

# GOOD: emit a signal (Qt queues it to the UI thread automatically)
def engine_callback(state):
    self.adapter.state_changed.emit(state)

# BAD: building the whole UI in __init__ with no separation
class MainWindow(QMainWindow):
    def __init__(self):
        # 500 lines of widget creation here

# GOOD: delegate to sub-widgets, each in their own file under src/ui/
```

---

## Quick Reference

| Pattern | PySide6 API |
|---------|-------------|
| Custom signal | `Signal(str)` on `QObject` subclass |
| Slot decorator | `@Slot(str)` |
| Cross-thread update | Queued signal/slot (automatic for different threads) |
| Table display | `QAbstractTableModel` + `QTableView` |
| Background task | `QThread` subclass with `run()` |
| Periodic refresh | `QTimer` |
| Input validation | `QValidator` subclass |
| Non-blocking status | `QStatusBar.showMessage()` |
| Modal error | `QMessageBox.critical()` |
| Layout with resize | `QSplitter` |
| Keyboard shortcut | `QShortcut(QKeySequence(...), parent, slot)` |

**Remember**: PySide6 is strictly single-threaded for UI operations. All widget reads and writes must happen on the main thread. Use signals to safely post work from the engine thread to the UI thread.

---

## Python Patterns

For general Python best practices (type hints, error handling, context managers, dataclasses, threading, anti-patterns), refer to the `python-backend-developer` agent which owns those conventions for the whole `src/` tree.
