"""
agent/skills.py
Automatic skill extraction from successful tasks.

After a task completes successfully, analyzes the action sequence
to extract reusable patterns and stores them in the skill store.
"""

import time
from typing import Optional

from memory.skill_store import add_skill, find_matching_skills, record_skill_usage
from memory.task_history import get_successful_tasks


def extract_skills_from_task(
    instruction: str,
    actions: list,
    success: bool,
    *,
    user_id: int | None = None,
) -> list:
    """Analyze a completed task and extract reusable skills.

    Returns list of extracted skill IDs.
    """
    if not success:
        return []

    extracted = []

    # Pattern: write a table then add verified formula columns.
    action_names = [a.get("name", "") for a in actions]
    if ({"write_table", "insert_formula"} <= set(action_names) or {"paste_table", "fill_formula_down"} <= set(action_names)):
        skill_id = add_skill(
            name="data_pipeline",
            description="Write tabular data and add verified formula columns",
            trigger_conditions=["add data", "paste table", "create data", "import data"],
            action_sequence=[name for name in action_names if name in {"write_table", "insert_formula", "paste_table", "fill_formula_down"}],
            tags=["data", "formulas", "pipeline"],
            user_id=user_id,
        )
        extracted.append(skill_id)

    # Pattern: navigate/create a sheet then write data there.
    if ("go_to_sheet" in action_names or "create_sheet" in action_names) and ("write_table" in action_names or "paste_table" in action_names):
        skill_id = add_skill(
            name="cross_sheet_reference",
            description="Navigate to a sheet and populate with data or formulas referencing other sheets",
            trigger_conditions=["cross sheet", "reference another sheet", "summary sheet", "dashboard"],
            action_sequence=[name for name in action_names if name in {"go_to_sheet", "create_sheet", "write_table", "paste_table"}],
            tags=["cross-sheet", "references", "formulas"],
            user_id=user_id,
        )
        extracted.append(skill_id)

    # Pattern: formatting combo (bold + color + borders)
    formatting_tools = {"bold", "set_fill_color", "set_font_color", "borders_all", "apply_formatting", "format_range", "auto_fit_columns", "conditional_formatting"}
    formatting_found = formatting_tools & set(action_names)
    if len(formatting_found) >= 2:
        skill_id = add_skill(
            name="professional_formatting",
            description="Apply professional styling with colors, bold text, and borders",
            trigger_conditions=["format table", "style table", "make it look professional",
                              "add colors", "format headers", "apply formatting"],
            action_sequence=list(formatting_found),
            tags=["formatting", "style", "colors", "borders"],
            user_id=user_id,
        )
        extracted.append(skill_id)

    # Pattern: chart creation after data
    if "create_pie_chart" in action_names or "create_chart" in action_names:
        chart_tool = "create_pie_chart" if "create_pie_chart" in action_names else "create_chart"
        skill_id = add_skill(
            name="chart_from_data",
            description="Create a chart from structured data",
            trigger_conditions=["create chart", "make chart", "add chart", "pie chart", "bar chart"],
            action_sequence=[chart_tool],
            tags=["chart", "visualization", "data"],
            user_id=user_id,
        )
        extracted.append(skill_id)

    # Pattern: multi-sheet workbook creation
    if action_names.count("create_sheet") >= 2 or action_names.count("go_to_sheet") >= 2:
        skill_id = add_skill(
            name="multi_sheet_workbook",
            description="Create and populate multiple sheets in a workbook",
            trigger_conditions=["multi sheet", "multiple sheets", "create sheets",
                              "workbook with several sheets", "separate sheets"],
            action_sequence=[name for name in action_names if name in {"create_sheet", "go_to_sheet", "write_table", "paste_table"}],
            tags=["multi-sheet", "workbook", "structure"],
            user_id=user_id,
        )
        extracted.append(skill_id)

    return extracted


def get_skill_recommendations(instruction: str, *, user_id: int | None = None) -> list:
    """Get recommended skills for the current instruction."""
    return find_matching_skills(instruction, max_results=3, user_id=user_id)


def update_skill_stats(skill_ids: list, success: bool, *, user_id: int | None = None):
    """Update success/failure stats for used skills."""
    for skill_id in skill_ids:
        record_skill_usage(skill_id, success, user_id=user_id)
