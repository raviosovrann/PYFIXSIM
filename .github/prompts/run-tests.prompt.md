---
description: "Run the project test suite and summarise failures."
---

1. Run `python -m pytest tests/ -v` and capture output
2. List any failing tests with their error messages
3. For each failure, identify the root cause in `src/`
4. Suggest or implement a fix, then re-run the affected tests to confirm they pass
