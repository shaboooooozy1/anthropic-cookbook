# Triage Tier Definitions

> **Status:** Stub. Flesh out over the first two triage sessions with real examples drawn from HUB commercial P&C inbox patterns.

Every unread message resolves to exactly one tier. Apply rules in order; first match wins.

## HIGH — respond today

Force HIGH when any one of the following is true:

- **Active pipeline signal.** Subject or body references an open quote, bind request, proposal review, or renewal within 30 days.
- **Unread client reply.** A client or prospect has replied to an outbound thread where the last message was ours.
- **Compliance deadline.** Subject/body references carrier filing, state DOI filing, audit response, or a dated regulatory request.
- **Named principal.** Sender is a C-level contact at a named prospect or current client, or a carrier underwriter with a quote in flight.
- **Inbound lead.** First-touch message from a prospect not yet in HubSpot.

## MEDIUM — respond within 24–48h

Default for internal HUB International traffic (see `hub-internal-senders.md`) unless it matches a HIGH pattern. Also:

- Carrier or wholesaler updates referencing an account we manage but no immediate action.
- Scheduling threads with no hard deadline.
- Cross-team asks from regional leadership that are not time-critical.

## LOW — respond end of week or batch

- FYI traffic cc'd without a named ask.
- Industry newsletters and carrier product updates with no account reference.
- Internal training / announcements / HR broadcasts with no action required.

## NOISE — unsubscribe, archive, or mark spam

- Cold vendor pitches with no existing relationship.
- Automated notifications already surfaced through another channel.
- Marketing blasts the user has repeatedly ignored.

NOISE-tier actions (`trash_thread`, `mark_spam`, `unsubscribe`) require explicit user approval before execution. Never auto-delete.

## Worked Examples

*To be added. Capture three real examples per tier after the first triage session.*
