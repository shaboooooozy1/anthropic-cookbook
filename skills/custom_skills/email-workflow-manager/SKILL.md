---
name: email-workflow-manager
description: Triages Microsoft 365 / Outlook inbox for a commercial P&C insurance broker. Categorizes unread mail into HIGH / MEDIUM / LOW / NOISE tiers, extracts active pipeline items with stage and next-action, flags emails needing response with draft points, and produces daily triage reports or weekly pipeline roll-ups with sent-items audits. Use whenever the user mentions email, inbox, Outlook, M365, Microsoft 365, unread, triage, follow-up, or pipeline from inbox. Use when the user says "triage my inbox," "what's in my email," "what do I need to respond to," "summarize my unread," "pull pipeline items," "weekly inbox review," "give me a triage report," "what needs follow-up," or asks to audit sent mail. Prefer M365 MCP tools (outlook_email_search, outlook_calendar_search) unless the user specifies Superhuman Mail. Excludes self-forwarding addresses from sent-item analysis. Delegates reply drafting to the churchill-hemingway-engine skill.
license: MIT
metadata:
  author: Will Bloomstine
  version: 1.0.0
  owner: wbloomstine@hubinternational.com
  role: ARM Client Executive, HUB International (Erie, PA)
  mcp-servers: microsoft-365, superhuman-mail, hubspot, google-calendar
  composes-with: churchill-hemingway-engine
  phase: 1
  priority: high
  migrated-from: email-workflow-manager-gmail-v0
---

# Email Workflow Manager

Clarity. Strategy. Action.

## Overview

Operating documentation for inbox command. Built for a commercial P&C broker who runs on volume, speed, and signal-to-noise discipline. This skill converts the Outlook inbox into a ranked, actionable work queue. It categorizes mail by tier, extracts pipeline state, flags what must be answered today, and hands drafting off to the Churchill-Hemingway engine.

One operator. One book of business. No wasted reads.

## When to Trigger

Trigger automatically when the user's message contains any of the following, alone or in combination:

- "triage my inbox" / "triage the inbox" / "run triage"
- "what's in my email" / "what's in my inbox"
- "what do I need to respond to" / "what needs a reply"
- "summarize my unread" / "unread summary"
- "pull pipeline items from my inbox" / "pipeline from email"
- "give me a triage report" / "triage report"
- "what needs follow-up" / "flag follow-ups"
- "weekly inbox review" / "weekly digest" / "roll up the week"
- "sent items audit" / "audit my sent mail"
- any bare mention of: email, inbox, Outlook, M365, unread, triage, follow-up, pipeline items, mail queue

Do NOT trigger on: calendar-only requests with no email component, document drafting with no inbox reference, research requests, HubSpot contact lookups with no mail context.

## Inbox Source Selection

Two MCP connectors provide mailbox access. Choose deliberately.

| Condition | Use |
|---|---|
| Default for all triage, pipeline extraction, and sent audits | **Microsoft 365 MCP** |
| User explicitly says "Superhuman" | **Superhuman Mail MCP** |
| Need label/split semantics (labels, splits, unsubscribe actions) | **Superhuman Mail MCP** |
| M365 returns auth error | Halt the workflow, surface reauth instructions, and ask the user before any mailbox pivot (see `references/tool-fallback-logic.md`). Never cross mailboxes silently. |

Always use fully-qualified tool names. Prefix every MCP call with the server name.

## Core Workflows

### Workflow 1 — Daily Triage Session

Target: 50+ emails per session, categorized output, under 10 minutes of user time.

Copy this checklist and track progress:

```
Daily Triage Progress:
- [ ] Step 1: Pull unread window (last 24-72h)
- [ ] Step 2: Classify each message into tier
- [ ] Step 3: Extract pipeline signals
- [ ] Step 4: Flag follow-ups needed today
- [ ] Step 5: Emit Triage Report
```

**Step 1 — Pull unread window.** Call `microsoft-365:outlook_email_search` with `isRead=false` and `receivedDateTime >= now-24h` by default. Widen the filter to `now-72h` only on Mondays or when the user says "catch up" / "widen the window."

**Step 2 — Classify each message.** For each message, apply the tier rules in `references/triage-tier-definitions.md`. Every message resolves to exactly one of: HIGH, MEDIUM, LOW, NOISE. Use `references/hub-internal-senders.md` to recognize internal HUB traffic.

