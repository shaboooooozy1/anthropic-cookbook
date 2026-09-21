#!/bin/bash
# PreToolUse Hook - Bash Safety Check
# Prevents dangerous commands and provides helpful reminders

set -e

# Claude Code passes the hook payload as JSON on stdin, not as argv
INPUT=$(cat)
TOOL_NAME=$(printf '%s' "$INPUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_name",""))')
COMMAND=$(printf '%s' "$INPUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))')

# Only run for Bash tool
if [[ "$TOOL_NAME" != "Bash" ]]; then
    exit 0
fi

# Check for potentially dangerous commands
if [[ "$COMMAND" == *"rm -rf outputs"* ]] || [[ "$COMMAND" == *"rm -rf sample_data"* ]]; then
    echo "⚠️  WARNING: Attempting to delete important directory!"
    echo "Command: $COMMAND"
    echo "These directories contain generated files and sample data."
    # Allow but warn
fi

# Warn about pip install without using requirements.txt
if [[ "$COMMAND" == *"pip install"* ]] && [[ "$COMMAND" != *"requirements.txt"* ]]; then
    echo "ℹ️  Installing package directly. Consider updating requirements.txt"
fi

# Remind about kernel restart after SDK reinstall
if [[ "$COMMAND" == *"pip install"* ]] && [[ "$COMMAND" == *"anthropic"* ]]; then
    echo "ℹ️  Remember: Restart Jupyter kernel after SDK installation!"
fi

# Warn if trying to start jupyter/servers
if [[ "$COMMAND" == *"jupyter notebook"* ]] || [[ "$COMMAND" == *"jupyter lab"* ]]; then
    # Block an auth-less server: this process holds the API key from .env.
    # Matches --ServerApp/--NotebookApp/--IdentityProvider .token/.password set to
    # an empty value in any spelling: =""  =''  = (bare)  or space-separated "" / ''.
    AUTH_OFF_RE="--(ServerApp|NotebookApp|IdentityProvider)\\.(token|password)"
    AUTH_OFF_RE+="(=(\"\"|''|)([[:space:]]|\$)|[[:space:]]+(\"\"|'')([[:space:]]|\$))"
    if [[ "$COMMAND" =~ $AUTH_OFF_RE ]]; then
        echo "BLOCKED: do not start Jupyter with token/password auth disabled." >&2
        exit 2
    fi
    echo "ℹ️  Starting Jupyter. Make sure to select the venv kernel in notebooks."
fi

exit 0
