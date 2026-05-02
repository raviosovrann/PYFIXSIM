#!/usr/bin/env bash
# PostToolUse: run flake8 on any Python files modified by the last tool call.
# Read the tool output JSON from stdin; extract edited file path and lint it.
#
# Requires: flake8 installed in the active Python environment.
#
# Uncomment and extend the logic below:
#
# input=$(cat)
# file=$(echo "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('output',{}).get('filePath',''))" 2>/dev/null)
# if [[ "$file" == *.py ]] && [[ -f "$file" ]]; then
#   flake8 --max-line-length=99 "$file"
# fi
exit 0
