# Tool Fallback Logic

Decision tree for MCP errors. Apply in order. Never retry silently on auth failures.

## Microsoft 365 MCP Errors

### `401 Unauthorized` or `invalid_grant`

OAuth token expired or revoked.

1. **Stop the active workflow.** Do not partial-complete.
2. Inform the user in one sentence: *"Microsoft 365 connector needs reauthentication."*
3. Direct them: *"Settings > Connectors > Microsoft 365 > Reconnect."*
4. Do not fall back to Superhuman Mail automatically — the two mailboxes may have different content windows. Ask the user whether to proceed against Superhuman for this session only.
5. Once the user confirms reauth, resume the workflow from the interrupted step.

### `429 Too Many Requests`

Rate limited.

1. Pause for 30 seconds on first occurrence.
2. Retry the exact same call once.
3. On a second `429`, stop and report to the user. Suggest narrowing the window (e.g., 24h instead of 72h) or reducing result size.

### `5xx Server Error`

Upstream Graph API issue.

1. Retry once after 10 seconds.
2. On second failure, fall back to Superhuman Mail MCP for the current workflow step only. Flag the fallback in the output.

## Superhuman Mail MCP Errors

### Auth failure

Same playbook as M365 `401`: stop, inform, direct to reconnect. Do not silently cross to M365 either — if the user explicitly invoked Superhuman, respect that.

### Tool not found

Usually a fully-qualified name issue. Verify the prefix `superhuman-mail:` is present. If present and still not found, the server may be disconnected; surface to user.

## HubSpot MCP Errors

HubSpot is an optional cross-reference. On any error:

1. Skip the HubSpot cross-check.
2. Proceed with inbox-only data.
3. Note in output: *"HubSpot cross-reference unavailable this session."*

## Tool Selection Principles

- **Always use fully-qualified tool names.** `microsoft-365:outlook_email_search`, not `outlook_email_search`.
- **Do not cross mailboxes silently.** If the user asked for M365 and M365 fails, ask before pivoting to Superhuman.
- **State-mutating tools require explicit user consent per item.** `trash_thread`, `mark_spam`, `unsubscribe`, `send_draft` never run on Claude's initiative.

## Escalation

If two consecutive sessions hit the same fallback path, flag in the Weekly Digest so the user can investigate connector health rather than working around it.
