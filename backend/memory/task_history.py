"""Per-user task outcomes used for planning and reusable-pattern learning."""

from __future__ import annotations

import time
from uuid import uuid4

from memory._store import read_records, write_records


def log_task_start(instruction: str, plan: list | None = None, *, user_id: int | None = None) -> str:
    history = read_records("task_history", user_id)
    task_id = f"task_{uuid4().hex}"
    history.append({
        "id": task_id, "instruction": instruction, "plan": plan or [], "actions": [],
        "outcome": None, "success": None, "duration_seconds": None,
        "sheet_count": None, "sheets_created": [], "start_time": time.time(),
        "end_time": None, "error": None,
    })
    write_records("task_history", user_id, history)
    return task_id


def log_task_action(task_id: str, action_name: str, action_input: dict, result: dict, *, user_id: int | None = None) -> None:
    history = read_records("task_history", user_id)
    for entry in history:
        if entry.get("id") == task_id:
            entry["actions"].append({"name": action_name, "input": action_input, "result": result, "timestamp": time.time()})
            break
    write_records("task_history", user_id, history)


def log_task_complete(task_id: str, outcome: str, success: bool, sheet_count: int | None = None, sheets_created: list | None = None, error: str | None = None, *, user_id: int | None = None) -> None:
    history = read_records("task_history", user_id)
    for entry in history:
        if entry.get("id") == task_id:
            entry.update({"outcome": outcome, "success": bool(success), "end_time": time.time(), "sheet_count": sheet_count, "sheets_created": sheets_created or [], "error": error})
            entry["duration_seconds"] = entry["end_time"] - entry["start_time"]
            break
    write_records("task_history", user_id, history)


def get_successful_tasks(max_results: int = 10, *, user_id: int | None = None) -> list[dict]:
    successful = [entry for entry in read_records("task_history", user_id) if entry.get("success") is True]
    return sorted(successful, key=lambda entry: entry.get("end_time") or 0, reverse=True)[:max_results]


def get_similar_tasks(instruction: str, max_results: int = 5, *, user_id: int | None = None) -> list[dict]:
    words = set(instruction.lower().split())
    scored = []
    for entry in read_records("task_history", user_id):
        overlap = len(words & set(str(entry.get("instruction", "")).lower().split()))
        if overlap:
            scored.append((overlap, entry))
    return [entry for _, entry in sorted(scored, key=lambda item: item[0], reverse=True)[:max_results]]


def get_history_count(*, user_id: int | None = None) -> int:
    return len(read_records("task_history", user_id))


def get_stats(*, user_id: int | None = None) -> dict:
    history = read_records("task_history", user_id)
    successful = sum(entry.get("success") is True for entry in history)
    failed = sum(entry.get("success") is False for entry in history)
    durations = [entry["duration_seconds"] for entry in history if entry.get("duration_seconds") is not None]
    return {
        "total_tasks": len(history), "successful": successful, "failed": failed,
        "success_rate": successful / max(len(history), 1),
        "avg_duration_seconds": sum(durations) / max(len(durations), 1),
    }
