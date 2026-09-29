"""Backend action decisions for the Xelora task loop.

This is deliberately independent of prompts: every tool call the model makes
passes through ``decide_action`` before dispatch, and the decision is based on
registry metadata and live configuration rather than on a hand-maintained
list or on anything the model says.

Decision order (first match wins):
1. Unknown tool                      -> blocked
2. Disabled by server configuration  -> blocked (clear reason)
3. User files without a JWT session  -> blocked
4. Invalid arguments for the schema  -> blocked (model can correct and retry)
5. Planning-only mode and not a read -> held for the user's confirmation
6. Otherwise                         -> allowed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.tool_registry import ToolRisk, ToolSpec, availability, validate_tool_input


@dataclass(frozen=True)
class ActionDecision:
    allowed: bool
    needs_user: bool = False
    reason: str = ""
    status: str = "allowed"
    normalized_input: dict[str, Any] | None = field(default=None, compare=False)


def decide_action(
    spec: ToolSpec | None,
    *,
    planning_only: bool,
    tool_input: Any = None,
    file_access_authorized: bool = True,
) -> ActionDecision:
    """Decide whether a known action may execute in the current task mode."""
    if spec is None:
        return ActionDecision(False, reason="Unknown tools are never executable.", status="tool_not_authorized")
    enabled, why = availability(spec)
    if not enabled:
        return ActionDecision(False, reason=why, status="disabled")
    if spec.execution_layer in {"files", "workspace_import"} and not file_access_authorized:
        return ActionDecision(
            False, reason="User file tools require a signed-in (JWT-authenticated) Xelora session.",
            status="authenticated_file_access_required",
        )
    normalized, error = validate_tool_input(spec, tool_input)
    if error:
        return ActionDecision(False, reason=error, status="invalid_arguments")
    if planning_only and spec.risk is not ToolRisk.READ:
        return ActionDecision(
            False,
            needs_user=True,
            reason="This action changes Excel, files, or the desktop, or executes code, and requires the user's confirmation.",
            status="approval_required",
        )
    return ActionDecision(True, normalized_input=normalized)
