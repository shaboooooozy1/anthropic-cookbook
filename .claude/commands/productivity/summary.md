---
description: Show a summary of the current productivity session including elapsed time, goals, and completed tasks.
allowed-tools: Bash
---

# Productivity Session Summary

Read the active session and display a formatted summary.

## Steps

1. **Read session:**
   ```sh
   cat ~/.claude/productivity/active-session.json 2>/dev/null
   ```
   If not found, tell the user there is no active session and stop.

2. **Calculate elapsed time** from `started_at` to now. Express as `Xh Ym` if ≥60 min, `Xm` if ≥1 min but <60 min, `Xs` if <1 min. Always truncate (do not round) partial units.

3. **Print summary** inside a fenced code block to preserve alignment:
   ```
   Session Summary
   ─────────────────────────────────
   Started:   2025-04-30 14:23 UTC
   Elapsed:   1h 12m
   Turns:     8

   Goals (2):
     · Build auth module
     · Write tests

   Completed Tasks (3):
     14:31  Set up JWT middleware
     14:45  Add login endpoint
     15:02  Write unit tests
   ```

4. **Omit empty sections:** skip Goals if none were set; skip Tasks if none logged; omit Turns line if `turns` is 0 (i.e., no Stop events have fired yet).

## Notes

- All goals use `·` — they are reminders, not auto-completed.
- Sort tasks by `logged_at` ascending.
- Show task timestamps in the local timezone using `date`.
