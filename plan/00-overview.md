# Second Brain: Self-Hosted Implementation Plan

## Overview

A self-hosted "second brain" system that captures thoughts via Matrix, classifies them with LLMs, stores them in PostgreSQL, and surfaces relevant information through daily/weekly digests and on-demand retrieval.

## Core Philosophy

- **One human behavior**: Capture to Matrix channel, nothing else required
- **AI does the routing**: No tagging, no organizing at capture time
- **References require intent**: Prefix-based declaration for decisions/howtos/snippets
- **Trust through transparency**: Audit log, confidence scores, easy corrections
- **Design for restart**: No guilt, no backlog monster

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         INTERFACE                                │
│                                                                  │
│   Matrix (Dendrite)  ←→  Element/FluffyChat                     │
│   - #sb-inbox channel (capture)                                  │
│   - DM from bot (digests, confirmations)                        │
│   - Query commands (?recall, ?search)                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         COMPUTE                                  │
│                                                                  │
│   Python Bot (matrix-nio)                                        │
│   ├── Listener: watches #sb-inbox                               │
│   ├── Classifier: LLM routing                                   │
│   │   ├── GLM-4: classification tasks                           │
│   │   └── Claude: summaries, retrieval                          │
│   ├── Router: prefix detection + confidence check               │
│   ├── Responder: confirms, offers fix, answers queries          │
│   └── Cron jobs:                                                │
│       ├── daily_digest.py (06:00)                               │
│       └── weekly_review.py (Sunday 16:00)                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         MEMORY                                   │
│                                                                  │
│   PostgreSQL                                                     │
│   ├── people                                                    │
│   ├── projects                                                  │
│   ├── ideas                                                     │
│   ├── admin                                                     │
│   ├── decisions                                                 │
│   ├── howtos                                                    │
│   ├── snippets                                                  │
│   └── inbox_log                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Categories

### Dynamic Categories (LLM-inferred, no prefix)

| Category | Fields | Surfaces In |
|----------|--------|-------------|
| **people** | name, context, follow_ups, last_touched, tags | Daily: upcoming follow-ups |
| **projects** | name, status, next_action, notes, tags | Daily: active + next actions |
| **ideas** | title, one_liner, elaboration, tags | Weekly: ideas captured |
| **admin** | name, due_date, status, notes, tags | Daily: due soon |

### Reference Categories (prefix required)

| Category | Prefix | Fields | Surfaces In |
|----------|--------|--------|-------------|
| **decisions** | `decision:` | title, decision, rationale, context, tags | Weekly: recent decisions |
| **howtos** | `howto:` | title, content, tags | On-demand only |
| **snippets** | `snippet:` | title, content, tags | On-demand only |

## Capture Rules

```
# Dynamic - just type, AI figures it out
Met João at conference, works on EHR integration
Need to review papercage nftables rules
Could use Matrix reactions for quick triage
Renew domain carloszan.com by Jan 15

# References - prefix required
decision: Using Postgres over markdown because queryability and atomicity
howto: Restart papercage → systemctl --user restart papercage-sandbox
snippet: Firejail base → firejail --net=none --private-tmp --private-dev
```

## Query Commands

```
?recall <query>     → searches decisions, howtos, snippets
?search <query>     → searches all categories
?people <query>     → searches people only
?projects [status]  → lists projects, optionally by status
?ideas              → lists recent ideas
?admin [due]        → lists admin tasks, optionally due soon
```

## Phases

| Phase | Focus | Deliverable |
|-------|-------|-------------|
| 1 | Core loop | Capture → Classify → Store |
| 2 | Trust mechanisms | Confirmations, fix command, inbox_log |
| 3 | Daily digest | Morning summary via Matrix DM |
| 4 | Weekly review | Sunday summary via Matrix DM |
| 5 | On-demand retrieval | ?recall, ?search commands |
| 6 | Refinements | Tuning, restart procedures, maintenance |

## Files in This Plan

- `00-overview.md` - This file
- `01-phase1-core-loop.md` - Database schema, bot skeleton, classifier
- `02-phase2-trust.md` - Confirmations, fix mechanism, logging
- `03-phase3-daily-digest.md` - Morning digest implementation
- `04-phase4-weekly-review.md` - Sunday review implementation
- `05-phase5-retrieval.md` - Query commands implementation
- `06-phase6-refinements.md` - Tuning, maintenance, restart guide
- `07-prompts.md` - All LLM prompts (classification, summarization, retrieval)
- `08-deployment.md` - Systemd units, cron setup, environment config
