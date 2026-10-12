"""Per-user layered agent memory for completed workbook tasks."""

from __future__ import annotations

import time
from uuid import uuid4

from memory._store import keywords, read_records, update_records


def store_conversation(user_id: int | None, instruction: str, actions: list, outcome: str, success: bool) -> str:
    entry = {
        "id": f"conv_{uuid4().hex}", "level": "L0", "timestamp": time.time(),
        "instruction": instruction, "actions": actions, "outcome": outcome,
        "success": bool(success), "atoms": [], "scenario": None,
    }
    update_records("chat_memory", user_id, lambda memories: memories.append(entry))
    return entry["id"]


def _update_entry(user_id: int | None, conversation_id: str, values: dict) -> None:
    def mutate(memories):
        for memory in memories:
            if memory.get("id") == conversation_id:
                memory.update(values)
                break
    update_records("chat_memory", user_id, mutate)


def extract_atoms(user_id: int | None, conversation_id: str, facts: list[str]) -> None:
    _update_entry(user_id, conversation_id, {"atoms": [str(fact) for fact in facts], "level": "L1"})


def assign_scenario(user_id: int | None, conversation_id: str, scenario: str) -> None:
    _update_entry(user_id, conversation_id, {"scenario": str(scenario), "level": "L2"})


def get_relevant_memories(user_id: int | None, instruction: str, max_results: int = 5) -> list[dict]:
    words = keywords(instruction)
    scored = []
    for memory in read_records("chat_memory", user_id):
        score = len(words & keywords(memory.get("instruction", ""))) * 2
        score += sum(len(words & keywords(atom)) for atom in memory.get("atoms", []))
        score += len(words & keywords(memory.get("scenario") or ""))
        if not score:
            continue  # success alone does not make an unrelated task relevant
        score += int(bool(memory.get("success")))
        scored.append((score, memory.get("timestamp") or 0, memory))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [memory for _, _, memory in scored[:max_results]]


def get_user_profile(user_id: int | None) -> dict:
    memories = read_records("chat_memory", user_id)
    preferences = {atom for memory in memories for atom in memory.get("atoms", [])}
    scenarios: dict[str, int] = {}
    for memory in memories:
        if memory.get("scenario"):
            scenario = str(memory["scenario"])
            scenarios[scenario] = scenarios.get(scenario, 0) + 1
    successes = sum(bool(memory.get("success")) for memory in memories)
    return {
        "total_tasks": len(memories), "success_rate": successes / max(len(memories), 1),
        "top_scenarios": sorted(scenarios.items(), key=lambda item: item[1], reverse=True)[:5],
        "preferences": sorted(preferences),
    }


def get_memory_count(user_id: int | None) -> int:
    return len(read_records("chat_memory", user_id))
