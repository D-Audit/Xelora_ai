"""seed_templates.py - ADDITIVE. Seeds a handful of starter workflow
templates on first run, so /dashboard/templates isn't empty on a fresh
database. Safe to run every startup - it checks for existing rows
first."""
from sqlalchemy.orm import Session
from workspace_models import WorkflowTemplate

_DEFAULT_TEMPLATES = [
    {
        "name": "Clean and deduplicate",
        "description": "Removes blank rows, trims whitespace, and deletes duplicate rows.",
        "category": "cleaning",
        "steps": [
            {"name": "Remove blank rows", "description": "Delete fully empty rows.", "type": "clean", "isEnabled": True, "requiresApproval": False, "errorBehaviour": "stop", "estimatedAiActions": 1},
            {"name": "Trim whitespace", "description": "Strip leading/trailing spaces from all text cells.", "type": "clean", "isEnabled": True, "requiresApproval": False, "errorBehaviour": "skip", "estimatedAiActions": 1},
            {"name": "Deduplicate rows", "description": "Remove exact duplicate rows.", "type": "deduplicate", "isEnabled": True, "requiresApproval": False, "errorBehaviour": "stop", "estimatedAiActions": 1},
        ],
    },
    {
        "name": "Monthly revenue summary",
        "description": "Builds a pivot table and chart summarising revenue by region and month.",
        "category": "reporting",
        "steps": [
            {"name": "Build pivot table", "description": "Summarise revenue by region and month.", "type": "report", "isEnabled": True, "requiresApproval": False, "errorBehaviour": "stop", "estimatedAiActions": 2},
            {"name": "Add chart", "description": "Insert a column chart of the pivot output.", "type": "chart", "isEnabled": True, "requiresApproval": False, "errorBehaviour": "skip", "estimatedAiActions": 1},
        ],
    },
    {
        "name": "Sort and format",
        "description": "Sorts by a key column and applies consistent number/date formatting.",
        "category": "formatting",
        "steps": [
            {"name": "Sort rows", "description": "Sort by the first column, ascending.", "type": "sort", "isEnabled": True, "requiresApproval": False, "errorBehaviour": "stop", "estimatedAiActions": 1},
            {"name": "Apply formatting", "description": "Format currency and date columns consistently.", "type": "format", "isEnabled": True, "requiresApproval": False, "errorBehaviour": "skip", "estimatedAiActions": 1},
        ],
    },
]


def seed_default_templates(db: Session) -> None:
    if db.query(WorkflowTemplate).count() > 0:
        return
    for t in _DEFAULT_TEMPLATES:
        db.add(WorkflowTemplate(name=t["name"], description=t["description"], category=t["category"], steps=t["steps"], is_public=True))
    db.commit()
