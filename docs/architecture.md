# Architecture

## Core Philosophy

Leaknote is a **behavior-changing system**, not just storage. The key insight:

> Humans do one thing (capture), automation does everything else.

Traditional second-brain systems fail because they require cognitive work at capture time - deciding categories, tags, folders. Leaknote eliminates this friction.

## The Core Loop

```
Capture → Classify → Route → Store → Surface
   ↑                                    |
   └────────── Feedback Loop ───────────┘
```

1. **Capture**: You throw a thought at the Matrix channel
2. **Classify**: LLM determines what type of thought it is
3. **Route**: System decides which table to store it in
4. **Store**: Record is created with extracted fields
5. **Surface**: Digests and queries bring information back to you

## Building Blocks

| Block | Purpose | Implementation |
|-------|---------|----------------|
| **Dropbox** | Frictionless capture point | Matrix channel `#leaknote-inbox` |
| **Sorter** | AI classification | GLM-4 with classification prompt |
| **Form** | Consistent schema per category | PostgreSQL tables with defined fields |
| **Filing Cabinet** | Structured storage | PostgreSQL database |
| **Receipt** | Audit trail | `inbox_log` table |
| **Bouncer** | Confidence filter | Threshold check (default 0.6) |
| **Tap on Shoulder** | Proactive surfacing | Daily digest, weekly review |
| **Fix Button** | One-step corrections | `fix:` reply command |

## Categories

### Dynamic Categories (LLM-inferred)

No prefix required - just capture naturally.

| Category | Fields | Surfaces In |
|----------|--------|-------------|
| **people** | name, context, follow_ups, last_touched, tags | Daily: upcoming follow-ups |
| **projects** | name, status, next_action, notes, tags | Daily: active + next actions |
| **ideas** | title, one_liner, elaboration, tags | Weekly: ideas captured |
| **admin** | name, due_date, status, notes, tags | Daily: due soon |

### Reference Categories (prefix required)

Explicit intent declaration for retrievable knowledge.

| Category | Prefix | Fields | Surfaces In |
|----------|--------|--------|-------------|
| **decisions** | `decision:` | title, decision, rationale, context, tags | Weekly: recent decisions |
| **howtos** | `howto:` | title, content, tags | On-demand only |
| **snippets** | `snippet:` | title, content, tags | On-demand only |

### Why the Split?

Dynamic categories are for **fluid capture** - thoughts that need processing, follow-up, or action. The AI routes them automatically.

Reference categories are for **canonical knowledge** - things you deliberately want to retrieve later. The prefix signals intent: "I'm creating a record, not just dumping a thought."

This distinction preserves the frictionless capture experience while enabling high-quality reference storage.

## Capture Rules

### Dynamic (80% of inputs)

```
Met João at conference, works on EHR integration
→ LLM detects: person mentioned → routes to people

Need to review papercage nftables rules this week
→ LLM detects: task with multiple steps → routes to projects

Could use Matrix reactions for quick triage
→ LLM detects: possibility to explore → routes to ideas

Renew domain carloszan.com by January 15
→ LLM detects: task with deadline → routes to admin
```

### Reference (20% of inputs)

```
decision: Using Postgres over markdown because queryability
→ Prefix detected → routes to decisions

howto: Restart papercage → systemctl --user restart papercage-sandbox
→ Prefix detected → routes to howtos

snippet: Firejail base → firejail --net=none --private-tmp --private-dev
→ Prefix detected → routes to snippets
```

## Trust Mechanisms

### Confidence Threshold

When the classifier is uncertain (confidence < 0.6), it asks for clarification instead of filing:

```
🤔 Not sure about this one.
Best guess: idea (45% confident)

Reply with one of:
• `person:` - if about a person
• `project:` - if it's a project
• ...
```

### Audit Trail

Every capture is logged in `inbox_log`:

- Original text
- Destination table
- Record ID
- Confidence score
- Status (filed, needs_review, fixed)

### Fix Command

Any misclassification can be corrected with a simple reply:

```
fix: people
```

The system moves the record to the correct table.

## Surfacing

### Daily Digest (06:00)

Short, actionable briefing (<150 words):

- Top 3 actions for today
- Due soon items
- People to follow up with
- One stuck/blocked item
- One recent decision

### Weekly Review (Sunday 16:00)

Reflective summary (<250 words):

- What happened this week
- Open loops (stuck/waiting items)
- 3 suggested actions for next week
- Pattern noticed
- Ideas captured
- Decisions made

### On-Demand Retrieval

Query commands for instant access:

```
?recall postgres decision
→ Searches decisions, howtos, snippets
→ LLM formats results into helpful response

?projects active
→ Lists all active projects with next actions
```

## Design Principles

1. **One human behavior**: Capture to Matrix, nothing else required
2. **Separate memory/compute/interface**: Swap any layer independently
3. **Prompts as APIs**: Fixed input/output schema, JSON only, no surprises
4. **Trust through transparency**: Audit log, confidence scores, easy corrections
5. **Small outputs**: Daily <150 words, weekly <250 words
6. **Next action as unit**: Not "work on website" but "email Sarah about copy"
7. **Routing over organizing**: Let the system route into stable buckets
8. **Design for restart**: No guilt, no backlog monster
