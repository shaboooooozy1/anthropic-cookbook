# Pipeline Stage Taxonomy

> **Status:** Stub. Tighten signal phrases and entry/exit criteria after Phase 1 shakeout.

Every active pipeline item extracted by Workflow 2 maps to exactly one of these stages. Use the first matching stage when signals conflict.

## prospecting

- **Definition.** Initial contact; no confirmed meeting; qualification not yet complete.
- **Entry.** Inbound lead, referral introduction, or cold outreach reply.
- **Exit.** Prospect accepts a discovery call or provides exposure data.
- **Signal phrases.** "nice to meet," "happy to connect," "tell me more about HUB," "what do you guys do."

## active pursuit

- **Definition.** Qualified; discovery underway; exposures / loss runs / renewal dates being gathered.
- **Entry.** Discovery call held, or prospect shares current carrier/policy info.
- **Exit.** Submission goes to market, or proposal is delivered.
- **Signal phrases.** "loss runs attached," "current expiration," "send me your submission," "what info do you need."

## proposal

- **Definition.** Quote(s) delivered; prospect evaluating; decision window open.
- **Entry.** Proposal PDF or summary delivered.
- **Exit.** Bind instructions, or written/verbal decline.
- **Signal phrases.** "reviewing with the team," "a few questions on the quote," "comparing to incumbent," "decision by [date]."

## closing

- **Definition.** Verbal or written intent to bind; awaiting signed docs or binder.
- **Entry.** Prospect says "let's move forward," signs application, or asks for bind instructions.
- **Exit.** Policy bound (moves out of pipeline into book) or deal falls apart (moves to stalled).
- **Signal phrases.** "bind it," "send the application," "move forward with HUB," "effective [date]."

## stalled

- **Definition.** Any stage where no response has been received for more than 5 business days after last outbound touch, or where the prospect has explicitly paused.
- **Entry.** 5 business day silence after a pending ask, or explicit "circle back later."
- **Exit.** Prospect replies and reopens the thread (return to prior stage), or stage is closed out.
- **Signal phrases.** None (inferred from silence) or "let's revisit next quarter."

## Stage Hygiene Rules

- An item cannot sit in `stalled` indefinitely. Stalled >30 days → close out of pipeline or return to `prospecting` with a fresh outreach plan.
- An item cannot skip stages forward except from `prospecting` to `active pursuit` on same-thread discovery.
- Any stage regression (e.g., `proposal` → `active pursuit`) must be noted in the next Weekly Digest.
