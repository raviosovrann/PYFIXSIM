# FIXSIM — FIX Client Simulator

## Project Overview
Desktop application that simulates a FIX (Financial Information eXchange) protocol client. Python for both UI and backend.

## Stack
- **UI**: PySide6 — widgets, signals/slots, QThread for background tasks
- **Backend**: Python — FIX engine, session management, message parsing
- **FIX Library**: simplefix 1.0.17 — pure-Python FIX codec
- **Concurrency**: `threading` only — do **not** use `asyncio`, never mix the two
- **Testing**: pytest + pytest-cov
- **Static analysis**: ruff, mypy, black, bandit, isort

## Architecture

```
FIXSIM/
├── src/
│   ├── ui/          — PySide6 widgets, views, dialogs (MainWindow, controller, panels)
│   ├── engine/      — FIX session state machine, connectivity, timers, message queuing
│   ├── messages/    — FIX message classes (NewOrderSingle, ExecutionReport, …)
│   └── config/      — SessionConfig dataclass, .cfg loader (session.cfg gitignored)
├── tests/
│   ├── engine/      — unit tests for session, connectivity, sequence numbers
│   └── messages/    — unit tests for message constructors and parsers
├── docs/            — FIX42.xml, FIX44.xml protocol dictionaries
└── logs/            — runtime session logs (gitignored)
```

## Build & Test
```bash
# Install all dependencies
pip install -r requirements.txt

# Run tests with coverage
python -m pytest tests/

# Static analysis
ruff check src/ tests/
mypy src/
black --check src/ tests/
bandit -r src/

# Run the application
python src/main.py
```

## Key Conventions

### Architecture
- **UI never calls the FIX engine directly.** UI slots emit signals; `AppController` in `src/ui/controller.py` wires them to `FIXEngineService`.
- **Engine knows nothing about widgets.** Cross-thread updates use Qt queued signal/slot connections via an `EngineAdapter(QObject)`.
- Config is loaded from `src/config/session.cfg` (gitignored). Commit `session.cfg.example` with placeholder values.

### Python
- Follow PEP 8; max line length 99 chars
- Full type hints on all public functions and methods — no bare `Any`
- Use `threading.Lock` to protect all shared session state (`in_seq_num`, `out_seq_num`, `state`)
- Background threads must be `daemon=True` so they don't block shutdown
- Use `with` for all socket and file operations — never manual open/close
- Use `logging.getLogger(__name__)` — never `print()` in engine code
- Use `pathlib.Path` for all file path operations

### FIX Protocol
- FIX 4.2 is the default session version; FIX 4.4 also supported
- Use standard FIX tag names as variable names: `ClOrdID`, `Symbol`, `HeartBtInt`, `MsgSeqNum`
- Build messages with `simplefix.FixMessage.append_pair()` — never construct raw FIX strings by hand
- Validate required fields before encoding; raise `MessageValidationError(tag, reason)` on failure
- Sequence numbers must be persisted to disk — in-memory only risks gap-fill failure after crash
- Session-level messages (35=0,1,2,4,5,A) must never go through the application message queue

## Agents
Specialist agents are defined in `.github/agents/`:
- `python-backend-developer` — FIX engine, session, messages, config
- `python-ui-developer` — PySide6 widgets, layouts, signal/slot patterns
- `fix-protocol-expert` — FIX message construction, tag validation, spec reference
- `tester` — pytest fixtures, mocks, integration tests
- `python-reviewer` — PEP 8, type hints, security, FIX correctness review

See `docs/` for FIX protocol XML dictionaries.
