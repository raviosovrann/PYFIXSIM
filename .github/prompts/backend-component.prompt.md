---
description: "Build or extend a FIXSIM backend component for V1 session creation, configuration persistence, order sending, execution reports, or event logging."
agent: "python-backend-developer"
argument-hint: "Build SessionConfig, FIXSession, FIXEngineService, NewOrderSingle, ExecutionReport, or the next unchecked backend item"
---

# Build Backend Component — FIXSIM

## Before you write a single line

1. Read `.github/instructions/python-backend.instructions.md` — it is the
	source of truth for backend V1 scope, file ownership, and checklist order.
2. Find the **first unchecked item** in the backend Build Order list unless the
	user has specified a different backend component.
3. Read the target backend file and its most relevant test file before editing.
4. If the task touches FIX application messages, also follow
	`.github/instructions/fix-protocol.instructions.md`.

## Current task

Implement or extend: **${componentName}**

Target file: **${targetFile}**

Related test file: **${testFile}**

If `${componentName}` is not specified, pick the first unchecked step from the
build order in `python-backend.instructions.md`, infer the owning file from the
File ownership table there, and begin there without asking the user for the
file path unless the ownership mapping is missing or ambiguous.

## How to implement

1. Keep backend logic decoupled from UI widgets and Qt imports.
2. Use `threading` only — never introduce `asyncio`.
3. Use typed dataclasses, enums, and typed exceptions where appropriate.
4. Build FIX messages with `simplefix.FixMessage.append_pair()` — never by hand.
5. Protect shared session state with `threading.Lock`.
6. Record or emit enough event information for the UI Events Viewer happy path.
7. Add or update tests in `tests/` alongside every behavior change.
8. Prefer the smallest testable change that moves the backend checklist forward.

## Done checklist

Before marking the build-order item as complete:

- [ ] Every acceptance bullet under the current numbered step in
	`python-backend.instructions.md` is satisfied
- [ ] All public methods and `__init__` signatures have full type hints
- [ ] No `asyncio` introduced; concurrency uses `threading` only
- [ ] No hardcoded host/port/credentials in backend code
- [ ] FIX messages are encoded/parsing logic is implemented with `simplefix`
- [ ] Corresponding tests were added or updated in `tests/`
- [ ] Backend code remains decoupled from UI widgets
- [ ] Errors are typed or clearly logged; no bare `except`
- [ ] Build-order checkbox in `python-backend.instructions.md` is marked `[x]`

If the agent cannot run the backend locally, it may ask the human user to
verify the implementation. Once the user explicitly confirms that it works,
that approval counts as permission to mark the checklist item complete,
provided the written acceptance bullets also appear satisfied.
