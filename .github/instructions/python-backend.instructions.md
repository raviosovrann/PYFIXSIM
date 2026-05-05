---
description: "Use when building or modifying FIXSIM backend Python in src/engine/, src/config/, or src/messages/. Covers session creation, configuration persistence, order sending, execution reports, event logging, and V1 backend scope."
applyTo: "src/{engine,config,messages}/**/*.py"
---

# Backend / Engine Guidelines

## Source of truth

Backend V1 scope is intentionally narrow. Prioritize only the flows needed for
the first usable FIX Client Simulator:

- create FIX sessions from saved configuration
- save and update session configurations
- open and close sessions cleanly
- send `NewOrderSingle` orders
- receive and parse `ExecutionReport` messages
- expose inbound, outbound, and system events for the UI Events Viewer

Kafka, advanced recovery flows, and non-essential protocol features are out of
scope for V1 unless the user explicitly asks for them.

## Preferred test targets

Back-end development should validate FIXSIM against test targets in this order:

1. **Our own local mock/simulated FIX acceptor**
	 - This is the primary V1 integration target.
	 - Build and maintain a lightweight local acceptor that can accept a TCP
		 connection, respond to `Logon`, `Heartbeat`, `TestRequest`, and `Logout`,
		 accept `NewOrderSingle`, and return happy-path `ExecutionReport` messages.
	 - Prefer Python + `threading` + `simplefix` so the simulator matches this
		 repository's architecture and can be used in local development and tests.
2. **A QuickFIX-based acceptor**
	 - After the local acceptor works, verify interoperability against a
		 QuickFIX-based FIX acceptor to ensure our client can talk to a widely used
		 real-world FIX engine.
	 - A local QuickFIX sample acceptor is a valid compatibility target.
3. **External venue / institutional FIX environments (optional after local
	 validation)**
	 - These are useful for later integration confidence, but they are not
		 required to complete V1.
	 - Treat Coinbase Prime, Kraken FIX, and Gemini FIX as **external venue or
		 institutional trading endpoints**, not as generic vendor sandboxes.
	 - External access usually requires onboarding, credentials, comp IDs,
		 account approval, and sometimes IP whitelisting.

Known external options discovered during research:

- **Coinbase Prime FIX**
	- FIX 4.2 order-entry connectivity is documented publicly.
	- Docs show a production FIX endpoint and sample application guidance.
	- This is a real venue/institutional integration target, not a public vendor
		sandbox.
- **Kraken FIX**
	- Kraken documents institutional FIX access, onboarding, and a sandboxed UAT
		environment for testing/certification.
	- Access requires working with Kraken support or an account manager.
- **Gemini FIX**
	- Gemini publishes FIX documentation, which makes it a plausible later venue
		option, though access model and environment details must be confirmed during
		onboarding.

Vendor simulators/demo tools are optional and separate from venue FIX sessions.
For V1, prefer our own local acceptor first and QuickFIX interoperability
second.

## File ownership

Each backend file owns one primary V1 responsibility:

| File | Component | Status |
|------|-----------|--------|
| `src/config/session_config.py` | `SessionConfig` + config load/save logic | ☑ done |
| `src/engine/session.py` | `FIXSession` — socket lifecycle, state machine, sequence numbers, logout/close | ☑ done |
| `src/engine/service.py` | `FIXEngineService` — UI-facing backend API, callbacks, event routing | ☑ done |
| `src/messages/order.py` | `NewOrderSingle` + `ExecutionReport` encode/parse support | ☐ not started |

Tests map to the owning backend areas like this:

| File | Purpose |
|------|---------|
| `tests/engine/test_session.py` | session lifecycle and state machine |
| `tests/test_engine.py` | service/config integration and happy-path backend behavior |
| `tests/messages/test_order.py` | order message validation and parsing |

## Default targeting rule

When the user asks to build "the next backend item", "continue the backend
checklist", or names a backend component without naming a file, do **not** ask
where to write code if the mapping is already present in the File ownership
table above.

Resolve the target automatically:

- `SessionConfig` → `src/config/session_config.py`
- `FIXSession` → `src/engine/session.py`
- `FIXEngineService` → `src/engine/service.py`
- `NewOrderSingle` / `ExecutionReport` → `src/messages/order.py`

Only ask the user for a target file if the ownership table is missing an entry
or the request explicitly conflicts with the default mapping.

## Build order (V1 backend first)

Work through this list top to bottom. Mark a step done only when tests pass or
the user explicitly confirms the implementation works **and** every acceptance
bullet under that step is satisfied.

