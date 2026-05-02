---
description: Log a completed task to the active productivity session.
argument-hint: "<task description>"
allowed-tools: Bash
---

# Log Completed Task

Append a completed task entry to the active productivity session.

## Steps

1. **Read active session:**
   ```sh
   cat ~/.claude/productivity/active-session.json 2>/dev/null
   ```
   If the file does not exist, tell the user to run `/productivity:start` first and stop.

2. **Check arguments.** If `$ARGUMENTS` is empty, ask the user what task to log and stop.

3. **Append the task** to the `tasks` array. Use `date -u +"%Y-%m-%dT%H:%M:%SZ"` as `logged_at`:
   ```json
   { "description": "<task>", "logged_at": "<ISO 8601 datetime>" }
   ```
   Use a `python3 -c` one-liner to parse and rewrite the JSON — do not require jq.

4. **Save** the updated JSON back to `~/.claude/productivity/active-session.json`.

5. **Confirm:** show the logged task and running task count (e.g., "Logged: Set up JWT middleware (3 tasks total)").

## Notes

- Do not discard existing tasks when saving.
