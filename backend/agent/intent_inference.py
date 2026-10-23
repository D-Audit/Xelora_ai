"""
agent/intent_inference.py

Predictive intent system: analyzes user instructions to infer implicit steps
that aren't explicitly stated but are common in similar workflows.

Example:
  User: "Add totals" 
  ? Infers: Identify numeric columns ? Add SUM formulas ? Format totals row
  
  User: "Create a dashboard"
  ? Infers: Create summary sheet ? Add KPI cells ? Add charts ? Apply theme
"""

import json
import re
from copy import deepcopy
from typing import List, Dict, Optional


INTENT_PATTERNS = {
    # Pattern: "Add totals" / "Add sum row"
    "add_totals": {
        "keywords": ["total", "sum", "add up", "aggregate"],
        "implicit_steps": [
            {
                "description": "Identify additive numeric measures; exclude IDs, dates, percentages and existing subtotals",
                "tool_hint": "read_range",
                "is_critical": False,
                "success_criteria": "Detected numeric columns"
            },
            {
                "description": "Add totals for the requested additive measures, avoiding double-counted subtotals",
                "tool_hint": "insert_formula",
                "is_critical": True,
                "success_criteria": "Total row shows sums"
            },
            {
                "description": "Format totals row (bold, colored background)",
                "tool_hint": "format_range",
                "is_critical": False,
                "success_criteria": "Total row visually distinct"
            }
        ]
    },
    
    # Pattern: "Create dashboard"
    "create_dashboard": {
        "keywords": ["dashboard", "summary view", "overview", "analytics"],
        "implicit_steps": [
            {
                "description": "Create a summary/dashboard sheet",
                "tool_hint": "create_sheet",
                "is_critical": True,
                "success_criteria": "New sheet created"
            },
            {
                "description": "Add KPI cells with key metrics",
                "tool_hint": "insert_formula",
                "is_critical": True,
                "success_criteria": "KPI cells populated with formulas"
            },
            {
                "description": "Create visualizations (charts)",
                "tool_hint": "create_chart",
                "is_critical": True,
                "success_criteria": "Charts added to dashboard"
            },
            {
                "description": "Apply professional formatting/theme",
                "tool_hint": "apply_formatting",
                "is_critical": False,
                "success_criteria": "Dashboard looks polished"
            }
        ]
    },
    
    # Pattern: "Budget vs actual"
    "budget_analysis": {
        "keywords": ["budget vs actual", "actual vs budget", "variance"],
        "implicit_steps": [
            {
                "description": "Create variance columns ($ and %)",
                "tool_hint": "variance_analysis",
                "is_critical": True,
                "success_criteria": "Variance columns calculated"
            },
            {
                "description": "Identify and flag significant variances",
                "tool_hint": "conditional_formatting",
                "is_critical": True,
                "success_criteria": "Variances highlighted"
            },
            {
                "description": "Create summary analysis",
                "tool_hint": "create_pivot_table",
                "is_critical": False,
                "success_criteria": "Summary table created"
            }
        ]
    },
    
    # Pattern: "Scenario analysis" / "What-if"
    "scenario_analysis": {
        "keywords": ["scenario", "what-if", "sensitivity"],
        "implicit_steps": [
            {
                "description": "Create scenario builder table",
                "tool_hint": "scenario_builder",
                "is_critical": True,
                "success_criteria": "Scenario table created"
            },
            {
                "description": "Add parameter variation rows",
                "tool_hint": "write_table",
                "is_critical": True,
                "success_criteria": "Scenarios populated"
            },
            {
                "description": "Create visualization of results",
                "tool_hint": "create_chart",
                "is_critical": False,
                "success_criteria": "Scenario chart created"
            }
        ]
    },
    
    # Pattern: "Format report" / "Make it look professional"
    "format_report": {
        "keywords": ["format", "professional", "style", "make it look", "pretty"],
        "implicit_steps": [
            {
                "description": "Format headers (bold, color, larger font)",
                "tool_hint": "format_range",
                "is_critical": True,
                "success_criteria": "Headers formatted"
            },
            {
                "description": "Apply number formatting (currency, decimals)",
                "tool_hint": "apply_formatting",
                "is_critical": True,
                "success_criteria": "Numbers properly formatted"
            },
            {
                "description": "Add borders and alignment",
                "tool_hint": "apply_formatting",
                "is_critical": False,
                "success_criteria": "Table looks organized"
            },
            {
                "description": "Auto-fit columns for readability",
                "tool_hint": "auto_fit_columns",
                "is_critical": False,
                "success_criteria": "Columns properly sized"
            }
        ]
    },
    
    # Pattern: "Data cleanup" / "Remove duplicates"
    "data_cleanup": {
        "keywords": ["clean", "cleanup", "duplicate", "remove duplicate", "normalize"],
        "implicit_steps": [
            {
                "description": "Inspect source rows, blanks, types and candidate duplicate keys before proposing cleanup",
                "tool_hint": "read_range",
                "is_critical": True,
                "success_criteria": "Data quality issues identified without changing source rows"
            },
            {
                "description": "Apply only requested cleanup; repeated values alone do not justify deleting rows",
                "tool_hint": "read_range",
                "is_critical": False,
                "success_criteria": "Data quality assessed"
            },
            {
                "description": "Read back cleaned data and reconcile row counts with the approved changes",
                "tool_hint": "read_range",
                "is_critical": False,
                "success_criteria": "No unintended row loss or changed identifiers"
            }
        ]
    }
}