**Step 3 — Extract pipeline signals.** For any message referencing a prospect, carrier, renewal, quote, or bind, pass to the Pipeline Item Extraction workflow (Workflow 2). Cross-reference with HubSpot when ambiguous using `hubspot:search_contacts`.

**Step 4 — Flag follow-ups.** Apply the Follow-Up Flagging workflow (Workflow 3) to every HIGH and MEDIUM item.

**Step 5 — Emit Triage Report.** Use the Triage Report template from `references/output-templates.md`.

### Workflow 2 — Pipeline Item Extraction

Produce one row per active pipeline item. Fields, in order:

1. **Item name / subject** — short, concrete
2. **Contact / prospect name** — person + company
3. **Stage** — one of: prospecting, active pursuit, proposal, closing, stalled (see `references/pipeline-stage-taxonomy.md`)
4. **Last touchpoint date** — date of most recent email in either direction
5. **Recommended next action** — one verb, one object
6. **Urgency** — HIGH / MEDIUM / LOW

Pull thread context from the active mailbox only. When M365 is the active source, use `microsoft-365:outlook_email_search` by subject + sender and, if needed, a follow-up search narrowed by `conversationId`. When Superhuman is the active source, use `superhuman-mail:get_thread` by thread ID. Do not cross providers mid-workflow — a cross-provider pull can return a divergent thread history and corrupt the last-touch date. If the active provider genuinely lacks the thread, ask the user before pivoting. Cross-check against HubSpot with `hubspot:search_contacts` only when the contact is not obvious from the header.

### Workflow 3 — Follow-Up Flagging

For every HIGH and MEDIUM item, produce:

- **Suggested response timing** — `today`, `24h`, `48h`, `end of week`
- **Draft response points** — three bullets maximum, no prose
- **Priority** — HIGH / MEDIUM

When the user asks for an actual drafted reply (not just points), **invoke the `churchill-hemingway-engine` skill** with the draft points as input. Do not draft prose directly in this skill.

### Workflow 4 — Weekly Inbox Review

Run on Friday afternoons or on demand.

1. Widen window to 7 days; include read + unread.
2. Run Workflow 1 across the full window.
3. Roll up pipeline items by stage — count, movement, stalls.
4. Identify stalled threads (no response >5 business days).
5. Run Workflow 5 (Sent-Items Audit).
6. Emit Weekly Digest per `references/output-templates.md`.

### Workflow 5 — Sent-Items Audit

Purpose: surface unanswered outbound, measure response discipline, and catch pipeline items the outbound side is tracking that the inbound side missed.

1. Call `microsoft-365:outlook_email_search` filtered to `folder=SentItems`, window=7 days.
2. **Exclude all messages whose sole recipient is a self-forwarding address.** Consult `references/self-forward-exclusion-list.md`.
3. For each remaining sent message, check whether a reply exists in the thread.
4. Flag threads with no reply >48h as "awaiting response."
5. Include the flagged list in the Weekly Digest.

## Tool Usage Protocols

Always use fully-qualified MCP tool names.

**Microsoft 365 MCP — primary inbox source**
- `microsoft-365:outlook_email_search` — search inbox, sent, folders
- `microsoft-365:outlook_calendar_search` — pull calendar context when a follow-up depends on a meeting
- `microsoft-365:sharepoint_search` — pull referenced documents cited in mail
- `microsoft-365:chat_message_search` — cross-reference Teams chat context
- `microsoft-365:find_meeting_availability` — when follow-up requires scheduling
- `microsoft-365:read_resource` — fetch a specific resource by URI

**Superhuman Mail MCP — secondary inbox source**
- `superhuman-mail:list_threads` — paginated thread listing
- `superhuman-mail:get_thread` / `superhuman-mail:get_message` — thread and message detail
- `superhuman-mail:query_email_and_calendar` — combined inbox + calendar query
- `superhuman-mail:list_labels` / `superhuman-mail:list_splits` — label/split semantics
- `superhuman-mail:get_attachment` — attachment pull
- `superhuman-mail:create_or_update_draft` / `superhuman-mail:send_draft` — drafting (only after churchill-hemingway-engine has produced copy)
- `superhuman-mail:trash_thread` / `superhuman-mail:mark_spam` / `superhuman-mail:update_thread` / `superhuman-mail:unsubscribe` — NOISE tier actions; require explicit user approval before executing

