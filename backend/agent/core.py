"""
agent/core.py
The brain of the system. Goal -> Planning -> Execution -> Verification
-> Correction -> Completion, dispatching each action to one of three
layers: skill library, code generation, or visual fallback.
"""

import concurrent.futures
import json
import os
import re

import config
from skills.registry import has_skill, run_skill
from codegen.executor import run_generated_code
from agent import providers
from agent.prompts import build_system_prompt

VISUAL_TOOL_NAMES = {"take_screenshot", "parse_screen", "click", "double_click", "type_text", "press_key", "hotkey", "scroll", "activate_ribbon_tab", "go_to_range", "paste_table", "fill_formula_down", "format_currency", "format_bold", "autofit_columns", "create_clustered_column_chart"}
READ_ONLY_TOOL_NAMES = {"take_screenshot", "parse_screen"}

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKILL_TIMEOUT_SECONDS = 15


def _run_skill_with_timeout(tool_name: str, tool_input: dict, timeout: int = SKILL_TIMEOUT_SECONDS):
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = ex.submit(run_skill, tool_name, **tool_input)
    timed_out = False
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        timed_out = True
        future.cancel()

        from skills.excel_shared import force_restart_excel_and_reopen
        try:
            force_restart_excel_and_reopen()
            recovery_note = "Excel was automatically restarted to clear the hang - everything written before this point is safely saved."
        except Exception as recovery_error:
            recovery_note = f"Attempted auto-recovery but it also failed: {recovery_error}"

        return {
            "error": f"'{tool_name}' timed out after {timeout}s. Excel appeared to be "
                     f"permanently blocked (a hung dynamic-array/spilling formula is the most "
                     f"common cause). {recovery_note}",
            "verified": False,
            "status": "timeout_recovered",
        }
    finally:
        ex.shutdown(wait=not timed_out, cancel_futures=True)


class AgentTask:
    def __init__(self, instruction: str, user_id: int = None, workbook_name: str = None):
        self.instruction = instruction
        self.user_id = user_id
        self.workbook_name = workbook_name
        self.messages = [{"role": "user", "content": instruction}]
        self.is_paused = False
        self.is_done = False
        self.progress_log = []
        self.structured_steps = []
        self.retry_counts = {}
        self.gemini_model_index = 0
        self.final_response = None
        self.chat_transcript = [{"role": "user", "text": instruction}]
        self.excel_version_info = None  # filled in once at task start, see run_task()
        self.text_only_action_retry_used = False
        self.final_verification_requested = False
        self.successful_visual_actions = set()
        self.successful_action_signatures = set()
        self.visual_checkpoints = []
        self.visual_checkpoint_unavailable = False
        # Direct imperative requests (for example, "click the Insert tab")
        # already state the action the user wants.  Start those tasks in
        # execution mode; descriptive or exploratory requests still begin
        # with the existing plan-and-confirm safeguard.
        self.awaiting_approval = not _is_direct_action_instruction(instruction)
        # True when the very first message was already an imperative
        # ("click the Insert tab"), so execution was approved from the start.
        # Used by run_task to stop visual-mode tasks after the one requested
        # action succeeds. Tasks that began in planning mode (multi-step plan
        # awaiting approval) keep this False, so once approved they still run
        # the whole plan.
        self.started_in_execution_mode = not self.awaiting_approval

    def pause(self):
        self.is_paused = True

    def resume(self, correction: str = None):
        self.is_paused = False
        self.is_done = False
        self.final_response = None
        if correction:
            # A bare confirmation approves the plan already proposed; it is
            # not a replacement task. Keeping the original instruction is
            # important for deterministic execution and for an accurate task
            # record. A substantive follow-up remains a new active request.
            is_plan_confirmation = self.awaiting_approval and _is_explicit_approval(correction)
            is_plan_acknowledgement = self.awaiting_approval and _is_plan_acknowledgement(correction)
            # A follow-up such as "click the Insert tab" is an unambiguous
            # instruction to carry out the proposed action.  Previously only
            # a handful of exact words ("confirm", "yes", etc.) unlocked a
            # conversation, so retrying a command repeatedly replayed the
            # planning-only refusal from the existing chat.
            if self.awaiting_approval and (
                is_plan_confirmation or _is_direct_action_instruction(correction)
            ):
                self.awaiting_approval = False
            if is_plan_acknowledgement:
                # "Continue" is a common conversational acknowledgement of a
                # proposed plan, not a new Excel request.  Treating it as a
                # replacement instruction loses the original workbook task;
                # the next model turn then has no idea what it was supposed
                # to execute after the user eventually confirms.
                self.messages.append({"role": "user", "content": correction})
            elif is_plan_confirmation:
                # Make the handoff unambiguous for the execution model.  The
                # short word "Confirm" alone is easy for a provider to treat
                # as ordinary chat and reply to without taking a tool action.
                # Repeating the original instruction here preserves the plan
                # in context and explicitly directs it to begin working.
                self.messages.append({
                    "role": "user",
                    "content": (
                        "The user explicitly approved the proposed plan. Execute it now. "
                        "Do not ask for confirmation again and do not ask what to do next. "
                        "Use Excel tools to complete this original request:\n\n"
                        f"{self.instruction}"
                    ),
                })
            else:
                # A substantive message is a new request in the same visible
                # conversation. Keep the transcript for the user, but reset
                # model/tool history so a previous failure cannot poison the
                # next task (the old "cache" behaviour).
                self.instruction = correction
                self.awaiting_approval = not _is_direct_action_instruction(correction)
                self.started_in_execution_mode = not self.awaiting_approval
                self.messages = [{"role": "user", "content": correction}]
            # These values describe a completed attempt.  They must not leak
            # into a corrected run, otherwise a previous visual/API failure
            # can make the next response look failed even after it succeeds.
            self.structured_steps = []
            self.progress_log = []
            self.retry_counts = {}
            self.text_only_action_retry_used = False
            self.final_verification_requested = False
            self.successful_visual_actions = set()
            self.successful_action_signatures = set()
            self.visual_checkpoints = []
            self.visual_checkpoint_unavailable = False
            self.chat_transcript.append({"role": "user", "text": correction})

    def log_step(self, message: str):
        self.progress_log.append(message)
        print(message)


