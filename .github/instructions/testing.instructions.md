---
description: "Use when writing pytest tests, test fixtures, mocks for FIX sessions, or integration tests that spin up a simulated counterparty. Covers test layout, naming conventions, and fixture patterns for the FIX engine."
applyTo: "tests/**/*.py"
---

# Testing Guidelines

- Mirror `src/` structure inside `tests/` (e.g., `tests/engine/`, `tests/messages/`)
- Name test files `test_<module>.py` and test functions `test_<behaviour>()`
- Use `pytest` fixtures for shared setup; avoid module-level state
- Mock the FIX session layer when unit-testing message parsing logic
- Mark slow integration tests with `@pytest.mark.integration` and exclude them in CI fast runs
- Assert on specific FIX tag values, not full message string equality
