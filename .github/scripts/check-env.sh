#!/usr/bin/env bash
# SessionStart: verify the Python environment has the required packages.
# Prints a warning systemMessage if dependencies are missing.
#
# Uncomment and extend the logic below:
#
# missing=()
# for pkg in simplefix PySide6 pytest; do
#   python3 -c "import $pkg" 2>/dev/null || missing+=("$pkg")
# done
# if [[ ${#missing[@]} -gt 0 ]]; then
#   echo "{\"systemMessage\":\"WARNING: missing Python packages: ${missing[*]}. Run pip install -r requirements.txt\"}"
# fi
exit 0
