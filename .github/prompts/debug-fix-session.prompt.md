---
description: "Investigate and debug a FIX session issue — connection drop, message rejection, sequence number mismatch, or unexpected logon/logout."
---

Debug the following FIX session issue: `$issueDescription`

1. Check the session log files in `logs/` for the relevant session
2. Identify the last successfully exchanged message and sequence numbers
3. Look for Reject (35=3), Logout (35=5), or ResendRequest (35=2) messages
4. Trace the issue to `src/engine/` session logic or `src/messages/` parsing
5. Propose and implement a fix with a corresponding test in `tests/`
