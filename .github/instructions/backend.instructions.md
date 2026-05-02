---
description: "Use when working on FIX engine internals, session management, connectivity logic, or configuration parsing in src/engine/ or src/config/. Covers session lifecycle, heartbeat timers, reconnect strategy, and quickfix initiator/acceptor setup."
applyTo: "src/engine/**/*.py"
---

# Backend / Engine Guidelines

- Keep session state transitions explicit and logged at DEBUG level
- Use Python `threading` or `asyncio` consistently — do not mix both models
- All public engine methods must have type hints and raise typed exceptions
- Configuration values must be loaded from `src/config/`; no hardcoded host/port/credentials
- Implement graceful shutdown: send Logout before closing the TCP connection
