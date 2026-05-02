---
description: Start a new productivity tracking session with optional semicolon-separated goals.
argument-hint: "[goal1; goal2; ...]"
allowed-tools: Bash
---

# Start Productivity Session

Initialize a new session file at `~/.claude/productivity/active-session.json` and optionally record goals.

## Steps

1. **Create the data directory:**
   ```sh
   mkdir -p ~/.claude/productivity
   ```

2. **Build session JSON.** Use `date -u +"%Y-%m-%dT%H:%M:%SZ"` for `started_at` and `date +%s` for the numeric session id. Parse goals from `$ARGUMENTS` by splitting on `;` and trimming whitespace (empty string → empty goals array):
   ```json
   {
     "id": "<unix-timestamp>",
     "started_at": "<ISO 8601 datetime>",
     "goals": ["goal 1", "goal 2"],
     "tasks": [],
     "turns": 0
   }
   ```

3. **Write to** `~/.claude/productivity/active-session.json` (overwrite any existing file) using a `python3 -c` one-liner.

4. **Confirm** to the user: show start time and the goals list. If no goals, print "No goals set". Keep it to one short message.

## Notes

- Overwriting an existing session starts fresh — no warning needed.
- Goals are reminders only; they are not automatically marked complete.
- Example: `/productivity:start Build auth module; Write tests; Update docs`
