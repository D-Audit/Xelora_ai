---
name: variance_analysis
category: analysis
description: "Builds formula-based budget-versus-actual analysis."
source: Xelora financial analysis skill
---

# Variance Analysis

Builds formula-based budget-versus-actual analysis.

Use this skill to calculate dollar and percentage variance, add status flags, and highlight material positive or negative performance with conditional formatting.

## Input schema

```json
{
  "type": "object",
  "properties": {
    "budget_column": {"type": "string", "description": "Budget column letter, for example B."},
    "actual_column": {"type": "string", "description": "Actual column letter, for example C."},
    "data_start_row": {"type": "integer", "description": "First data row; defaults to 2."},
    "data_end_row": {"type": "integer", "description": "Last data row to analyze."},
    "variance_threshold_percent": {"type": "number", "description": "Flag absolute percentage variances above this number; defaults to 10."}
  },
  "required": ["budget_column", "actual_column", "data_end_row"]
}
```
