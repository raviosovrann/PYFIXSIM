#!/usr/bin/env bash
# PreToolUse: block dangerous shell commands before the agent runs them.
# Read the tool input JSON from stdin. Exit 2 to block, 0 to allow.
#
# Example: deny `rm -rf`, `git push --force`, `git reset --hard`
#
# INPUT (stdin): JSON with tool name and input fields
# OUTPUT (stdout): JSON with permissionDecision
#
# Uncomment and extend the logic below:
#
# input=$(cat)
# command=$(echo "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('input',{}).get('command',''))")
# if echo "$command" | grep -qE 'rm\s+-rf|--force|reset\s+--hard'; then
#   echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Dangerous command blocked by hook"}}'
#   exit 2
# fi
exit 0