def _is_explicit_approval(message: str) -> bool:
    normalized = " ".join(message.lower().strip().split())
    return normalized in {
        "confirm", "confirmed", "approve", "approved", "yes", "yes proceed",
        "yes, proceed", "go ahead", "go ahead and do it", "proceed", "do it",
    }


def _is_plan_acknowledgement(message: str) -> bool:
    """Return True for a non-approval acknowledgement of the current plan.

    These messages should keep the proposed plan and request intact while
    Xelora asks for the explicit approval required before changing Excel.
    """
    normalized = " ".join(message.lower().strip().split())
    return normalized in {
        "continue", "continue please", "please continue", "ok", "okay",
        "alright", "sure", "i understand", "got it",
    }


def _is_direct_action_instruction(message: str) -> bool:
    """Recognize a new imperative as approval to execute an existing plan.

    This is intentionally limited to common imperative verbs so ordinary
    clarifications (for example, "the workbook is open") still remain in
    planning mode until the user explicitly asks the agent to act.
    """
    normalized = " ".join(message.lower().strip().split())
    return normalized.startswith((
        "click ", "double click ", "open ", "close ", "insert ", "add ",
        "delete ", "remove ", "update ", "change ", "edit ", "write ",
        "create ", "format ", "sort ", "filter ", "run ", "apply ",
        "select ", "type ", "press ", "go to ", "make ",
    ))


def _is_one_step_navigation_request(message: str) -> bool:
    """Whether a request can truthfully finish after one UI interaction.

    This is deliberately about the *shape* of the request, not a list of
    Excel commands. It prevents a completed navigation request from invoking
    Gemini again, while keeping multi-step workbook work (data entry, charts,
    formulas, formatting) in the normal planner/executor loop.
    """
    normalized = " ".join(message.lower().strip().split())
    if not normalized.startswith(("click ", "open ", "go to ", "select ", "press ")):
        return False
    multi_step_markers = (
        " then ", " and ", " after ", "create ", "add ",
        "write ", "type ", "enter ", "format ", "chart", "formula",
        "table", "data", "save", "delete", "remove", "change", "edit",
    )
    return not any(marker in normalized for marker in multi_step_markers)


def _standard_ribbon_tab_shortcut(instruction: str) -> tuple[str, list[str]] | None:
    """Resolve only an unambiguous *navigation-only* ribbon request locally.

    This is an execution policy, not a replacement for Gemini's planning:
    workbook creation, data entry, formulas, charts, and formatting still go
    through Gemini.  Excel's top-level tabs have stable keyboard access keys,
    so sending a CPU-heavy visual parser there is unnecessary and fragile.
    """
    if not _is_one_step_navigation_request(instruction):
        return None
    normalized = " ".join(instruction.lower().strip().split())
    match = re.fullmatch(
        r"(?:please )?(?:click|open|go to|select) (?:the )?([a-z]+(?: [a-z]+)?) tab(?: in excel)?[.!]?",
        normalized,
    )
    if not match:
        return None
    tab_keys = {
        "home": ["alt", "h"],
        "insert": ["alt", "n"],
        "page layout": ["alt", "p"],
        "formulas": ["alt", "m"],
        "data": ["alt", "a"],
        "review": ["alt", "r"],
        "view": ["alt", "w"],
    }
    tab = match.group(1)
    return (tab, tab_keys[tab]) if tab in tab_keys else None


