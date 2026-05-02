#!/usr/bin/env bash
# Increment turn counter in the active productivity session on each Claude stop.
SESSION_FILE="$HOME/.claude/productivity/active-session.json"

[ -f "$SESSION_FILE" ] || exit 0

python3 - "$SESSION_FILE" <<'EOF'
import json, sys

path = sys.argv[1]
try:
    with open(path) as f:
        data = json.load(f)
except (json.JSONDecodeError, OSError):
    sys.exit(0)

data["turns"] = data.get("turns", 0) + 1

with open(path, "w") as f:
    json.dump(data, f, indent=2)
EOF
