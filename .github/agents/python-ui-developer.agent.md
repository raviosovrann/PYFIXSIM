---
description: "Use when building or modifying UI components, views, dialogs, or layouts in src/ui/ using PySide6. Handles UI event bindings, widget styling, and keeping UI logic decoupled from FIX engine logic."
tools: ["Read", "Grep", "Glob", "Bash"]
model: Claude Sonnet 4.6
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

## Python Development Patterns

Idiomatic Python patterns and best practices for building robust, efficient, and maintainable applications.

## Core Principles

### 1. Readability Counts

Python prioritizes readability. Code should be obvious and easy to understand.

```python
# Good: Clear and readable
def get_active_users(users: list[User]) -> list[User]:
    """Return only active users from the provided list."""
    return [user for user in users if user.is_active]


# Bad: Clever but confusing
def get_active_users(u):
    return [x for x in u if x.a]
```

### 2. Explicit is Better Than Implicit

Avoid magic; be clear about what your code does.

```python
# Good: Explicit configuration
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Bad: Hidden side effects
import some_module
some_module.setup()  # What does this do?
```

### 3. EAFP - Easier to Ask Forgiveness Than Permission

Python prefers exception handling over checking conditions.

```python
# Good: EAFP style
def get_value(dictionary: dict, key: str) -> Any:
    try:
        return dictionary[key]
    except KeyError:
        return default_value

# Bad: LBYL (Look Before You Leap) style
def get_value(dictionary: dict, key: str) -> Any:
    if key in dictionary:
        return dictionary[key]
    else:
        return default_value
```

## Type Hints

### Basic Type Annotations

```python
from typing import Optional, List, Dict, Any

def process_user(
    user_id: str,
    data: Dict[str, Any],
    active: bool = True
) -> Optional[User]:
    """Process a user and return the updated User or None."""
    if not active:
        return None
    return User(user_id, data)
```

### Modern Type Hints (Python 3.9+)

```python
# Python 3.9+ - Use built-in types
def process_items(items: list[str]) -> dict[str, int]:
    return {item: len(item) for item in items}

# Python 3.8 and earlier - Use typing module
from typing import List, Dict

def process_items(items: List[str]) -> Dict[str, int]:
    return {item: len(item) for item in items}
```

### Type Aliases and TypeVar

```python
from typing import TypeVar, Union

# Type alias for complex types
JSON = Union[dict[str, Any], list[Any], str, int, float, bool, None]

def parse_json(data: str) -> JSON:
    return json.loads(data)

# Generic types
T = TypeVar('T')

def first(items: list[T]) -> T | None:
    """Return the first item or None if list is empty."""
    return items[0] if items else None
```

### Protocol-Based Duck Typing

```python
from typing import Protocol

class Renderable(Protocol):
    def render(self) -> str:
        """Render the object to a string."""

def render_all(items: list[Renderable]) -> str:
    """Render all items that implement the Renderable protocol."""
    return "\n".join(item.render() for item in items)
```

## Error Handling Patterns

### Specific Exception Handling

```python
# Good: Catch specific exceptions
def load_config(path: str) -> Config:
    try:
        with open(path) as f:
            return Config.from_json(f.read())
    except FileNotFoundError as e:
        raise ConfigError(f"Config file not found: {path}") from e
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in config: {path}") from e

# Bad: Bare except
def load_config(path: str) -> Config:
    try:
        with open(path) as f:
            return Config.from_json(f.read())
    except:
        return None  # Silent failure!
```

### Exception Chaining

```python
def process_data(data: str) -> Result:
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as e:
        # Chain exceptions to preserve the traceback
        raise ValueError(f"Failed to parse data: {data}") from e
```

### Custom Exception Hierarchy

```python
class AppError(Exception):
    """Base exception for all application errors."""
    pass

class ValidationError(AppError):
    """Raised when input validation fails."""
    pass

class NotFoundError(AppError):
    """Raised when a requested resource is not found."""
    pass

# Usage
def get_user(user_id: str) -> User:
    user = db.find_user(user_id)
    if not user:
        raise NotFoundError(f"User not found: {user_id}")
    return user
```

## Context Managers

### Resource Management

```python
# Good: Using context managers
def process_file(path: str) -> str:
    with open(path, 'r') as f:
        return f.read()

# Bad: Manual resource management
def process_file(path: str) -> str:
    f = open(path, 'r')
    try:
        return f.read()
    finally:
        f.close()
```

### Custom Context Managers