def _standard_go_to_range(instruction: str) -> str | None:
    """Resolve direct Name Box / Go To requests without visual parsing."""
    normalized = " ".join(instruction.strip().split())
    match = re.fullmatch(
        r"(?:please )?(?:go to|select) (?:cell |range |the cell |the range )?([^.!?]+?)(?: in excel)?[.!?]?",
        normalized,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    reference = match.group(1).strip()
    # A1 references and ordinary defined names are safe to send to Excel's
    # Go To dialog. Do not turn arbitrary natural-language text into keys.
    a1_reference = r"(?:(?:'[^']+'|[A-Za-z0-9_ ]+)!?)?\$?[A-Za-z]{1,3}\$?\d+(?::\$?[A-Za-z]{1,3}\$?\d+)?"
    defined_name = r"[A-Za-z_][A-Za-z0-9_.]*"
    if re.fullmatch(a1_reference, reference) or re.fullmatch(defined_name, reference):
        return reference
    return None


def _visual_only_requires_structured_workbook_automation(instruction: str) -> bool:
    """Whether the request needs Excel's object model rather than keystrokes.

    Visual-only mode is deliberately a narrow accessibility fallback.  It can
    safely navigate or perform a small, directly observable command, but it
    cannot reliably create/rename sheets, build a dashboard, or inspect the
    resulting formulas and chart objects.  Letting an LLM try those jobs with
    raw keystrokes caused the exact failure in the reported run: sheet names
    were typed into cells and the task sounded complete despite no workbook
    structure ever having been created.
    """
    normalized = " ".join(instruction.lower().split())
    structured_markers = (
        "worksheet", "worksheets", "sheet", "sheets", "dashboard", "pivot",
        "formula", "formulas", "table", "tables", "report", "chart", "charts",
        "sample data", "dataset", "data set", "transaction", "transactions",
        "summary", "summaries", "rename", "multiple tabs", "multiple sheets",
    )
    return any(marker in normalized for marker in structured_markers)


def _finish_visual_only_routing_block(task: AgentTask) -> AgentTask:
    """Finish without sending any input when visual-only mode is insufficient."""
    task.is_done = True
    task.final_response = (
        "INCOMPLETE: This request needs structured Excel automation (such as worksheets, "
        "formulas, charts, or a dashboard), but VISUAL_ONLY_MODE is enabled. "
        "No workbook changes were sent because keyboard-only automation cannot safely "
        "create and verify this work. Set VISUAL_ONLY_MODE=false and keep "
        "ENABLE_CODEGEN_LAYER=true, restart the backend, then retry the same task."
    )
    task.structured_steps.append({
        "type": "routing",
        "mode": "visual_only_blocked",
        "verified": True,
        "reason": "Structured workbook automation requires Excel skills or code generation.",
    })
    task.log_step(task.final_response)
    task.chat_transcript.append({"role": "assistant", "text": task.final_response})
    return task


def dispatch_action(tool_name: str, tool_input: dict):
    if config.VISUAL_ONLY_MODE:
        if tool_name not in VISUAL_TOOL_NAMES:
            return {"error": "VISUAL_ONLY_MODE blocks Excel API and code-generation tools.", "verified": False}, "blocked", None
        if tool_name == "hotkey":
            keys = [str(key).lower() for key in tool_input.get("keys", [])]
            if keys in (["ctrl", "g"], ["f5"]):
                return {
                    "error": "Use go_to_range with a valid reference; raw Go To shortcuts can leave an unfinished dialog.",
                    "verified": False,
                }, "blocked", None
        from vision import ui_control
        return getattr(ui_control, tool_name)(**tool_input), "visual", None

    if has_skill(tool_name):
        return _run_skill_with_timeout(tool_name, tool_input), "skill", None

    if tool_name == "run_excel_code":
        if not config.ENABLE_CODEGEN_LAYER:
            return {"error": "The code-generation layer is disabled by configuration.", "verified": False}, "blocked", None
        code = tool_input.get("code", "")
        result = run_generated_code(code, project_root=PROJECT_ROOT)
        return result, "codegen", code

    if tool_name in VISUAL_TOOL_NAMES:
        if not config.ENABLE_VISUAL_FALLBACK:
            return {"error": "Visual fallback is disabled (ENABLE_VISUAL_FALLBACK=false).",
                    "verified": False}, "visual", None
        from vision import ui_control
        func = getattr(ui_control, tool_name)
        return func(**tool_input), "visual", None

    return {"error": f"Unknown tool '{tool_name}'", "verified": False}, "unknown", None


def _log_action_to_db(db, task_id, tool_name, tool_input, execution_layer, generated_code, result, status):
    if db is None:
        return
    from models import ActionLog
    entry = ActionLog(
        task_id=task_id,
        action_name=tool_name,
        execution_layer=execution_layer,
        input_params=json.dumps(tool_input, default=str),
        generated_code=generated_code,
        result=json.dumps(result, default=str),
        verified=bool(result.get("verified", False)) if isinstance(result, dict) else False,
        verification_note=result.get("verification_note") if isinstance(result, dict) else None,
        status=status,
    )
    db.add(entry)
    db.commit()


def _detect_excel_version_once(task: AgentTask):
    """
    Runs get_excel_version automatically at the very start of a task
    (not left to the AI to remember to call), so version-awareness is
    guaranteed rather than dependent on the model choosing to check.
    Cached on the task so a resumed conversation doesn't re-detect
    every turn.
    """
    if config.VISUAL_ONLY_MODE:
        return {"verified": True, "label": "visual-only mode", "supports_dynamic_arrays": False}
    if task.excel_version_info is not None:
        return task.excel_version_info
    try:
        result, _, _ = dispatch_action("get_excel_version", {})
        task.excel_version_info = result
    except Exception as e:
        task.excel_version_info = {"status": "detection_failed", "error": str(e), "verified": False}
    return task.excel_version_info


def _keep_excel_visible(task: AgentTask) -> None:
    """Make API-driven work observable in the real Excel desktop app."""
    if config.VISUAL_ONLY_MODE or not config.HYBRID_VISIBLE_MODE:
        return
    try:
        from skills.excel_shared import get_active_workbook, keep_workbook_visible

        workbook = get_active_workbook()
        details = keep_workbook_visible(workbook)
        # Visual controls (screenshots, Name Box navigation, and shortcuts)
        # must operate on this exact COM-owned Excel process.  Without this
        # binding, ui_control may create a second blank Excel instance.
        try:
            from vision import ui_control

            ui_control.bind_existing_excel_workbook(workbook.app.pid, workbook.name)
        except Exception:
            # The skill layer is still functional if visual dependencies are
            # unavailable; the following action will report that limitation.
            pass
        if not getattr(task, "visible_session_announced", False):
            task.visible_session_announced = True
            task.log_step(
                f"👁️ Excel is visible: {details['workbook']}. "
                "Using reliable workbook automation with visible checkpoints."
            )
    except Exception as exc:
        # Visibility is a user-experience enhancement.  A transient window
        # activation problem must not make a correctly verified Excel change
        # look like it failed.
        task.log_step(f"👁️ Excel visibility check skipped: {exc}")


def _capture_visual_checkpoint(task: AgentTask, tool_name: str) -> None:
    """Capture the real Excel window after a meaningful verified change.

    Object-model verification remains the source of truth for formulas,
    sheets, and charts.  The checkpoint gives the user a visible, human-like
    audit trail without using fragile mouse automation for structured work.
    """
    if (
        config.VISUAL_ONLY_MODE
        or not config.HYBRID_VISIBLE_MODE
        or not config.ENABLE_VISUAL_CHECKPOINTS
        or tool_name in _OBSERVATION_TOOL_NAMES
        or getattr(task, "visual_checkpoint_unavailable", False)
    ):
        return

    try:
        from datetime import datetime, timezone
        from vision import ui_control

        checkpoint_dir = os.path.join(PROJECT_ROOT, "storage", "visual-checkpoints")
        os.makedirs(checkpoint_dir, exist_ok=True)
        sequence = len(task.visual_checkpoints) + 1
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        filename = f"checkpoint-{timestamp}-{sequence:03d}.png"
        file_path = os.path.join(checkpoint_dir, filename)
        capture = ui_control.screenshot_active_window(file_path)
        checkpoint = {
            "after_tool": tool_name,
            "filename": filename,
            "file_path": file_path,
            "capture": capture,
            "verified": True,
        }
        task.visual_checkpoints.append(checkpoint)
        task.structured_steps.append({"type": "visual_checkpoint", **checkpoint})
        task.log_step(f"📸 Visible Excel checkpoint captured after {tool_name}.")
    except Exception as exc:
        # Do not spam the log after a missing desktop dependency or a locked
        # display.  The normal skill result is still valid on its own.
        task.visual_checkpoint_unavailable = True
        task.log_step(f"📸 Visual checkpoint unavailable: {exc}")


def _visible_range_reference(tool_name: str, tool_input: dict) -> str | None:
    """Return the range worth showing in the Name Box before a skill edits it."""
    range_keys = ("cell", "start_cell", "cell_range", "data_range", "source_range", "reference")
    address = next((tool_input.get(key) for key in range_keys if tool_input.get(key)), None)
    if not isinstance(address, str) or "!" in address:
        return address if isinstance(address, str) else None

    # Workbook-wide actions such as creating a worksheet do not have a target
    # range.  Selecting a made-up cell would look human but provide no value.
    sheet_name = tool_input.get("sheet_name")
    if not isinstance(sheet_name, str) or not sheet_name:
        return address
    escaped_sheet_name = sheet_name.replace("'", "''")
    return f"'{escaped_sheet_name}'!{address}"


def _show_target_in_excel(task: AgentTask, tool_name: str, tool_input: dict) -> None:
    """Use Excel's visible Name Box before a structured range operation."""
    if (
        config.VISUAL_ONLY_MODE
        or not config.HYBRID_VISIBLE_MODE
        or not config.ENABLE_VISIBLE_RANGE_NAVIGATION
        or tool_name in _OBSERVATION_TOOL_NAMES
    ):
        return
    reference = _visible_range_reference(tool_name, tool_input)
    if reference is None:
        return
    try:
        from vision import ui_control

        ui_control.go_to_range(reference)
        task.log_step(f"⌖ Showing {reference} in Excel before {tool_name}.")
    except Exception as exc:
        # The actual skill still has authoritative range addressing, so a
        # visual navigation failure must not turn into a duplicate edit or
        # block the verified operation.
        task.log_step(f"⌖ Name Box navigation skipped for {tool_name}: {exc}")


def _live_sheet_names() -> list[str]:
    """Read actual sheet names instead of letting final review invent them."""
    try:
        from skills.excel_shared import get_active_workbook

        return [sheet.name for sheet in get_active_workbook().sheets]
    except Exception:
        return []


def _build_final_response_reality_check(task: AgentTask, ai_final_text: str) -> str:
    """
    The single most important fix from today's testing: the AI's own
    closing summary has repeatedly claimed full success (sometimes
    describing detailed work on entire sheets it never touched at all)
    while the real structured_steps showed genuine, unresolved
    failures. Trusting that text as-is means the user has no reliable
    way to know whether their workbook is actually complete.

    This rebuilds the user-facing final message by checking REALITY
    (structured_steps) against the AI's claim, and if they disagree,
    prepends a clear, code-generated correction that cannot be
    silently overridden by confident-sounding prose.
    """
    failed_or_unresolved = [
        step for step in task.structured_steps
        if step.get("type") == "action"
        and (
            step.get("status") in {"failed", "retried"}
            or (isinstance(step.get("result"), dict) and step["result"].get("verified") is False)
        )
    ]

    attempted_tools = {
        step.get("tool_name") for step in task.structured_steps if step.get("type") == "action"
    }

    if not failed_or_unresolved:
        return ai_final_text

    failed_names = []
    for step in failed_or_unresolved:
        name = _user_facing_action_name(step.get("tool_name", "unknown"))
        if name not in failed_names:
            failed_names.append(name)

    # A model's prose is not evidence. Never place its completion claims next
    # to an unverified action, because that tells the user a chart/formula
    # exists when the live workbook did not confirm it.
    return (
        "INCOMPLETE: Xelora could not verify every requested Excel change. "
        f"Unverified action(s): {', '.join(failed_names)}. "
        "It will not claim that an unverified result was created. "
        "Please check the workbook before relying on it."
    )


def _user_facing_action_name(tool_name: str) -> str:
    return {
        "activate_ribbon_tab": "opening an Excel tab",
        "go_to_range": "selecting a cell or range",
        "hotkey": "using an Excel keyboard shortcut",
        "press_key": "using an Excel key command",
        "type_text": "entering information",
        "parse_screen": "checking the relevant Excel area",
        "click": "selecting an Excel control",
        "double_click": "opening an Excel control",
        "scroll": "navigating Excel",
        "create_clustered_column_chart": "creating a clustered column chart",
    }.get(tool_name, "an Excel action")


_OBSERVATION_TOOL_NAMES = {
    "get_excel_version", "inspect_workbook", "read_range", "screenshot_active_window",
    "take_screenshot", "parse_screen",
}


def get_task_completion_status(task: AgentTask) -> str:
    """Return the truthful lifecycle state for a task.

    ``is_done`` only means that the worker has stopped. It must not be
    presented as proof that every requested workbook action succeeded. This
    helper is the single status policy used by the live endpoints and the
    persisted task history.
    """
    if task.is_paused:
        return "paused"
    if task.awaiting_approval:
        return "awaiting_approval"
    if not task.is_done:
        return "running"

    actions = [step for step in task.structured_steps if step.get("type") == "action"]
    verified_actions = [
        step for step in actions
        if step.get("status") == "success"
        and isinstance(step.get("result"), dict)
        and step["result"].get("verified") is True
    ]
    meaningful_actions = [
        step for step in verified_actions
        if step.get("tool_name") not in _OBSERVATION_TOOL_NAMES
    ]
    unresolved = [
        step for step in actions
        if step.get("status") in {"failed", "retried", "blocked"}
        or (isinstance(step.get("result"), dict) and step["result"].get("verified") is False)
    ]
    final_text = (task.final_response or "").lstrip().upper()
    explicitly_incomplete = final_text.startswith("INCOMPLETE:") or "VERIFIED STATUS CHECK:" in final_text

    if not verified_actions:
        return "failed"
    if task.started_in_execution_mode and not meaningful_actions:
        return "failed"
    if unresolved or explicitly_incomplete:
        return "completed_with_warnings" if meaningful_actions else "failed"
    return "completed"


def run_task(task: AgentTask, db=None, db_task_id: int = None, user_preferences: dict = None):
    if task.is_paused:
        return task
    if config.VISUAL_ONLY_MODE:
        if _visual_only_requires_structured_workbook_automation(task.instruction):
            return _finish_visual_only_routing_block(task)
        from vision import ui_control
        instruction = task.instruction.lower()
        use_existing = bool(re.search(
            r"\b(existing|open|current|my)\s+(excel\s+)?(workbook|spreadsheet|data)\b"
            r"|\buse\s+(the|this|my)\s+(excel\s+)?(workbook|spreadsheet|data)\b",
            instruction,
        ))
        ui_control.set_workbook_mode(use_existing)
        if not use_existing:
            # The agent owns this blank workbook. It is safe to create before
            # planning and removes the false "I cannot see Excel" dead end.
            try:
                ui_control.prepare_agent_workbook()
            except Exception as exc:
                task.is_done = True
                task.final_response = (
                    "INCOMPLETE: Xelora could not prepare its blank Excel workbook. "
                    f"Reason: {exc}"
                )
                task.chat_transcript.append({"role": "assistant", "text": task.final_response})
                task.log_step(task.final_response)
                return task
    excel_version_info = _detect_excel_version_once(task)
    system_prompt = build_system_prompt(user_preferences, excel_version_info)
    if task.awaiting_approval:
        system_prompt += (
            "\n\nCURRENT MODE: PLANNING ONLY. You may use only read-only workbook tools "
            "to understand the request and workbook. Do not change Excel. Summarize the "
            "proposed changes and ask the user to reply Confirm before execution."
        )
    else:
        system_prompt += (
            "\n\nCURRENT MODE: EXECUTION APPROVED. Apply only the plan the user confirmed. "
            "For a new-workbook request, Xelora has already opened its own blank workbook. "
            "Do not ask the user to describe the screen or confirm that Excel should be opened."
        )
    steps_taken = 0

    if not config.VISUAL_ONLY_MODE:
        from skills.excel_shared import bind_workbook_context
        bind_workbook_context(task.workbook_name)
        _keep_excel_visible(task)

    from knowledge.rag import bind_user_context
    bind_user_context(task.user_id)

    # Do not ask Gemini or OmniParser to rediscover an Excel ribbon tab that
    # has a stable keyboard shortcut.  This runs before the model loop, so a
    # rate limit or a broken local parser cannot prevent a simple navigation
    # request from succeeding.
    if config.VISUAL_ONLY_MODE and task.started_in_execution_mode:
        go_to_reference = _standard_go_to_range(task.instruction)
        if go_to_reference is not None:
            tool_name, tool_input = "go_to_range", {"reference": go_to_reference}
            task.log_step(f"Using Excel Go To for: {go_to_reference}")
            try:
                result, execution_layer, generated_code = dispatch_action(tool_name, tool_input)
            except Exception as exc:
                result = {"error": str(exc), "verified": False}
                execution_layer, generated_code = "error", None
            status = "success" if result.get("verified") is True else "failed"
            task.structured_steps.append({
                "type": "action", "tool_name": tool_name, "execution_layer": execution_layer,
                "input": tool_input, "result": result, "status": status,
            })
            task.is_done = True
            task.final_response = (f"Done — selected {go_to_reference}." if status == "success"
                                   else f"INCOMPLETE: Could not select {go_to_reference}: {result.get('error', 'unknown error')}")
            task.log_step(task.final_response)
            task.chat_transcript.append({"role": "assistant", "text": task.final_response})
            return task
        ribbon_shortcut = _standard_ribbon_tab_shortcut(task.instruction)
        if ribbon_shortcut is not None:
            tab, keys = ribbon_shortcut
            tool_name = "activate_ribbon_tab"
            tool_input = {"tab": tab, "fallback_keys": keys}
            task.log_step(f"Using Excel shortcut for the {tab.title()} tab: {' + '.join(keys)}")
            try:
                result, execution_layer, generated_code = dispatch_action(tool_name, tool_input)
            except Exception as exc:
                result = {"error": str(exc), "verified": False}
                execution_layer, generated_code = "error", None
            status = "success" if result.get("verified") is True else "failed"
            task.structured_steps.append({
                "type": "action", "tool_name": tool_name,
                "execution_layer": execution_layer, "input": tool_input,
                "result": result, "status": status,
            })
            if db is not None and db_task_id is not None:
                _log_action_to_db(db, db_task_id, tool_name, tool_input, execution_layer, generated_code, result, status)
            task.is_done = True
            if status == "success":
                task.final_response = f"Done — opened the Excel {tab.title()} tab."
                task.log_step(task.final_response)
            else:
                task.final_response = f"INCOMPLETE: Could not open the Excel {tab.title()} tab: {result.get('error', 'unknown error')}"
                task.log_step(task.final_response)
            task.chat_transcript.append({"role": "assistant", "text": task.final_response})
            return task

    while not task.is_done and not task.is_paused:
        if steps_taken >= config.MAX_STEPS_PER_TASK:
            task.log_step("⚠️ Reached the maximum number of steps for this task. Stopping for safety.")
            task.is_done = True
            task.final_response = _build_final_response_reality_check(
                task, "Reached the maximum number of steps for this task before finishing."
            )
            break

        if config.AI_PROVIDER == "claude":
            tool_calls, text_blocks, stop_reason = providers.call_claude(task, system_prompt)
        elif config.AI_PROVIDER == "openrouter":
            tool_calls, text_blocks, stop_reason = providers.call_openrouter(task, system_prompt)
        else:
            tool_calls, text_blocks, stop_reason = providers.call_gemini(task, system_prompt)

        for text in text_blocks:
            if text:
                task.log_step(f"🤖 {text}")
                task.structured_steps.append({"type": "reasoning", "text": text})

        if not tool_calls:
            if task.awaiting_approval:
                task.is_done = True
                task.final_response = text_blocks[-1] if text_blocks else (
                    "I need to understand the requested workbook change before proceeding. "
                    "Please clarify what you would like changed."
                )
                task.chat_transcript.append({"role": "assistant", "text": task.final_response})
                break
            has_attempted_action = any(step.get("type") == "action" for step in task.structured_steps)
            if not has_attempted_action and not task.text_only_action_retry_used:
                task.text_only_action_retry_used = True
                task.log_step("â†©ï¸ The model replied without using Excel. Requesting an inspection before completion.")
                task.messages.append({
                    "role": "user",
                    "content": (
                        "Do not provide a text-only plan. Use the available Excel tools now: "
                        "first inspect the active workbook, then perform the requested changes. "
                        "Only report completion after attempting real workbook actions."
                    ),
                })
                continue
            action_steps = [
                step for step in task.structured_steps if step.get("type") == "action"
            ]
            read_only_tools = (
                {"take_screenshot", "parse_screen"}
                if config.VISUAL_ONLY_MODE
                else {"get_excel_version", "inspect_workbook", "read_range", "screenshot_active_window"}
            )
            # OmniParser is very expensive on CPU.  A visual task has already
            # validated the target immediately before its click, so do not
            # force a second full-screen parse merely to finish a one-step
            # request.  Excel API tasks retain their final inspection.
            requires_final_verification = not config.VISUAL_ONLY_MODE
            verification_tool = "inspect_workbook"
            last_workbook_change = max(
                (index for index, step in enumerate(action_steps)
                 if step.get("tool_name") not in read_only_tools),
                default=-1,
            )
            has_final_inspection = any(
                index > last_workbook_change
                and step.get("tool_name") == verification_tool
                and step.get("status") == "success"
                and isinstance(step.get("result"), dict)
                and step["result"].get("verified") is True
                for index, step in enumerate(action_steps)
            )
            if (requires_final_verification and has_attempted_action
                    and not has_final_inspection and not task.final_verification_requested):
                task.final_verification_requested = True
                actual_sheet_names = _live_sheet_names()
                known_sheets = ", ".join(actual_sheet_names) if actual_sheet_names else "(could not read sheet names)"
                task.log_step("Final verification required: requesting a fresh workbook inspection.")
                task.messages.append({
                    "role": "user",
                    "content": (
                        f"Before giving a final answer, call {verification_tool} now as the final verification "
                        "step. Compare the live state to every requested deliverable. Fix any gaps you "
                        "find; if you cannot fix them, respond INCOMPLETE with the missing items. "
                        f"The live workbook currently contains only these sheet names: {known_sheets}. "
                        "Never inspect or claim a sheet name outside that exact list."
                    ),
                })
                continue
            task.is_done = True
            final_text = text_blocks[-1] if text_blocks else "Task complete."
            if requires_final_verification and has_attempted_action and not has_final_inspection:
                final_text = (
                    "INCOMPLETE: a final inspection of the workbook was not successfully completed, "
                    "so the requested work cannot be verified.\n\n" + final_text
                )
            task.final_response = _build_final_response_reality_check(task, final_text)
            task.chat_transcript.append({"role": "assistant", "text": task.final_response})

            unresolved = [
                step for step in task.structured_steps
                if step.get("type") == "action"
                and (
                    step.get("status") in {"failed", "retried"}
                    or (isinstance(step.get("result"), dict) and step["result"].get("verified") is False)
                )
            ]
            if unresolved:
                failed_names = []
                for step in unresolved:
                    name = step.get("tool_name", "unknown")
                    if name not in failed_names:
                        failed_names.append(name)
                task.log_step(
                    "⚠️ Task stopped with unresolved failures: "
                    + ", ".join(failed_names)
                    + ". Do not treat this run as fully complete."
                )
            else:
                task.log_step("✅ Task complete.")
            break

        for tool_call in tool_calls:
            if task.is_paused:
                task.log_step("Task paused before the next workbook action.")
                break
            tool_name = tool_call.name
            tool_input = providers.tool_input(tool_call)
            action_signature = json.dumps([tool_name, tool_input], sort_keys=True, default=str)

            if config.VISUAL_ONLY_MODE:
                visual_actions = [
                    step for step in task.structured_steps
                    if step.get("type") == "action" and step.get("tool_name") in VISUAL_TOOL_NAMES
                ]
                if len(visual_actions) >= config.MAX_VISUAL_ACTIONS_PER_TASK:
                    task.log_step("Visual action limit reached; stopping to protect the workbook from repeated input.")
                    task.is_done = True
                    task.final_response = "INCOMPLETE: Xelora stopped because the visual action limit was reached before the task could be verified."
                    task.chat_transcript.append({"role": "assistant", "text": task.final_response})
                    break

                if tool_name not in READ_ONLY_TOOL_NAMES and action_signature in task.successful_visual_actions:
                    result = {
                        "verified": True,
                        "status": "already_completed",
                        "verification_note": "This exact Excel action already succeeded in this task and was skipped.",
                    }
                    task.structured_steps.append({
                        "type": "action", "tool_name": tool_name, "execution_layer": "duplicate_guard",
                        "input": tool_input, "result": result, "status": "success",
                    })
                    providers.submit_tool_result(task, tool_call, result)
                    continue

            if task.awaiting_approval and tool_name not in READ_ONLY_TOOL_NAMES:
                result = {
                    "verified": False,
                    "error": "Workbook changes are locked until the user explicitly confirms the proposed plan.",
                }
                task.structured_steps.append({
                    "type": "action", "tool_name": tool_name, "execution_layer": "approval_gate",
                    "input": tool_input, "result": result, "status": "blocked",
                })
                providers.submit_tool_result(task, tool_call, result)
                continue

            if (
                tool_name not in _OBSERVATION_TOOL_NAMES
                and action_signature in task.successful_action_signatures
            ):
                result = {
                    "verified": True,
                    "status": "already_completed",
                    "verification_note": (
                        "This exact Excel action already succeeded in this task, so it was skipped "
                        "to avoid repeating the same workbook change."
                    ),
                }
                task.log_step(f"Skipping repeated successful action: {tool_name}.")
                task.structured_steps.append({
                    "type": "action", "tool_name": tool_name, "execution_layer": "duplicate_guard",
                    "input": tool_input, "result": result, "status": "success",
                })
                providers.submit_tool_result(task, tool_call, result)
                continue

            if not config.VISUAL_ONLY_MODE and tool_name not in VISUAL_TOOL_NAMES:
                _show_target_in_excel(task, tool_name, tool_input)

            task.log_step(f"⏳ Running: {tool_name} {tool_input}")

            try:
                result, execution_layer, generated_code = dispatch_action(tool_name, tool_input)
                status = "success"
                is_failure = isinstance(result, dict) and result.get("verified") is False
            except Exception as e:
                result = {"error": str(e), "verified": False}
                execution_layer, generated_code = "error", None
                status = "success"  # placeholder, corrected by the shared block below
                is_failure = True

            if is_failure:
                task.log_step(f"⚠️ Not verified: {tool_name} -> {result.get('verification_note', result.get('error', 'no details'))}")
                retries_so_far = task.retry_counts.get(tool_name, 0)
                if retries_so_far < config.MAX_RETRIES_PER_ACTION:
                    task.retry_counts[tool_name] = retries_so_far + 1
                    status = "retried"
                    task.log_step(f"🔁 Letting the AI decide whether to retry (attempt {retries_so_far + 1}).")
                else:
                    status = "failed"
                    task.log_step(f"❌ Giving up on {tool_name} after {config.MAX_RETRIES_PER_ACTION} attempts.")
            else:
                task.log_step(f"✅ Done: {tool_name} ({execution_layer}) -> {result}")

            task.structured_steps.append({
                "type": "action", "tool_name": tool_name, "execution_layer": execution_layer,
                "input": tool_input, "result": result, "status": status,
            })

            if status == "success" and isinstance(result, dict) and result.get("verified") is True:
                if tool_name not in _OBSERVATION_TOOL_NAMES:
                    task.successful_action_signatures.add(action_signature)
                _keep_excel_visible(task)
                _capture_visual_checkpoint(task, tool_name)

            if config.VISUAL_ONLY_MODE and status == "success" and tool_name not in READ_ONLY_TOOL_NAMES:
                task.successful_visual_actions.add(action_signature)

            if db is not None and db_task_id is not None:
                _log_action_to_db(db, db_task_id, tool_name, tool_input, execution_layer, generated_code, result, status)

            providers.submit_tool_result(task, tool_call, result)

        # VISUAL-MODE COMPLETION GUARD. A direct-action request ("click the
        # Insert tab") is done as soon as that action actually succeeded -
        # but nothing in the loop stopped the model from re-parsing and
        # re-clicking the finished action forever. The visual system prompt
        # already tells the model to stop after one action; this enforces it
        # at the loop level. Tasks that began in planning mode (multi-step
        # plan awaiting approval) are not affected - once approved they run
        # the full plan.
        if (config.VISUAL_ONLY_MODE and task.started_in_execution_mode
                and _is_one_step_navigation_request(task.instruction)):
            turn_steps = task.structured_steps[-len(tool_calls):]
            succeeded_actions = [
                step.get("tool_name")
                for step in turn_steps
                if step.get("type") == "action"
                and step.get("status") == "success"
                and step.get("tool_name") not in ("take_screenshot", "parse_screen")
                and isinstance(step.get("result"), dict)
                and step["result"].get("verified") is True
            ]
            if succeeded_actions:
                task.log_step("✅ Requested action completed - stopping.")
                task.is_done = True
                completed = ", ".join(dict.fromkeys(succeeded_actions))
                task.final_response = f"Done - completed: {completed}."
                task.chat_transcript.append({"role": "assistant", "text": task.final_response})
                break

        steps_taken += 1

    return task