**HubSpot MCP — optional cross-reference**
- `hubspot:search_contacts` — resolve a sender against the 39-contact book
- `hubspot:get_contact` — full contact record when stage ambiguity exists

**Calendar — context only**
- `microsoft-365:outlook_calendar_search` by default
- Google Calendar tools only if the user explicitly references Google

For fallback logic on MCP auth failures, see `references/tool-fallback-logic.md`.

## Output Formats

Every output uses one of four templates, defined in full in `references/output-templates.md`.

**Triage Report** — grouped by tier, HIGH first. Each item: subject, sender, one-line summary, recommended action. No pleasantries, no headers beyond the tier labels.

**Pipeline Roll-Up** — table. Columns per Workflow 2. Sorted by urgency desc, then stage.

**Follow-Up Queue** — ranked list. Each item: sender, deadline, three draft points.

**Weekly Digest** — five sections: tier counts, pipeline movement, stalls, sent-items audit, recommended Monday focus.

## Composition with Other Skills

This skill composes with:

- **`churchill-hemingway-engine`** — invoked whenever actual prose is drafted. Pass draft points; receive finished copy. Never draft prose here directly.
- **`momentum-engine`** (pending Phase 2) — when triage surfaces a pipeline action that needs to be created or advanced, pass the item to momentum-engine for action creation. Until momentum-engine ships, emit the recommended action as plain text in the Triage Report.
- **`outreach-workflow`** (pending Phase 2) — when triage surfaces a prospect requiring net-new outreach (not a reply), hand off. Until outreach-workflow ships, flag with the tag `[OUTREACH-CANDIDATE]` in the report and proceed.

## Success Criteria

This skill ships successfully when all four are met:

1. Three consecutive triage sessions complete without MCP tool errors.
2. Pipeline items extracted and categorized match the audit-baseline quality (stage, contact, next action correct on ≥90% of items).
3. Triage time is measurably lower than the prior Copilot-assisted baseline.
4. Sessions reliably process 50+ emails with full tier categorization.

## Known Issues and Migration Notes

- **Migration from Gmail-v0.** A prior version of this skill incorrectly referenced Gmail MCP tools. All inbox tool references are now M365/Outlook-native. If the user or any downstream skill still references a Gmail tool name, treat that as a bug and substitute the correct `microsoft-365:outlook_*` equivalent.
- **M365 reauthentication.** The Microsoft 365 MCP connector's OAuth token can expire. On `401` or `invalid_grant`: stop the workflow, inform the user, and direct them to Settings > Connectors > Microsoft 365 > Reconnect. Do not retry silently. See `references/tool-fallback-logic.md`.
- **Self-forward exclusion is non-negotiable.** Will auto-forwards Outlook mail to four personal addresses for mobile reading. Any sent-items audit that counts mail to those addresses as "outbound" will be wrong. The exclusion list lives in `references/self-forward-exclusion-list.md` and must be applied to every sent-items pass.
- **Superhuman action tools require explicit user consent.** `trash_thread`, `mark_spam`, `unsubscribe`, and `send_draft` mutate state. Never call without a direct user instruction for that specific item.

## References

Detail files. Load only when the workflow needs them.

- `references/triage-tier-definitions.md` — full decision rules for HIGH / MEDIUM / LOW / NOISE classification, with examples drawn from HUB commercial P&C inbox patterns.
- `references/pipeline-stage-taxonomy.md` — definitions and entry/exit criteria for prospecting, active pursuit, proposal, closing, stalled.
- `references/hub-internal-senders.md` — domain list and name list for recognizing internal HUB International traffic, including Erie office, regional leadership, carrier reps, and shared mailboxes.
- `references/self-forward-exclusion-list.md` — the four self-forwarding addresses to exclude from sent-items analysis: wblooms325@gmail.com, williebeamin459@gmail.com, will.bloomstine@outlook.com, wb@lakeshark.co.
- `references/output-templates.md` — exact markdown templates for Triage Report, Pipeline Roll-Up, Follow-Up Queue, and Weekly Digest.
- `references/tool-fallback-logic.md` — decision tree for MCP auth failures, rate limits, and when to fall back from M365 to Superhuman Mail.
