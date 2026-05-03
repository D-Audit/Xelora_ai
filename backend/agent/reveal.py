"""
agent/reveal.py
Reveal Workflow + Intelligent Progress Visualization.

Reveal Workflow: turns the raw action log into the sequence of native
Excel feature names a human would recognize ("Data > Sort", "Insert >
PivotTable") instead of internal tool/skill names - hidden by default,
the user can request it at any time to learn/verify/reproduce what the
AI did manually.

Progress Visualization: structures the same log into current task /
completed actions / decision explanations, for a live status view.
"""

NATIVE_FEATURE_NAMES = {
    "read_range": "Selecting a range",
    "inspect_workbook": "Reviewing the sheet",
    "write_cell": "Typing into a cell",
    "insert_formula": "Entering a formula",
    "write_table": "Typing a table of data",
    "remove_duplicates": "Data > Remove Duplicates",
    "sort_range": "Data > Sort",
    "filter_data": "Data > Filter",
    "find_replace": "Home > Find & Select > Replace",
    "apply_formatting": "Home > Font / Number Format",
    "conditional_formatting": "Home > Conditional Formatting",
    "freeze_panes": "View > Freeze Panes",
    "auto_fit_columns": "Home > Format > AutoFit Column Width",
    "create_chart": "Insert > Chart",
    "create_pivot_table": "Insert > PivotTable",
    "create_named_range": "Formulas > Name Manager > New Name",
    "create_sheet": "Right-click sheet tabs > Insert Sheet",
    "rename_sheet": "Double-click sheet tab > Rename",
    "delete_sheet": "Right-click sheet tab > Delete",
    "combine_sheets": "Manually copying rows from each sheet",
    "insert_row": "Right-click row header > Insert",
    "insert_column": "Right-click column header > Insert",
    "data_validation": "Data > Data Validation",
    "protect_sheet": "Review > Protect Sheet",
    "export_to_pdf": "File > Export > Create PDF/XPS",
    "split_column": "Data > Text to Columns",
    "merge_columns": "Formula (CONCAT) across columns",
    "fetch_live_data": "Data > Get Data (external source)",
    "run_excel_code": "Custom automation (no direct menu equivalent)",
    "screenshot_active_window": "(observing the screen)",
    "click_at": "Mouse click",
    "type_text": "Keyboard input",
    "press_key": "Keyboard shortcut",
}


def reveal_workflow(structured_steps: list) -> list:
    """Returns an ordered list of {step, native_feature, detail} for
    every action in the log - the on-demand replay view."""
    revealed = []
    step_num = 1
    for step in structured_steps:
        if step.get("type") != "action":
            continue
        tool_name = step["tool_name"]
        revealed.append({
            "step": step_num,
            "native_feature": NATIVE_FEATURE_NAMES.get(tool_name, tool_name),
            "tool_name": tool_name,
            "execution_layer": step.get("execution_layer"),
            "succeeded": step.get("status") == "success",
        })
        step_num += 1
    return revealed


def progress_snapshot(structured_steps: list, is_done: bool) -> dict:
    """A compact 'what is the AI doing right now' view - Current task /
    Completed actions / Decision explanations, per the Intelligent
    Progress Visualization capability."""
    completed = [s for s in structured_steps if s.get("type") == "action" and s.get("status") == "success"]
    reasoning = [s["text"] for s in structured_steps if s.get("type") == "reasoning"]

    current_task = reasoning[-1] if reasoning and not is_done else ("Done" if is_done else "Starting up...")

    return {
        "current_task": current_task,
        "completed_action_count": len(completed),
        "completed_actions": [
            {"tool_name": s["tool_name"], "execution_layer": s.get("execution_layer")} for s in completed
        ],
        "decision_explanations": reasoning,
        "is_done": is_done,
    }
