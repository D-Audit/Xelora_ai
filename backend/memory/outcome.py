"""Record what a finished task teaches Xelora (history, chat memory, skills).

Shared by the server's task worker and the desktop local agent, so a task
learns the same way wherever it ran.
"""
from __future__ import annotations

import json

import config

# Tool inputs/results can be whole sheets of data; memory keeps a preview.
_MAX_STORED_CHARS = 1500


def _compact(value):
    try:
        text = json.dumps(value, default=str)
    except (TypeError, ValueError):
        text = str(value)
    if len(text) <= _MAX_STORED_CHARS:
        return value
    return {"truncated": True, "preview": text[:_MAX_STORED_CHARS]}


def _for_memory(actions: list[dict]) -> list[dict]:
    return [{**action, "input": _compact(action.get("input", {})), "result": _compact(action.get("result", {}))}
            for action in actions]


def task_actions(task) -> list[dict]:
    """Normalize the core executor's action steps for reports and memory."""
    actions = []
    for step in task.structured_steps:
        if step.get("type") != "action":
            continue
        result = step.get("result")
        actions.append({
            "name": step.get("tool_name", "unknown"),
            "input": step.get("input", step.get("tool_input", {})) or {},
            "result": result if isinstance(result, dict) else {"result": result},
            "status": step.get("status"),
        })
    return actions


def start_task_history(task, user_id) -> str | None:
    if not config.ENABLE_MEMORY_STORAGE:
        return None
    from memory.task_history import log_task_start
    return log_task_start(task.instruction, user_id=user_id)


def record_task_outcome(task, user_id, history_task_id: str | None = None) -> None:
    """Store the run in task history and chat memory, and extract reusable skills."""
    if not config.ENABLE_MEMORY_STORAGE:
        return
    from agent.core import get_task_completion_status
    from memory.chat_memory import store_conversation
    from memory.task_history import log_task_actions, log_task_complete

    status = get_task_completion_status(task)
    success = status == "completed"
    actions = _for_memory(task_actions(task))
    if history_task_id is None:
        history_task_id = start_task_history(task, user_id)
    if history_task_id:
        if actions:
            log_task_actions(history_task_id, actions, user_id=user_id)
        log_task_complete(history_task_id, task.final_response or status, success,
                          error=None if success else task.final_response, user_id=user_id)
    store_conversation(user_id, task.instruction, actions, task.final_response or status, success)
    if config.ENABLE_SKILL_EXTRACTION:
        from agent.skills import extract_skills_from_task
        extract_skills_from_task(task.instruction, actions, success, user_id=user_id)
