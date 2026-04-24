# HUB Internal Senders

> **Status:** Stub. Populate domain list and named-contact table during Phase 1 rollout.

Purpose: let the triage workflow recognize HUB International internal traffic so it defaults to MEDIUM unless a HIGH signal is present.

## Domain Patterns

Treat any message from the following domains as internal HUB traffic:

- `hubinternational.com`
- `*.hubinternational.com` (regional subdomains)

Cross-check for display-name spoofing: an external sender using "HUB International" in their display name does not count as internal unless the From address matches the domains above.

## Named Internal Contacts

*To be populated.* Track at minimum:

| Name | Role | Office | Default Tier |
|---|---|---|---|
| *(Erie office team members)* | | Erie, PA | MEDIUM |
| *(Regional leadership)* | | Regional | MEDIUM, HIGH if direct ask |
| *(Carrier reps inside HUB)* | | Varies | MEDIUM |

## Shared Mailbox Patterns

Recognize shared / distribution aliases and route per rules below:

- `*-submissions@hubinternational.com` → MEDIUM, extract as pipeline candidate if referencing a named account.
- `*-team@hubinternational.com` → LOW by default unless named in To: (not cc:).
- `noreply@*.hubinternational.com` → NOISE unless referencing a named account with an action.

## Override Rules

Internal traffic escalates to HIGH when any of:

- Sender is regional leadership AND message contains a direct ask ("need," "please," "by [date]").
- Message references a compliance deadline or carrier filing.
- Message references an account currently in the `closing` pipeline stage.
