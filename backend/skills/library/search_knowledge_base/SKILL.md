---
name: search_knowledge_base
category: knowledge
description: "Searches this user's stored company knowledge (previously ingested documents, manuals, SOPs, past reports) for passages relevant to a query. Use this before writing a report or answering a question that should reflect company-specific context rather than general knowledge."
source: migrated from skills/knowledge_skills.py
---

# search_knowledge_base

Searches this user's stored company knowledge (previously ingested documents, manuals, SOPs, past reports) for passages relevant to a query. Use this before writing a report or answering a question that should reflect company-specific context rather than general knowledge.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string"
    },
    "top_k": {
      "type": "integer",
      "default": 5
    }
  },
  "required": [
    "query"
  ]
}
```

## Implementation

See `impl.py` in this folder. It exposes a single function `run(**kwargs)`
matching the input schema above.