```python
from contextlib import contextmanager

@contextmanager
def timer(name: str):
    """Context manager to time a block of code."""
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    print(f"{name} took {elapsed:.4f} seconds")

# Usage
with timer("data processing"):
    process_large_dataset()
```

### Context Manager Classes

```python
class DatabaseTransaction:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        self.connection.begin_transaction()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        return False  # Don't suppress exceptions

# Usage
with DatabaseTransaction(conn):
    user = conn.create_user(user_data)
    conn.create_profile(user.id, profile_data)
```

## Comprehensions and Generators

### List Comprehensions

```python
# Good: List comprehension for simple transformations
names = [user.name for user in users if user.is_active]

# Bad: Manual loop
names = []
for user in users:
    if user.is_active:
        names.append(user.name)

# Complex comprehensions should be expanded
# Bad: Too complex
result = [x * 2 for x in items if x > 0 if x % 2 == 0]

# Good: Use a generator function
def filter_and_transform(items: Iterable[int]) -> list[int]:
    result = []
    for x in items:
        if x > 0 and x % 2 == 0:
            result.append(x * 2)
    return result
```

### Generator Expressions

```python
# Good: Generator for lazy evaluation
total = sum(x * x for x in range(1_000_000))

# Bad: Creates large intermediate list
total = sum([x * x for x in range(1_000_000)])
```

### Generator Functions

```python
def read_large_file(path: str) -> Iterator[str]:
    """Read a large file line by line."""
    with open(path) as f:
        for line in f:
            yield line.strip()

# Usage
for line in read_large_file("huge.txt"):
    process(line)
```

## Data Classes and Named Tuples

### Data Classes

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class User:
    """User entity with automatic __init__, __repr__, and __eq__."""
    id: str
    name: str
    email: str
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True

# Usage
user = User(
    id="123",
    name="Alice",
    email="alice@example.com"
)
```

### Data Classes with Validation

```python
@dataclass
class User:
    email: str
    age: int

    def __post_init__(self):
        # Validate email format
        if "@" not in self.email:
            raise ValueError(f"Invalid email: {self.email}")
        # Validate age range
        if self.age < 0 or self.age > 150:
            raise ValueError(f"Invalid age: {self.age}")
```

### Named Tuples

```python
from typing import NamedTuple

class Point(NamedTuple):
    """Immutable 2D point."""
    x: float
    y: float

    def distance(self, other: 'Point') -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5

# Usage
p1 = Point(0, 0)
p2 = Point(3, 4)
print(p1.distance(p2))  # 5.0
```

## Decorators

### Function Decorators

```python
import functools
import time

def timer(func: Callable) -> Callable:
    """Decorator to time function execution."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} took {elapsed:.4f}s")
        return result
    return wrapper

@timer
def slow_function():
    time.sleep(1)

# slow_function() prints: slow_function took 1.0012s
```

### Parameterized Decorators

```python
def repeat(times: int):
    """Decorator to repeat a function multiple times."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            results = []
            for _ in range(times):
                results.append(func(*args, **kwargs))
            return results
        return wrapper
    return decorator

@repeat(times=3)
def greet(name: str) -> str:
    return f"Hello, {name}!"

# greet("Alice") returns ["Hello, Alice!", "Hello, Alice!", "Hello, Alice!"]
```

### Class-Based Decorators

```python
class CountCalls:
    """Decorator that counts how many times a function is called."""
    def __init__(self, func: Callable):
        functools.update_wrapper(self, func)
        self.func = func
        self.count = 0

    def __call__(self, *args, **kwargs):
        self.count += 1
        print(f"{self.func.__name__} has been called {self.count} times")
        return self.func(*args, **kwargs)

@CountCalls
def process():
    pass

# Each call to process() prints the call count
```

## Concurrency Patterns

### Threading for I/O-Bound Tasks

```python
import concurrent.futures
import threading

def fetch_url(url: str) -> str:
    """Fetch a URL (I/O-bound operation)."""
    import urllib.request
    with urllib.request.urlopen(url) as response:
        return response.read().decode()