def infer_implicit_steps(instruction: str) -> List[Dict]:
    """
    Analyze instruction and infer implicit steps based on intent patterns.
    
    Returns list of implicit subtasks to prepend to the explicit plan.
    """
    instruction_lower = instruction.lower()
    
    # Score each pattern
    scores = {}
    for pattern_key, pattern_info in INTENT_PATTERNS.items():
        score = 0
        for keyword in pattern_info["keywords"]:
            if re.search(r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", instruction_lower):
                score += 1
        scores[pattern_key] = score
    
    # Find best matching pattern
    best_pattern = max(scores, key=scores.get)
    if scores[best_pattern] == 0:
        return []  # No matching pattern
    
    # Return implicit steps from best pattern
    implicit = []
    pattern_data = INTENT_PATTERNS[best_pattern]
    
    for idx, step in enumerate(pattern_data["implicit_steps"]):
        implicit_task = {
            "id": f"implicit_{idx + 1}",
            "description": f"[Auto-inferred] {step['description']}",
            "tool_hint": step["tool_hint"],
            "target_sheet": "auto",
            "cell_range": None,
            "depends_on": [f"implicit_{idx}"] if idx > 0 else [],
            "is_critical": step["is_critical"],
            "success_criteria": step["success_criteria"],
            "is_implicit": True,
            "confidence": scores[best_pattern] / len(pattern_data["keywords"])
        }
        implicit.append(implicit_task)
    
    return implicit


def enhance_plan_with_intent(explicit_plan: List[Dict], instruction: str) -> List[Dict]:
    """
    Combine explicit plan from user instruction with inferred implicit steps.
    
    Returns merged plan with implicit steps first.
    """
    implicit_steps = infer_implicit_steps(instruction)
    
    if not implicit_steps:
        return explicit_plan
    
    # Preserve explicit IDs and dependency edges: changing only references
    # creates dangling/self dependencies. Do not mutate the caller's plan.
    explicit_plan = deepcopy(explicit_plan)
    occupied = {step["id"] for step in explicit_plan}
    previous = None
    for index, step in enumerate(implicit_steps, 1):
        candidate = f"implicit_{index}"
        while candidate in occupied:
            candidate = "inferred_" + candidate
        occupied.add(candidate)
        step["id"] = candidate
        step["depends_on"] = [previous] if previous else []
        previous = candidate
    for step in explicit_plan:
        if not step.get("depends_on"):
            step["depends_on"] = [previous]
    
    # Merge: implicit first, then explicit
    merged = implicit_steps + explicit_plan
    
    return merged


# Quick test
if __name__ == "__main__":
    test_instructions = [
        "Add totals to the Q3 budget report",
        "Create a dashboard showing sales by region",
        "Budget vs actual analysis with variance",
        "Clean up the customer data and remove duplicates",
    ]
    
    for instr in test_instructions:
        print(f"\nInstruction: {instr}")
        steps = infer_implicit_steps(instr)
        print(f"Inferred {len(steps)} implicit steps:")
        for step in steps:
            print(f"  - {step['description']} ({step['tool_hint']})")
