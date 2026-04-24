# Output Templates

Verbatim markdown for the four output artifacts. Use exactly. No pleasantries, no padding, no emojis.

---

## Triage Report

```markdown
# Triage Report — {{date}}
Window: {{window_hours}}h · Messages reviewed: {{count}}

## HIGH ({{count_high}})
- **{{subject}}** — {{sender}} · {{one_line_summary}}
  Action: {{verb}} {{object}}

## MEDIUM ({{count_medium}})
- **{{subject}}** — {{sender}} · {{one_line_summary}}
  Action: {{verb}} {{object}}

## LOW ({{count_low}})
- {{subject}} — {{sender}}

## NOISE ({{count_noise}})
- {{count}} messages flagged for unsubscribe/trash. Awaiting approval.
```

Ordering: HIGH first, then MEDIUM, then LOW. NOISE last and summarized, not enumerated.

---

## Pipeline Roll-Up

```markdown
# Pipeline Roll-Up — {{date}}

| Item | Contact | Stage | Last Touch | Next Action | Urgency |
|---|---|---|---|---|---|
| {{item}} | {{contact}} | {{stage}} | {{date}} | {{verb}} {{object}} | {{urgency}} |
```

Sort: urgency DESC (HIGH → LOW), then stage in canonical order (closing, proposal, active pursuit, prospecting, stalled).

---

## Follow-Up Queue

```markdown
# Follow-Up Queue — {{date}}

## Today
- **{{sender}}** — due today
  - {{draft_point_1}}
  - {{draft_point_2}}
  - {{draft_point_3}}

## 24h
- **{{sender}}** — due {{date+24h}}
  - {{draft_point_1}}
  - {{draft_point_2}}

## 48h
- ...

## End of Week
- ...
```

If the user asks for drafted prose rather than points, invoke `churchill-hemingway-engine` with these points as input.

---

## Weekly Digest

```markdown
# Weekly Digest — Week of {{monday_date}}

## 1. Tier Counts
- HIGH: {{count}} · MEDIUM: {{count}} · LOW: {{count}} · NOISE: {{count}}
- Week-over-week HIGH delta: {{+/-count}}

## 2. Pipeline Movement
- New items: {{count}}
- Stage advances: {{count}}
- Stage regressions: {{count}}
- Closed won: {{count}} · Closed lost: {{count}}

## 3. Stalled Threads ({{count}})
- **{{contact}}** — {{stage}} · last touch {{date}} · suggested action: {{verb}} {{object}}

## 4. Sent-Items Audit
- Outbound sent (self-forwards excluded): {{count}}
- Awaiting response >48h: {{count}}
  - {{recipient}} — subject: {{subject}} — sent {{date}}

## 5. Monday Focus
- Three items the operator should move first Monday morning, in order.
- 1. ...
- 2. ...
- 3. ...
```