If the agent cannot run the backend locally, or if the user validates the
backend behavior in their own environment first, the user's explicit
confirmation counts as approval to mark that checklist item complete. Keep the
acceptance bullets honest — do not mark an item done unless the implementation
appears to satisfy the written criteria.

- [x] 1. `SessionConfig` — configuration persistence
	- define a typed `SessionConfig` dataclass with the required V1 FIX session
		fields used by the UI session dialog
	- load configuration from `src/config/session.cfg` / `.example` using
		`configparser` or equivalent standard-library parsing
	- support saving updated configuration values back to disk
	- raise typed exceptions for missing or invalid required values
	- use `pathlib.Path`; no hardcoded host/port/credentials in engine code
- [x] 2. `FIXSession` — connection lifecycle
	- explicit `SessionState` enum and DEBUG-level state-transition logging
	- connect, logon, logout, disconnect, and close methods exist
	- shared session state (`state`, sequence numbers, socket) is protected with
		`threading.Lock`
	- graceful shutdown sends Logout before closing the TCP connection
	- implementation uses `threading` only — no `asyncio`
- [x] 3. `FIXEngineService` — application-facing backend API
	- create/open/close session methods callable from the UI controller
	- service owns backend callbacks/events; it imports no UI widgets
	- exposes state-change, inbound-message, outbound-message, and error hooks
	- stores or references the active session/config needed for V1 workflows
	- close-session path is covered for happy-path behavior
- [ ] 4. `NewOrderSingle` support — outbound order flow
	- validate required FIX order fields before encoding
	- build FIX messages with `simplefix.FixMessage.append_pair()`
	- service can send a `NewOrderSingle` through the active session
	- outbound order send path records an event/log entry for the UI viewer
	- tests cover required-field validation and message encoding basics
- [ ] 5. `ExecutionReport` handling — inbound report flow
	- parse core execution-report fields needed for V1 UI display
	- safe handling for missing/invalid fields via typed exceptions or logged
		validation failures
	- service forwards parsed execution reports to callbacks/events for the UI
	- inbound execution-report path records an event/log entry
	- tests cover at least one valid parse and one invalid input case
- [ ] 6. Event capture / message log feed — backend → Events Viewer data
	- create a simple event record shape containing timestamp, direction,
		session identity, and raw/system message text
	- emit or return events for connect, logon, logout, disconnect, send, receive,
		and backend error conditions
	- log/message capture is sufficient for the UI Events Viewer happy path
	- event generation is decoupled from widget code

- [ ] 7. Local FIX acceptor — primary integration target
	- implement a lightweight local simulated FIX acceptor for development and
		happy-path integration testing
	- accept a TCP connection and handle `Logon`, `Heartbeat`, `TestRequest`,
		`Logout`, and `NewOrderSingle`
	- return at least one happy-path `ExecutionReport` response for accepted
		orders
	- keep the implementation aligned with project conventions: Python,
		`threading`, `simplefix`, typed code, and no UI coupling
	- provide a simple way to run it locally for manual verification or tests
- [ ] 8. QuickFIX acceptor compatibility
	- verify that our FIX session can connect and complete logon/logout against a
		QuickFIX-based acceptor
	- confirm basic administrative message interoperability: heartbeat,
		test-request handling, and graceful disconnect
	- if practical, confirm at least one order-entry happy path or equivalent
		message exchange against the QuickFIX acceptor
	- capture any QuickFIX-specific interoperability notes that affect session
		configuration or message handling
- [ ] 9. V1 backend test pass
	- tests cover config load/save, session lifecycle, close/logout, order send,
		and execution-report parsing
	- backend tests use mocks/fakes rather than flaky live-network dependencies
	- perform a manual or automated happy-path smoke test against our own local
		simulated FIX acceptor once the main session and order flow are implemented
	- if practical, run a compatibility smoke test against a QuickFIX-based
		acceptor after the local acceptor path works
	- `tests/` updates accompany behavior changes
	- failing or missing tests block checklist completion

## Protocol and concurrency rules

- Use Python `threading` consistently — do **not** use `asyncio` in this project
- Keep session state transitions explicit and logged at DEBUG level
- All public engine methods must have type hints and raise typed exceptions
- Configuration values must be loaded from `src/config/`; no hardcoded
	host/port/credentials
- Implement graceful shutdown: send Logout before closing the TCP connection
- Build outbound FIX messages with `simplefix.FixMessage.append_pair()`
- Sequence numbers and session state must be protected with `threading.Lock`
- Use `logging.getLogger(__name__)` — never `print()` in backend code
- Use `pathlib.Path` and context managers for file/socket operations
- When editing `src/messages/**/*.py`, also follow
	`.github/instructions/fix-protocol.instructions.md`
