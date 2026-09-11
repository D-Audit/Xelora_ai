"""Task planning for multi-step Excel requests.

The planner is deliberately local and side-effect free.  It provides the
agent with an ordered checklist before execution without opening a second AI
chat window or altering the workbook.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from agent.intent_inference import infer_implicit_steps
from memory.task_history import get_similar_tasks


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class SubTask:
    id: str
    description: str
    tool_hint: str = ""
    target_sheet: str = "active"
    cell_range: Optional[str] = None
    depends_on: list[str] = field(default_factory=list)
    status: str = TaskStatus.PENDING.value
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2
    is_critical: bool = True
    success_criteria: str = ""
    is_implicit: bool = False
    confidence: Optional[float] = None


@dataclass
class TaskPlan:
    task_id: str
    instruction: str
    subtasks: list[SubTask]
    estimated_steps: int
    workbook_state: Optional[dict[str, Any]] = None


def _active_sheet(workbook_info: Optional[dict[str, Any]]) -> str:
    if isinstance(workbook_info, dict):
        return str(workbook_info.get("active_sheet") or "active")
    return "active"


def _subtask_from_mapping(item: dict[str, Any], number: int, target_sheet: str) -> SubTask:
    return SubTask(
        id=f"subtask_{number}",
        description=str(item.get("description") or "Complete the requested workbook step"),
        tool_hint=str(item.get("tool_hint") or ""),
        target_sheet=str(item.get("target_sheet") or target_sheet),
        cell_range=item.get("cell_range"),
        is_critical=bool(item.get("is_critical", True)),
        success_criteria=str(item.get("success_criteria") or ""),
        is_implicit=bool(item.get("is_implicit", False)),
        confidence=item.get("confidence"),
    )


def build_plan(
    instruction: str,
    workbook_info: Optional[dict[str, Any]] = None,
    *,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Return a safe, ordered execution checklist.

    This function does not perform workbook actions and never calls an LLM.
    The primary agent remains responsible for selecting valid registered skills
    and for asking for confirmation before workbook edits.
    """
    if not isinstance(instruction, str) or not instruction.strip():
        return {"plan": [], "error": "instruction must be a non-empty string"}

    target_sheet = _active_sheet(workbook_info)
    subtasks: list[SubTask] = [
        SubTask(
            id="subtask_1",
            description="Inspect the active workbook and confirm the source data and target sheet.",
            tool_hint="inspect_workbook",
            target_sheet=target_sheet,
            is_critical=True,
            success_criteria="The workbook structure and destination are known before any edit.",
        )
    ]

    # Intent inference supplies optional, domain-specific checklist items. It
    # must never silently issue edits; the model verifies each against the
    # user request and the live workbook before execution.
    for inferred in infer_implicit_steps(instruction):
        subtask = _subtask_from_mapping(inferred, len(subtasks) + 1, target_sheet)
        subtask.depends_on = [subtasks[-1].id]
        subtasks.append(subtask)

    subtasks.append(
        SubTask(
            id=f"subtask_{len(subtasks) + 1}",
            description="Perform the explicitly requested workbook changes using registered Excel skills.",
            tool_hint="agent_selected_skill",
            target_sheet=target_sheet,
            depends_on=[subtasks[-1].id],
            is_critical=True,
            success_criteria="The requested change is complete and each write is verified.",
        )
    )
    subtasks.append(
        SubTask(
            id=f"subtask_{len(subtasks) + 1}",
            description="Verify the resulting workbook state and report any unresolved issue.",
            tool_hint="inspect_workbook",
            target_sheet=target_sheet,
            depends_on=[subtasks[-1].id],
            is_critical=True,
            success_criteria="The result is verified from the workbook, not merely assumed.",
        )
    )

    similar_tasks = get_similar_tasks(instruction, user_id=user_id, max_results=3)
    return {
        "task_id": f"plan_{uuid4().hex}",
        "instruction": instruction,
        "plan": [asdict(subtask) for subtask in subtasks],
        "estimated_steps": len(subtasks),
        "workbook_state": workbook_info,
        "similar_task_count": len(similar_tasks),
    }


def plan_context(plan: dict[str, Any]) -> str:
    """Render a compact checklist for the primary agent's system prompt."""
    steps = plan.get("plan", []) if isinstance(plan, dict) else []
    if not steps:
        return ""
    lines = ["\n\nPRE-FLIGHT EXECUTION CHECKLIST (advisory; verify against the live workbook):"]
    for step in steps:
        lines.append(f"- {step['id']}: {step['description']}")
    return "\n".join(lines)


def get_next_subtask(plan: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Return the next pending subtask whose dependencies are complete."""
    steps = plan.get("plan", [])
    completed = {step["id"] for step in steps if step.get("status") in {"completed", "skipped"}}
    return next(
        (
            step
            for step in steps
            if step.get("status") == "pending"
            and all(dependency in completed for dependency in step.get("depends_on", []))
        ),
        None,
    )


def mark_subtask_done(plan: dict[str, Any], subtask_id: str, result: dict[str, Any]) -> None:
    for step in plan.get("plan", []):
        if step.get("id") == subtask_id:
            step.update({"status": "completed", "result": result, "error": None})
            return


def mark_subtask_failed(plan: dict[str, Any], subtask_id: str, error: str) -> None:
    for step in plan.get("plan", []):
        if step.get("id") == subtask_id:
            retries = int(step.get("retry_count", 0)) + 1
            step["retry_count"] = retries
            step["error"] = error
            step["status"] = "pending" if retries <= int(step.get("max_retries", 2)) else "failed"
            return
