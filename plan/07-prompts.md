# LLM Prompts Reference

All prompts used in the second brain system, in one place for easy tuning.

## 1. Classification Prompt

Used by: `classifier.py`
Model: GLM-4 (cheap, fast)
Purpose: Classify a thought into one of the 4 dynamic categories

```
You are a classifier for a personal knowledge management system.

Given a raw thought, classify it into ONE of these categories:
- people: Information about a person, relationship notes, follow-up reminders for someone
- projects: Active work items, tasks with multiple steps, ongoing efforts
- ideas: Insights, possibilities, things to explore later
- admin: Errands, single tasks with deadlines, administrative duties

Return ONLY valid JSON with this exact structure:
{
  "category": "people|projects|ideas|admin",
  "confidence": 0.0-1.0,
  "extracted": {
    // For people: {"name": "", "context": "", "follow_ups": ""}
    // For projects: {"name": "", "status": "active", "next_action": "", "notes": ""}
    // For ideas: {"title": "", "one_liner": "", "elaboration": ""}
    // For admin: {"name": "", "due_date": "YYYY-MM-DD or null", "notes": ""}
  },
  "tags": ["tag1", "tag2"]
}

Rules:
- Extract a clear, actionable next_action for projects (not vague intentions)
- For people, extract any mentioned follow-ups
- For admin, extract due dates if mentioned (interpret "next week", "by Friday", etc.)
- Tags should be 1-3 relevant keywords
- Confidence should reflect how certain you are about the category

Input thought:
```

### Tuning Notes

- **Temperature**: 0.1 (low for consistency)
- **If too many misclassifications**: Add examples to the prompt
- **If next_actions are vague**: Strengthen the "actionable" instruction
- **If dates not parsed**: Add more date format examples

### Example Inputs/Outputs

Input: `Met João at conference, works on EHR integration at Hospital X`

Expected output:
```json
{
  "category": "people",
  "confidence": 0.92,
  "extracted": {
    "name": "João",
    "context": "Met at conference, works on EHR integration at Hospital X",
    "follow_ups": ""
  },
  "tags": ["conference", "EHR", "healthcare"]
}
```

Input: `Need to review papercage nftables rules this week`

Expected output:
```json
{
  "category": "projects",
  "confidence": 0.88,
  "extracted": {
    "name": "Papercage nftables review",
    "status": "active",
    "next_action": "Review nftables rules for papercage",
    "notes": "This week"
  },
  "tags": ["papercage", "security", "networking"]
}
```

---

## 2. Daily Digest Prompt

Used by: `digest.py`
Model: Claude (quality matters for summaries)
Purpose: Generate actionable morning briefing

```
You are generating a daily digest for a personal knowledge management system.

Your job is to create a SHORT, ACTIONABLE morning briefing.

STRICT CONSTRAINTS:
- Maximum 150 words total
- No fluff, no greetings, no encouragement
- Focus on ACTIONS, not descriptions
- Use bullet points sparingly

FORMAT:
## Today's Focus
[Top 3 most important actions - be specific]

## Due Soon
[Any deadlines in next 3 days]

## Follow Up
[Any people to reach out to]

## Watch Out
[One stuck/blocked item if any]

## Recent Decision
[One recent decision as a reminder, if any]

If a section has nothing, omit it entirely.

DATA:
```

### Tuning Notes

- **If too long**: Reduce word limit, add "be extremely concise"
- **If too generic**: Add "use specific names and actions from the data"
- **If missing sections**: The model might think there's nothing relevant; check data formatting

---

## 3. Weekly Review Prompt

Used by: `weekly_review.py`
Model: Claude
Purpose: Reflective weekly summary with patterns

```
You are generating a weekly review for a personal knowledge management system.

Your job is to create a thoughtful but CONCISE week-in-review.

STRICT CONSTRAINTS:
- Maximum 250 words total
- Be analytical, not descriptive
- Identify patterns and themes
- Suggest specific actions

FORMAT:
## This Week
[2-3 sentence summary of activity and progress]

## Open Loops
[Top 2-3 stuck or waiting items that need attention]

## Next Week
[3 specific, actionable suggestions]

## Pattern Noticed
[One theme or pattern across this week's entries]

## Ideas Captured
[List of ideas from this week, if any]

## Decisions Made
[List of decisions from this week, if any]

If a section has nothing meaningful, omit it.
Be direct. No pleasantries.

DATA:
```

### Tuning Notes

- **If patterns seem shallow**: Add "look for recurring themes, repeated concerns, or related items across categories"
- **If suggestions generic**: Add "suggestions should reference specific projects or people from the data"

---

## 4. Retrieval/Search Prompt

Used by: `commands.py`
Model: Claude
Purpose: Format search results into helpful response

```
You are formatting search results from a personal knowledge management system.

Given the search results below, create a CONCISE response that:
1. Directly answers the query if possible
2. Lists the most relevant results
3. Includes key details (content for howtos, rationale for decisions)

Keep response under 200 words. Use bullet points for multiple results.
If there's a clear answer (like a howto command), lead with that.

QUERY: {query}

RESULTS:
{results}

FORMAT YOUR RESPONSE:
```

### Tuning Notes

- **If howtos not surfaced clearly**: Add "For howtos, always show the exact command or steps first"
- **If too verbose**: Reduce word limit
- **If missing context**: Add "include dates and sources for each result"

---

## 5. Future: Natural Query Detection Prompt

Not yet implemented. Would detect if a message is a query vs. capture.

```
Classify this message as either CAPTURE or QUERY.

CAPTURE: The user wants to save/remember something
QUERY: The user wants to retrieve/find something

Examples:
- "Met João at conference" → CAPTURE
- "How do I restart papercage?" → QUERY
- "Need to review nftables" → CAPTURE
- "What did I decide about postgres?" → QUERY
- "decision: use postgres" → CAPTURE
- "?recall postgres" → QUERY

Message: {message}

Return JSON: {"type": "capture" | "query"}
```

---

## Prompt Engineering Principles

### 1. Fixed Output Format

All prompts specify exact JSON structure. This makes parsing reliable:
- No markdown code fences
- No explanatory text
- No creative variations

### 2. Examples > Instructions

When classification is failing, adding 2-3 examples works better than more instructions.

### 3. Negative Constraints

"No fluff, no greetings" works better than "be concise".

### 4. Word Limits

Explicit word limits (150, 250) prevent rambling.

### 5. Section Omission

"If a section has nothing, omit it" prevents filler content.

---

## Model Selection

| Task | Model | Reason |
|------|-------|--------|
| Classification | GLM-4 | Fast, cheap, reliable for structured output |
| Daily digest | Claude | Quality matters for actionable summaries |
| Weekly review | Claude | Needs pattern recognition, analysis |
| Search formatting | Claude | Better at natural responses |

### Cost Optimization

- Classification happens on every capture → use cheapest model that works
- Digests happen 1x/day → can afford better model
- Search happens on-demand → use Claude but cache if repeated

---

## Debugging Prompts

### If classification is wrong

1. Add the failed input to a test file
2. Run classification manually:

```python
import asyncio
from classifier import classify_thought

result = asyncio.run(classify_thought("your test input"))
print(result)
```

3. Adjust prompt based on failure mode

### If digest is too long/short

1. Check word count of recent digests
2. Adjust word limit in prompt
3. Add/remove sections as needed

### If search results unhelpful

1. Check raw search results (before LLM formatting)
2. If results are good but formatting bad → adjust retrieval prompt
3. If results are bad → improve PostgreSQL full-text search or add embeddings
