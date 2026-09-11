"""Specialist wrappers for registered Excel skills.

Subagents do not open a second model session and do not bypass the skill
library.  They give callers a narrow, observable way to delegate a validated
subtask to a data, design, review, or analysis specialist.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import monotonic
from typing import Any

import config
from skills.base import SKILL_REGISTRY
from skills.registry import has_skill, run_skill


@dataclass
class SubAgentResult:
    agent_type: str
    success: bool
    actions_taken: list[dict[str, Any]] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BaseSubAgent:
    agent_type = "base"
    allowed_categories: set[str] = set()

    def _is_allowed_skill(self, tool_name: str) -> bool:
        entry = SKILL_REGISTRY.get(tool_name)
        return bool(entry and entry.get("category") in self.allowed_categories)

    def execute(self, subtask: dict[str, Any], context: dict[str, Any] | None = None) -> SubAgentResult:
        started = monotonic()
        tool_name = str(subtask.get("tool_hint") or "")
        tool_input = dict((context or {}).get("tool_input") or subtask.get("tool_input") or {})

        if not has_skill(tool_name):
            return SubAgentResult(
                agent_type=self.agent_type,
                success=False,
                error=f"'{tool_name}' is not a registered Excel skill.",
                duration_seconds=monotonic() - started,
            )
        if not self._is_allowed_skill(tool_name):
            return SubAgentResult(
                agent_type=self.agent_type,
                success=False,
                error=f"'{tool_name}' is outside the {self.agent_type} specialist's allowed skill categories.",
                duration_seconds=monotonic() - started,
            )

        try:
            result = run_skill(tool_name, **tool_input)
        except Exception as exc:
            return SubAgentResult(
                agent_type=self.agent_type,
                success=False,
                actions_taken=[{"tool_name": tool_name, "input": tool_input}],
                error=str(exc),
                duration_seconds=monotonic() - started,
            )

        verified = isinstance(result, dict) and result.get("verified") is True
        return SubAgentResult(
            agent_type=self.agent_type,
            success=verified,
            actions_taken=[{"tool_name": tool_name, "input": tool_input, "result": result}],
            output=result if isinstance(result, dict) else {"result": result},
            error=None if verified else "The skill completed without verified evidence.",
            duration_seconds=monotonic() - started,
        )


class DataAgent(BaseSubAgent):
    agent_type = "data"
    allowed_categories = {"write", "etl", "transform", "data"}


class DesignerAgent(BaseSubAgent):
    agent_type = "designer"
    allowed_categories = {"format", "dashboard", "chart"}


class ReviewerAgent(BaseSubAgent):
    agent_type = "reviewer"
    allowed_categories = {"read", "inspection", "general"}


class AnalystAgent(BaseSubAgent):
    agent_type = "analyst"
    allowed_categories = {"analysis", "financial", "etl", "transform", "read", "inspection"}


SUBAGENTS = {
    "data": DataAgent,
    "designer": DesignerAgent,
    "reviewer": ReviewerAgent,
    "analyst": AnalystAgent,
}


def dispatch_subagent(
    agent_type: str,
    subtask: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> SubAgentResult:
    """Run one subtask through the named specialist."""
    if not config.ENABLE_SUBAGENTS:
        return SubAgentResult(
            agent_type=agent_type,
            success=False,
            error="Subagents are disabled by server configuration.",
        )
    agent_cls = SUBAGENTS.get(agent_type)
    if agent_cls is None:
        return SubAgentResult(
            agent_type=agent_type,
            success=False,
            error=f"Unknown specialist '{agent_type}'. Available: {', '.join(SUBAGENTS)}.",
        )
    return agent_cls().execute(subtask, context)
