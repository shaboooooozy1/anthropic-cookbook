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

# Warn if trying to start jupyter/servers. Covers the subcommands, the installed
# console-script entry points (jupyter-lab, jupyter-notebook) and python -m, since
# the auth check below is a security gate rather than just a notice.
JUPYTER_RE="(^|[^[:alnum:]_.-])(jupyter([[:space:]]+|-)(notebook|lab|server)"
JUPYTER_RE+="|python[0-9.]*[[:space:]]+-m[[:space:]]+(jupyterlab|notebook|jupyter_server))"
if [[ "$COMMAND" =~ $JUPYTER_RE ]]; then
    # Block an auth-less server: this process holds the API key from .env.
    # A token/password counts only as a non-empty literal. Rejected: the empty
    # spellings ("" '' bare-= flag-with-no-value) and any shell-expanded value
    # ($VAR, "$VAR", `cmd`, $(cmd)), which cannot be shown to be non-empty here.
    AUTH_OFF_RE="--(ServerApp|NotebookApp|IdentityProvider)\\.(token|password)"
    AUTH_OFF_RE+="((=|[[:space:]]+)([\"']?[\$\`]|\"\"|''|[[:space:]]|\$)|\$)"
    if [[ "$COMMAND" =~ $AUTH_OFF_RE ]]; then
        echo "BLOCKED: do not start Jupyter with token/password auth disabled." >&2
        exit 2
    fi
    echo "ℹ️  Starting Jupyter. Make sure to select the venv kernel in notebooks."
fi

exit 0
