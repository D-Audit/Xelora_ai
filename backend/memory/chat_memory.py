"""Per-user layered agent memory for completed workbook tasks."""

from __future__ import annotations

import time
from uuid import uuid4

from memory._store import read_records, write_records


def store_conversation(user_id: int | None, instruction: str, actions: list, outcome: str, success: bool) -> str:
    memories = read_records("chat_memory", user_id)
    entry = {
        "id": f"conv_{uuid4().hex}", "level": "L0", "timestamp": time.time(),
        "instruction": instruction, "actions": actions, "outcome": outcome,
        "success": bool(success), "atoms": [], "scenario": None,
    }
    memories.append(entry)
    write_records("chat_memory", user_id, memories)
    return entry["id"]


def extract_atoms(user_id: int | None, conversation_id: str, facts: list[str]) -> None:
    memories = read_records("chat_memory", user_id)
    for memory in memories:
        if memory.get("id") == conversation_id:
            memory.update({"atoms": [str(fact) for fact in facts], "level": "L1"})
            break
    write_records("chat_memory", user_id, memories)


def assign_scenario(user_id: int | None, conversation_id: str, scenario: str) -> None:
    memories = read_records("chat_memory", user_id)
    for memory in memories:
        if memory.get("id") == conversation_id:
            memory.update({"scenario": str(scenario), "level": "L2"})
            break
    write_records("chat_memory", user_id, memories)


def get_relevant_memories(user_id: int | None, instruction: str, max_results: int = 5) -> list[dict]:
    words = set(instruction.lower().split())
    scored = []
    for memory in read_records("chat_memory", user_id):
        score = len(words & set(str(memory.get("instruction", "")).lower().split())) * 2
        score += sum(len(words & set(str(atom).lower().split())) for atom in memory.get("atoms", []))
        score += len(words & set(str(memory.get("scenario") or "").lower().split()))
        score += int(bool(memory.get("success")))
        if score:
            scored.append((score, memory))
    return [memory for _, memory in sorted(scored, key=lambda item: item[0], reverse=True)[:max_results]]


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