def fetch_all_urls(urls: list[str]) -> dict[str, str]:
    """Fetch multiple URLs concurrently using threads."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(fetch_url, url): url for url in urls}
        results = {}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                results[url] = future.result()
            except Exception as e:
                results[url] = f"Error: {e}"
    return results
```

### Multiprocessing for CPU-Bound Tasks

```python
def process_data(data: list[int]) -> int:
    """CPU-intensive computation."""
    return sum(x ** 2 for x in data)

def process_all(datasets: list[list[int]]) -> list[int]:
    """Process multiple datasets using multiple processes."""
    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = list(executor.map(process_data, datasets))
    return results
```

## Package Organization

### Standard Project Layout

```
FIXSIM/
├── src/
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py
│   │   ├── controller.py
│   │   ├── session_widget.py
│   │   ├── order_panel.py
│   │   └── message_log.py
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── service.py
│   │   └── session.py
│   ├── messages/
│   │   ├── __init__.py
│   │   └── order.py
│   └── config/
│       ├── __init__.py
│       └── session_config.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_engine.py
│   └── test_messages.py
├── requirements.txt
├── README.md
└── .gitignore
```

### Import Conventions

```python
# Good: Import order - stdlib, third-party, local
import sys
import threading
from pathlib import Path

import simplefix
from PySide6.QtWidgets import QApplication

from src.engine.service import FIXEngineService
from src.ui.main_window import MainWindow

# Good: Use isort for automatic import sorting
# pip install isort
```

### __init__.py for Package Exports

```python
# src/ui/__init__.py
"""FIXSIM UI package."""

__version__ = "1.0.0"

from src.ui.main_window import MainWindow
from src.ui.controller import AppController

__all__ = ["MainWindow", "AppController"]
```

## Memory and Performance

### Using __slots__ for Memory Efficiency

```python
# Bad: Regular class uses __dict__ (more memory)
class Point:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

# Good: __slots__ reduces memory usage
class Point:
    __slots__ = ['x', 'y']

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
```

### Generator for Large Data

```python
# Bad: Returns full list in memory
def read_lines(path: str) -> list[str]:
    with open(path) as f:
        return [line.strip() for line in f]

# Good: Yields lines one at a time
def read_lines(path: str) -> Iterator[str]:
    with open(path) as f:
        for line in f:
            yield line.strip()
```

### Avoid String Concatenation in Loops

```python
# Bad: O(n²) due to string immutability
result = ""
for item in items:
    result += str(item)

# Good: O(n) using join
result = "".join(str(item) for item in items)

# Good: Using StringIO for building
from io import StringIO

buffer = StringIO()
for item in items:
    buffer.write(str(item))
result = buffer.getvalue()
```

## Python Tooling Integration

### Essential Commands

```bash
# Code formatting
black .
isort .

# Linting
ruff check .
pylint src/

# Type checking
mypy src/

# Testing
pytest --cov=src --cov-report=html

# Security scanning
bandit -r src/

# Dependency management
pip-audit
safety check
```

### pyproject.toml Configuration

```toml
[project]
name = "fixsim"
version = "1.0.0"
requires-python = ">=3.10"
dependencies = [
    "PySide6>=6.6.0",
    "simplefix>=1.0.17",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.5.0",
]

[tool.black]
line-length = 88
target-version = ['py310']

[tool.ruff]
line-length = 88
select = ["E", "F", "I", "N", "W"]

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=src --cov-report=term-missing"
```

## Quick Reference: Python Idioms

| Idiom | Description |
|-------|-------------|
| EAFP | Easier to Ask Forgiveness than Permission |
| Context managers | Use `with` for resource management |
| List comprehensions | For simple transformations |
| Generators | For lazy evaluation and large datasets |
| Type hints | Annotate function signatures |
| Dataclasses | For data containers with auto-generated methods |
| `__slots__` | For memory optimization |
| f-strings | For string formatting (Python 3.6+) |
| `pathlib.Path` | For path operations (Python 3.4+) |
| `enumerate` | For index-element pairs in loops |

## Python Anti-Patterns to Avoid

```python
# Bad: Mutable default arguments
def append_to(item, items=[]):
    items.append(item)
    return items

# Good: Use None and create new list
def append_to(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items

# Bad: Checking type with type()
if type(obj) == list:
    process(obj)

# Good: Use isinstance
if isinstance(obj, list):
    process(obj)

# Bad: Comparing to None with ==
if value == None:
    process()

# Good: Use is
if value is None:
    process()

# Bad: from module import *
from os.path import *

# Good: Explicit imports
from os.path import join, exists

# Bad: Bare except
try:
    risky_operation()
except:
    pass

# Good: Specific exception
try:
    risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
```

**Remember**: Python code should be readable, explicit, and follow the principle of least surprise. When in doubt, prioritize clarity over cleverness.
