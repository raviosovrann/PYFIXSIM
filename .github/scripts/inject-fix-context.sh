#!/usr/bin/env bash
# UserPromptSubmit: inject FIX session context into the agent's system message.
# Useful for surfacing active session state, last log line, or open orders.
#
# OUTPUT (stdout): JSON with a systemMessage field (optional)
#
# Example: append the last line from the FIX session log
#
# log=$(ls logs/*.log 2>/dev/null | head -1)
# if [[ -f "$log" ]]; then
#   last=$(tail -1 "$log")
#   echo "{\"systemMessage\":\"Last FIX log entry: $last\"}"
# fi
exit 0
