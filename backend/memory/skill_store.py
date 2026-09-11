"""Per-user reusable skill patterns learned from verified task outcomes."""

from __future__ import annotations

import time
from uuid import uuid4

from memory._store import read_records, write_records


def add_skill(name: str, description: str, trigger_conditions: list, action_sequence: list, tags: list | None = None, *, user_id: int | None = None) -> str:
    skills = read_records("skills", user_id)
    sequence = [str(action) for action in action_sequence]
    for skill in skills:
        if skill.get("name") == name and skill.get("action_sequence") == sequence:
            return str(skill["id"])
    skill_id = f"skill_{uuid4().hex}"
    skills.append({
        "id": skill_id, "name": name, "description": description,
        "trigger_conditions": [str(condition) for condition in trigger_conditions],
        "action_sequence": sequence, "tags": [str(tag) for tag in tags or []],
        "success_count": 0, "failure_count": 0, "version": 1,
        "created_at": time.time(), "last_used": None,
    })
    write_records("skills", user_id, skills)
    return skill_id


def record_skill_usage(skill_id: str, success: bool, *, user_id: int | None = None) -> None:
    skills = read_records("skills", user_id)
    for skill in skills:
        if skill.get("id") == skill_id:
            key = "success_count" if success else "failure_count"
            skill[key] = int(skill.get(key, 0)) + 1
            skill["last_used"] = time.time()
            break
    write_records("skills", user_id, skills)


def find_matching_skills(instruction: str, max_results: int = 3, *, user_id: int | None = None) -> list[dict]:
    words = set(instruction.lower().split())
    scored = []
    for skill in read_records("skills", user_id):
        score = sum(len(words & set(str(condition).lower().split())) for condition in skill.get("trigger_conditions", []))
        score += sum(2 for tag in skill.get("tags", []) if str(tag).lower() in instruction.lower())
        total = int(skill.get("success_count", 0)) + int(skill.get("failure_count", 0))
        if total:
            score *= 1 + int(skill.get("success_count", 0)) / total
        if score:
            scored.append((score, skill))
    return [skill for _, skill in sorted(scored, key=lambda item: item[0], reverse=True)[:max_results]]


def get_all_skills(*, user_id: int | None = None) -> list[dict]:
    return read_records("skills", user_id)


def get_skill_by_id(skill_id: str, *, user_id: int | None = None) -> dict | None:
    return next((skill for skill in read_records("skills", user_id) if skill.get("id") == skill_id), None)
