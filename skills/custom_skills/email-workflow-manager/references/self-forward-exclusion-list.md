# Self-Forward Exclusion List

Purpose: the user auto-forwards Outlook mail to four personal addresses for mobile reading. Any sent-items audit that counts mail to those addresses as "outbound" will be wrong. This list is non-negotiable — apply on every sent-items pass (Workflow 5).

## Exclusion Rule

When running Workflow 5 (Sent-Items Audit), **exclude every message whose sole recipient is on the list below.** If the message has additional recipients, do not exclude — the forward and the real send are the same message.

## Addresses

- `wblooms325@gmail.com`
- `williebeamin459@gmail.com`
- `will.bloomstine@outlook.com`
- `wb@lakeshark.co`

## Usage Notes

- These are personal addresses used strictly for mobile reading convenience. They are not counted as business correspondence.
- If the user adds or changes a self-forwarding address, update this file. The exclusion is driven by this list, not by pattern matching.
- Inbound mail from these addresses (e.g., the user replying to themselves) should also be excluded from pipeline extraction — it is not a third-party signal.
