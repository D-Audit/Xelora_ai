"""
agent/core.py
The brain of the system. Goal -> Planning -> Execution -> Verification
-> Correction -> Completion, dispatching each action to one of three
layers: skill library, code generation, or visual fallback.
"""

import concurrent.futures
import contextvars
import json
import os
import re
import sys

import config
from skills.registry import has_skill, run_skill
from codegen.executor import run_generated_code
from agent import providers
from agent.capabilities import (
    build_execution_capabilities,
    planning_context,
    recovery_options,
)
from agent.prompts import build_system_prompt

VISUAL_TOOL_NAMES = {"take_screenshot", "parse_screen", "click", "double_click", "hover_and_read_tooltip", "inspect_popup", "click_popup_button", "click_popup_control", "set_popup_text", "save_workbook", "type_text", "press_key", "hotkey", "scroll", "activate_ribbon_tab", "press_alt", "press_shortcut", "go_to_range", "paste_table", "fill_formula_down", "format_currency", "format_bold", "autofit_columns", "create_clustered_column_chart", "create_pie_chart", "execute_excel_shortcut", "batch_excel_operations", "search_cached_elements", "find_and_click", "click_ribbon_tab", "click_button", "create_sheet", "rename_sheet", "go_to_sheet", "navigate_to_cell_on_sheet", "verify_task_completion", "get_active_sheet_name", "verify_current_sheet", "get_sheet_info", "get_cell_value", "apply_cell_style", "set_header_style", "set_fill_color", "set_font_color", "apply_dashboard_theme"}
READ_ONLY_TOOL_NAMES = {"take_screenshot", "parse_screen", "inspect_popup", "search_cached_elements", "get_execution_capabilities"}

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKILL_TIMEOUT_SECONDS = config.SKILL_TIMEOUT_SECONDS

try:
    from vision.ui_control import _get_agent_excel_window
    _HAS_WINDOW_SAFETY = True
except ImportError:
    _HAS_WINDOW_SAFETY = False


def _run_skill_with_timeout(
    tool_name: str,
    tool_input: dict,
    timeout: int = SKILL_TIMEOUT_SECONDS,
    recover_excel_on_timeout: bool = True,
):
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    # The selected workbook is stored in a ContextVar.  New threads do not
    # inherit it automatically, which previously let a skill fall back to
    # whichever Excel workbook happened to be active.  Run each skill inside
    # a copy of the task context so all calls target the same workbook.
    task_context = contextvars.copy_context()
    future = ex.submit(task_context.run, run_skill, tool_name, **tool_input)
    timed_out = False
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        timed_out = True
        future.cancel()

        if not recover_excel_on_timeout:
            return {
                "error": f"'{tool_name}' did not finish within {timeout}s.",
                "verified": False,
                "status": "timeout",
                "verification_note": (
                    "This optional startup check timed out. Excel was left open and no workbook "
                    "restart was attempted. Xelora will use conservative Excel-compatible behavior."
                ),
            }

        from skills.excel_shared import force_restart_excel_and_reopen
        recovered_identity = {}
        try:
            recovered_workbook, _ = force_restart_excel_and_reopen()
            recovered_identity = {
                "workbook_recovered": True,
                "workbook_name": recovered_workbook.name,
                "excel_app_pid": recovered_workbook.app.pid,
            }
            recovery_note = "Excel was automatically restarted to clear the hang - everything written before this point is safely saved."
        except Exception as recovery_error:
            recovery_note = f"Attempted auto-recovery but it also failed: {recovery_error}"

        return {
            "error": f"'{tool_name}' did not finish within {timeout}s. "
                     f"Excel was restarted to recover the automation session. {recovery_note}",
            "verified": False,
            "status": "timeout_recovered",
            **recovered_identity,
        }
    finally:
        ex.shutdown(wait=not timed_out, cancel_futures=True)


class AgentTask:
    def __init__(self, instruction: str, user_id: int = None, workbook_name: str = None):
        self.instruction = instruction
        self.user_id = user_id
        self.workbook_name = workbook_name
        # Set after the first live workbook inspection.  Names such as Book1
        # are not unique, so all later codegen and visual fallback work must
        # retain this process identity too.
        self.excel_app_pid = None
        self.messages = [{"role": "user", "content": instruction}]
        self.is_paused = False
        self.is_done = False
        self.progress_log = []
        self.structured_steps = []
        self.retry_counts = {}
        self.gemini_model_index = 0
        # The task normally stays with the configured primary provider.  This
        # changes only after a proven provider availability failure, never
        # because an Excel action merely failed verification.
        self.active_provider = config.AI_PROVIDER
        self.provider_failover_history = []
        self.final_response = None
        self.chat_transcript = [{"role": "user", "text": instruction}]
        self.excel_version_info = None  # filled in once at task start, see run_task()
        self.workbook_state = None  # semantic, read-only state used for tool selection
        self.execution_capabilities = None
        self.text_only_action_retry_used = False
        self.final_verification_requested = False
        self.formula_error_repair_requested = False
        self.last_formula_error_audit = None
        # A formula that stored but returned #REF!, #VALUE!, or blank output
        # is a hard dependency boundary. The task may inspect freely and
        # repair the affected sheet, but it may not build downstream sheets
        # from an unverified calculation.
        self.pending_formula_repair = None
        # Gemini may return several parallel function calls in one response.
        # Their results must be returned together, otherwise a later unsigned
        # call is treated as a malformed new tool turn.
        self.gemini_expected_function_responses = 0
        self.gemini_function_response_order = []
        self.gemini_function_response_batch = []
        # A failed, eligible skill is escalated to a single code-generation
        # attempt on the next model turn. Keeping this explicit task state
        # lets both providers enforce the fallback instead of merely hoping
        # the model remembers a sentence in the prompt.
        self.pending_codegen_fallback = None
        # A task may be actively recovering after a failed action. This is
        # visible to the user, but it never authorizes overlapping or
        # speculative Excel writes. The executor remains serial.
        self.recovery_state = None
        self.recovery_guard_block_count = 0
        self.successful_visual_actions = set()
        self.successful_action_signatures = set()
        self.visual_checkpoints = []
        self.visual_checkpoint_unavailable = False
        # For structured visual-only workbook builds, the controller derives
        # the promised worksheet list from the user's instruction.  The model
        # may not replace that list with a convenient partial list such as
        # ["Sheet1"] when it asks to verify completion.
        self.required_visual_sheet_names = []
        self.final_save_requested = False
        # Direct imperative requests (for example, "click the Insert tab")
        # already state the action the user wants.  Start those tasks in
        # execution mode; descriptive or exploratory requests still begin
        # with the existing plan-and-confirm safeguard.
        # A request may start with an imperative ("create a dashboard") but
        # still explicitly require a plan and the user's approval before
        # Excel is opened or changed. That instruction must override the
        # otherwise convenient direct-action shortcut.
        self.defer_excel_until_approval = _requires_explicit_plan_approval(instruction)
        self.awaiting_approval = (
            self.defer_excel_until_approval
            or not _is_direct_action_instruction(instruction)
        )
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
                self.defer_excel_until_approval = False
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
                self.defer_excel_until_approval = _requires_explicit_plan_approval(correction)
                self.awaiting_approval = (
                    self.defer_excel_until_approval
                    or not _is_direct_action_instruction(correction)
                )
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
            self.formula_error_repair_requested = False
            self.last_formula_error_audit = None
            self.pending_formula_repair = None
            self.workbook_state = None
            self.execution_capabilities = None
            self.gemini_expected_function_responses = 0
            self.gemini_function_response_order = []
            self.gemini_function_response_batch = []
            self.active_provider = config.AI_PROVIDER
            self.provider_failover_history = []
            self.pending_codegen_fallback = None
            self.recovery_state = None
            self.recovery_guard_block_count = 0
            self.successful_visual_actions = set()
            self.successful_action_signatures = set()
            self.visual_checkpoints = []
            self.visual_checkpoint_unavailable = False
            self.chat_transcript.append({"role": "user", "text": correction})

    def log_step(self, message: str):
        self.progress_log.append(message)
        try:
            print(message)
        except UnicodeEncodeError:
            # Windows consoles can still use a legacy code page even when the
            # API and UI fully support Unicode.  Progress logging must never
            # terminate a workbook task merely because a provider used an
            # emoji or another non-ASCII character.
            encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
            safe_message = message.encode(encoding, errors="backslashreplace").decode(encoding)
            print(safe_message)

    def set_recovery_state(
        self,
        phase: str,
        message: str,
        *,
        tool_name: str | None = None,
        safe_to_continue: bool = False,
    ) -> None:
        """Publish a truthful, user-visible recovery checkpoint.

        This is progress information, not a second executor. Dependent
        workbook edits remain paused until the current action has either been
        verified or stopped with a clear reason.
        """
        self.recovery_state = {
            "phase": phase,
            "message": message,
            "tool_name": tool_name,
            "safe_to_continue": safe_to_continue,
        }
        self.structured_steps.append({
            "type": "recovery",
            "phase": phase,
            "text": message,
            "tool_name": tool_name,
            "safe_to_continue": safe_to_continue,
        })
        self.log_step(f"Recovery ({phase}): {message}")

    def clear_recovery_state(self, message: str | None = None) -> None:
        """End an active recovery only after a verified action succeeds."""
        if self.recovery_state is None:
            return
        previous = self.recovery_state
        self.recovery_state = None
        self.recovery_guard_block_count = 0
        if message:
            self.structured_steps.append({
                "type": "recovery",
                "phase": "recovered",
                "text": message,
                "tool_name": previous.get("tool_name"),
                "safe_to_continue": True,
            })
            self.log_step(f"Recovery complete: {message}")

    def log_rate_limit(self, model: str):
        """Log a rate limit hit for a model."""
        self.log_step(f"OpenRouter rate limited: {model}")


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


def _requires_explicit_plan_approval(message: str) -> bool:
    """Whether the user expressly prohibited starting Excel work yet."""
    normalized = " ".join(message.lower().strip().split())
    approval_markers = (
        "wait for my approval",
        "wait for explicit approval",
        "wait for my explicit approval",
        "only after i approve",
        "only after approval",
        "do not modify excel immediately",
        "do not change excel immediately",
        "do not open excel immediately",
        "plan first and wait",
    )
    return any(marker in normalized for marker in approval_markers)


def _is_direct_action_instruction(message: str) -> bool:
    """Recognize a new imperative as approval to execute an existing plan.

    This is intentionally limited to common imperative verbs so ordinary
    clarifications (for example, "the workbook is open") still remain in
    planning mode until the user explicitly asks the agent to act.
    """
    normalized = " ".join(message.lower().strip().split())
    if _requires_explicit_plan_approval(normalized):
        return False
    return normalized.startswith((
        "click ", "double click ", "open ", "close ", "insert ", "add ",
        "delete ", "remove ", "update ", "change ", "edit ", "write ",
        "create ", "format ", "sort ", "filter ", "run ", "apply ",
        "select ", "type ", "press ", "go to ", "make ", "build ",
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


def _order_tool_calls_by_sheet_dependency(tool_calls):
    """Run a requested create_sheet call before calls that target that sheet.

    Providers can return multiple function calls together. They do not always
    preserve the workbook dependency (for example, write_table('Sales Data')
    before create_sheet('Sales Data')). Reordering only those direct
    dependencies keeps the provider's otherwise chosen sequence intact while
    preventing a guaranteed missing-sheet failure.
    """
    calls_with_inputs = []
    created_sheets = set()
    targeted_sheets = set()
    for index, tool_call in enumerate(tool_calls):
        try:
            # Handle both object (Gemini/Claude) and dict (OpenRouter) formats
            tool_name = tool_call.name if hasattr(tool_call, 'name') else tool_call.get('name', '')
            tool_input = providers.tool_input(tool_call)
        except Exception:
            tool_name, tool_input = "", {}
        calls_with_inputs.append((index, tool_call, tool_name, tool_input))
        if tool_name == "create_sheet" and isinstance(tool_input.get("sheet_name"), str):
            created_sheets.add(tool_input["sheet_name"])
        elif isinstance(tool_input.get("sheet_name"), str):
            targeted_sheets.add(tool_input["sheet_name"])

    dependency_sheets = created_sheets & targeted_sheets
    ordered = sorted(
        calls_with_inputs,
        key=lambda item: (
            0 if item[2] == "create_sheet" and item[3].get("sheet_name") in dependency_sheets else 1,
            item[0],
        ),
    )
    return [item[1] for item in ordered]


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
    if config.OMNIPARSER_ONLY_MODE:
        task.final_response = (
            "INCOMPLETE: This request needs structured Excel automation (such as worksheets, "
            "formulas, charts, or a dashboard) that cannot be reliably performed through "
            "keyboard/mouse automation alone. OmniParser-only mode uses visual UI tools and "
            "cannot create complex workbook structures. Try a simpler request, or switch to "
            "hybrid mode (OMNIPARSER_ONLY_MODE=false) for API-backed automation."
        )
    else:
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


def _normalise_visual_tool_result(tool_name: str, result):
    """Keep a malformed visual helper from crashing the agent loop.

    Every provider tool must return an evidence mapping.  The guard converts a
    legacy primitive return (such as a bare sheet-name string) into a normal
    failed action, so the model can recover instead of the worker stopping
    with ``'str' object has no attribute 'get'``.
    """
    if isinstance(result, dict):
        if isinstance(result.get("verified"), bool):
            return result
        normalized = dict(result)
        normalized["verified"] = False
        normalized.setdefault("status", "missing_verification_evidence")
        normalized.setdefault(
            "error",
            f"Visual tool '{tool_name}' returned without a boolean verified result.",
        )
        return normalized
    return {
        "verified": False,
        "status": "invalid_visual_tool_result",
        "error": f"Visual tool '{tool_name}' returned {type(result).__name__}, not a result mapping.",
    }


def _is_lost_task_workbook(result: dict | None) -> bool:
    """Recognise a lost task workbook as terminal in every execution mode.

    Retrying with codegen, shortcuts, or another skill cannot recreate the
    exact workbook safely. It only wastes time and risks editing a different
    Excel window.
    """
    if not isinstance(result, dict):
        return False
    detail = " ".join(
        str(result.get(key, "")) for key in ("error", "verification_note", "status")
    ).lower()
    return any(phrase in detail for phrase in (
        "task's target workbook",
        "target workbook is not open in excel",
        "xelora-owned excel window is no longer visible",
        "excel workbook bound to this task is no longer visible",
        "excel process is no longer visible",
        "agent window lost",
    ))


def _is_lost_visual_excel_window(result: dict | None) -> bool:
    """Backward-compatible name for visual callers."""
    return _is_lost_task_workbook(result)


def _has_pending_create_table_completion(task: AgentTask, popups: list[dict]) -> bool:
    """Whether this task opened the valid Create Table dialog it now sees.

    A large clipboard paste can make Excel expose Create Table just after the
    first local wait expires. Only resume that dialog automatically when this
    same task attempted ``insert_table`` and received that specific timeout;
    a dialog a user opened independently is never accepted on their behalf.
    """
    if not any(
        isinstance(popup, dict) and "create table" in str(popup.get("title", "")).lower()
        for popup in popups
    ):
        return False
    for step in reversed(getattr(task, "structured_steps", [])):
        if step.get("type") != "action":
            continue
        if step.get("tool_name") not in {"execute_excel_shortcut", "press_shortcut"}:
            continue
        shortcut = str((step.get("input") or {}).get("shortcut_name", "")).strip().lower()
        outcome = step.get("result") if isinstance(step.get("result"), dict) else {}
        if shortcut == "insert_table" and outcome.get("status") == "create_table_dialog_not_found":
            return True
    return False


def dispatch_action(
    tool_name: str,
    tool_input: dict,
    workbook_name: str | None = None,
    excel_app_pid: int | None = None,
    skill_timeout: int | None = None,
    recover_excel_on_timeout: bool = True,
):
    if tool_name == "get_execution_capabilities":
        return build_execution_capabilities(), "capability_catalog", None

    if config.VISUAL_ONLY_MODE:
        if tool_name not in VISUAL_TOOL_NAMES:
            # In OmniParser-only mode, suggest a visual equivalent when possible
            if config.OMNIPARSER_ONLY_MODE:
                visual_hint = _suggest_visual_alternative(tool_name, tool_input)
                return {
                    "error": (
                        f"Tool '{tool_name}' is not available in OmniParser-only mode. "
                        f"{visual_hint}"
                    ),
                    "verified": False,
                    "status": "function_not_available_in_visual_mode",
                }, "blocked", None
            return {"error": "VISUAL_ONLY_MODE blocks Excel API and code-generation tools.", "verified": False}, "blocked", None
        if tool_name == "hotkey":
            keys = [str(key).lower() for key in tool_input.get("keys", [])]
            if keys in (["ctrl", "g"], ["f5"]):
                return {
                    "error": "Use go_to_range with a valid reference; raw Go To shortcuts can leave an unfinished dialog.",
                    "verified": False,
                }, "blocked", None
            if keys == ["ctrl", "s"]:
                from vision import ui_control
                return ui_control.save_workbook(), "visual", None
        from vision import ui_control
        result = getattr(ui_control, tool_name)(**tool_input)
        return _normalise_visual_tool_result(tool_name, result), "visual", None

    if tool_name == "write_table" and _write_table_input_contains_formula_values(tool_input):
        return {
            "error": (
                "write_table rows must contain source values only, not formulas. "
                "Keep the calculated-column headers, use blank values for those cells, "
                "create the Excel Table, then use insert_formula for each calculated column."
            ),
            "verified": False,
            "status": "formula_values_require_insert_formula",
        }, "input_guard", None

    if has_skill(tool_name):
        return _run_skill_with_timeout(
            tool_name,
            tool_input,
            timeout=skill_timeout or SKILL_TIMEOUT_SECONDS,
            recover_excel_on_timeout=recover_excel_on_timeout,
        ), "skill", None

    if tool_name == "run_excel_code":
        if not config.ENABLE_CODEGEN_LAYER:
            if config.OMNIPARSER_ONLY_MODE:
                return {
                    "error": (
                        "Code generation is disabled in OmniParser-only mode. "
                        "Use visual UI tools (go_to_range, type_text, paste_table, hotkey) "
                        "to perform this operation through Excel's interface."
                    ),
                    "verified": False,
                    "status": "codegen_disabled_visual_mode",
                }, "blocked", None
            return {"error": "The code-generation layer is disabled by configuration.", "verified": False}, "blocked", None
        fallback_reason = str(tool_input.get("fallback_reason") or "").strip()
        atomic_goal = str(tool_input.get("atomic_goal") or "").strip()
        alternatives_considered = tool_input.get("alternatives_considered")
        reveal_reference = str(tool_input.get("reveal_reference") or "").strip()
        valid_alternatives = (
            isinstance(alternatives_considered, list)
            and any(isinstance(item, str) and item.strip() for item in alternatives_considered)
        )
        if not fallback_reason or not atomic_goal or not valid_alternatives or not reveal_reference:
            return {
                "verified": False,
                "status": "codegen_selection_evidence_required",
                "error": (
                    "run_excel_code requires fallback_reason, atomic_goal, alternatives_considered, "
                    "and reveal_reference. Choose a shortcut or skill when one can safely do the "
                    "operation; otherwise name the one bounded goal, explain why the considered "
                    "routes are unsuitable, and state the result range or chart source to reveal."
                ),
            }, "codegen_guard", None
        code = tool_input.get("code", "")
        result = run_generated_code(
            code,
            project_root=PROJECT_ROOT,
            workbook_name=workbook_name,
            excel_app_pid=excel_app_pid,
        )
        if result.get("verified") is True:
            # The codegen runner uses a separate process. Save the same
            # named workbook again from the task process so a subsequent
            # timeout recovery has a persisted checkpoint to reopen.
            try:
                from skills.excel_shared import bind_workbook_context, save_active_workbook_best_effort

                bind_workbook_context(workbook_name, excel_app_pid)
                save_active_workbook_best_effort()
            except Exception:
                pass
        return result, "codegen", code

    if tool_name in VISUAL_TOOL_NAMES:
        if not config.ENABLE_VISUAL_FALLBACK:
            return {"error": "Visual fallback is disabled (ENABLE_VISUAL_FALLBACK=false).",
                    "verified": False}, "visual", None
        from vision import ui_control
        func = getattr(ui_control, tool_name)
        return _normalise_visual_tool_result(tool_name, func(**tool_input)), "visual", None

    return {"error": f"Unknown tool '{tool_name}'", "verified": False}, "unknown", None


def _suggest_visual_alternative(tool_name: str, tool_input: dict) -> str:
    """Suggest a visual UI alternative when a skill/API tool is unavailable."""
    alternatives = {
        "create_sheet": "Use create_sheet with the requested sheet name; it safely creates and verifies the tab before it is renamed or used.",
        "write_cell": "Use go_to_range to navigate to the cell, then type_text to enter the value.",
        "write_table": "Use go_to_range to navigate to the start cell, then paste_table with headers and rows.",
        "insert_formula": "Use go_to_range to navigate to the cell, type_text with the formula, then press_key('enter'). Use fill_formula_down for columns.",
        "apply_formatting": "Use go_to_range to select the range, then hotkey for formatting (Ctrl+B for bold, Ctrl+Shift+4 for currency).",
        "read_range": "Use parse_screen('window') to see the current content, or use take_screenshot.",
        "inspect_workbook": "Use parse_screen('window') to observe the current workbook state.",
        "get_excel_version": "Use parse_screen('ribbon') to see Excel version info in the title bar.",
        "sort_range": "Use hotkey with Excel sort shortcuts (Alt+A for Data tab).",
        "create_pivot_table": "Use hotkey Alt+N for Insert tab, then navigate pivot table creation via keyboard.",
        "create_chart": "Use create_clustered_column_chart visual tool for basic charts.",
        "freeze_panes": "Use hotkey Alt+W+R+F for View > Freeze Panes.",
        "auto_fit_columns": "Use autofit_columns visual tool.",
        "conditional_formatting": "Use hotkey Alt+H+L for Home > Conditional Formatting.",
        "save_workbook": "Use the visual save_workbook tool; provide file_name for a new workbook so it can complete Save As safely.",
        "export_to_pdf": "Use hotkey Ctrl+P for Print, then navigate to PDF export.",
        "open_workbook": "Use hotkey Ctrl+O to open a file.",
    }
    return alternatives.get(tool_name, "Try using go_to_range, type_text, hotkey, or parse_screen to achieve this through Excel's UI.")


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


def _adopt_workbook_from_result(task: AgentTask, result: dict, db=None, db_task_id: int = None) -> None:
    """Keep task, worker threads, codegen, and persisted task row on one workbook."""
    if not isinstance(result, dict) or result.get("verified") is not True:
        return
    workbook_name = result.get("workbook_name")
    if not isinstance(workbook_name, str) or not workbook_name.strip():
        return

    task.workbook_name = workbook_name
    excel_app_pid = result.get("excel_app_pid")
    if not isinstance(excel_app_pid, int):
        excel_app_pid = getattr(task, "excel_app_pid", None)
    task.excel_app_pid = excel_app_pid
    try:
        from skills.excel_shared import bind_workbook_context

        bind_workbook_context(workbook_name, excel_app_pid)
    except Exception:
        pass

    if db is not None and db_task_id is not None:
        try:
            from models import Task

            db_task = db.get(Task, db_task_id)
            if db_task is not None:
                db_task.workbook_name = workbook_name
                db.commit()
        except Exception:
            # Persistence failure must not discard a verified workbook action.
            try:
                db.rollback()
            except Exception:
                pass


def _adopt_recovered_workbook_identity(task: AgentTask, result: dict, db=None, db_task_id: int = None) -> None:
    """Rebind after a timeout restart even though the timed-out action failed.

    A restart creates a new Excel process by design.  Task 265 retained the
    dead PID after this recovery, so subsequent Name Box navigation and
    checkpoints correctly refused to touch the new workbook window.  The
    recovered workbook identity is safe evidence from the restart routine,
    not evidence that the original action succeeded.
    """
    if not isinstance(result, dict) or result.get("workbook_recovered") is not True:
        return
    workbook_name = result.get("workbook_name")
    excel_app_pid = result.get("excel_app_pid")
    if not isinstance(workbook_name, str) or not workbook_name.strip() or not isinstance(excel_app_pid, int):
        return

    task.workbook_name = workbook_name
    task.excel_app_pid = excel_app_pid
    try:
        from skills.excel_shared import bind_workbook_context

        bind_workbook_context(workbook_name, excel_app_pid)
    except Exception:
        pass

    if db is not None and db_task_id is not None:
        try:
            from models import Task

            db_task = db.get(Task, db_task_id)
            if db_task is not None:
                db_task.workbook_name = workbook_name
                db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass


def _action_recovery_key(tool_name: str, tool_input: dict) -> str | None:
    """Identify the workbook target that a later successful call can repair."""
    target_fields = {
        "insert_formula": ("sheet_name", "cell", "fill_to"),
        "write_table": ("sheet_name", "start_cell", "table_name"),
        "create_pivot_table": ("dest_sheet_name", "dest_cell"),
        "create_chart": ("sheet_name", "chart_name"),
    }.get(tool_name)
    if not target_fields:
        return None
    target = tuple(str(tool_input.get(field, "")) for field in target_fields)
    return json.dumps((tool_name, target), separators=(",", ":"))


def _mark_prior_action_recovered(task: AgentTask, tool_name: str, tool_input: dict) -> None:
    """Resolve failed attempts once the same workbook target is verified."""
    recovery_key = _action_recovery_key(tool_name, tool_input)
    if recovery_key is None:
        return
    for step in task.structured_steps:
        if (
            step.get("type") == "action"
            and step.get("status") in {"failed", "retried"}
            and _action_recovery_key(step.get("tool_name", ""), step.get("input", {})) == recovery_key
        ):
            step["status"] = "recovered"
            step["recovery_note"] = "A later verified action completed this same workbook target."


def _detect_excel_version_once(task: AgentTask):
    """
    Runs get_excel_version automatically at the very start of a task
    (not left to the AI to remember to call), so version-awareness is
    guaranteed rather than dependent on the model choosing to check.
    Cached on the task so a resumed conversation doesn't re-detect
    every turn.
    """
    if config.VISUAL_ONLY_MODE:
        if task.excel_version_info is not None:
            return task.excel_version_info
        try:
            from vision.ui_control import get_visual_excel_context

            task.excel_version_info = get_visual_excel_context()
        except Exception as exc:
            task.excel_version_info = {
                "verified": False,
                "label": "visual-only mode (identity unavailable)",
                "supports_dynamic_arrays": False,
                "error": str(exc),
            }
        return task.excel_version_info
    if task.excel_version_info is not None:
        return task.excel_version_info
    try:
        result, _, _ = dispatch_action(
            "get_excel_version",
            {},
            skill_timeout=config.INITIAL_EXCEL_CHECK_TIMEOUT_SECONDS,
            recover_excel_on_timeout=False,
        )
        task.excel_version_info = result
    except Exception as e:
        task.excel_version_info = {"status": "detection_failed", "error": str(e), "verified": False}
    return task.excel_version_info


def _inspect_workbook_state_once(task: AgentTask) -> dict:
    """Collect read-only workbook evidence before the planner chooses write tools."""
    if isinstance(task.workbook_state, dict):
        return task.workbook_state

    try:
        if config.VISUAL_ONLY_MODE:
            from vision import ui_control

            context = ui_control.get_visual_excel_context()
            popup = ui_control.inspect_popup()
            sheets = ui_control.get_existing_sheet_names()
            active = ui_control.get_active_sheet_name()
            task.workbook_state = {
                **context,
                "sheet_names": sheets,
                "active_sheet": active.get("sheet_name"),
                "popup_status": popup.get("status"),
                "verified": bool(context.get("verified") is True and popup.get("status") == "clean"),
            }
        else:
            state, _, _ = dispatch_action("inspect_workbook", {}, workbook_name=task.workbook_name)
            task.workbook_state = state if isinstance(state, dict) else {
                "verified": False,
                "error": "Workbook inspection did not return a result mapping.",
            }
    except Exception as exc:
        task.workbook_state = {
            "verified": False,
            "error": f"Workbook inspection was unavailable: {exc}",
        }

    if task.workbook_state.get("verified") is True:
        task.log_step("Workbook state inspected before tool selection.")
    else:
        task.log_step(
            "Workbook state inspection was unavailable; the AI must use read-only evidence "
            "before changing an unfamiliar workbook."
        )
    return task.workbook_state


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
    range_keys = (
        "reveal_reference", "cell", "start_cell", "cell_range", "data_range",
        "source_range", "reference",
    )
    address = next((tool_input.get(key) for key in range_keys if tool_input.get(key)), None)
    if not isinstance(address, str):
        return None
    if "!" in address:
        sheet_name, cell_reference = address.rsplit("!", 1)
        stripped_sheet = sheet_name.strip()
        # Excel accepts quoted sheet names universally, but bare multi-word
        # names make Ctrl+G reject the reference. Normalise this UI-only
        # representation instead of letting a missing quote silently skip
        # the visible navigation.
        if not (
            len(stripped_sheet) >= 2
            and stripped_sheet.startswith("'")
            and stripped_sheet.endswith("'")
        ) and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", stripped_sheet):
            stripped_sheet = "'" + stripped_sheet.replace("'", "''") + "'"
        return f"{stripped_sheet}!{cell_reference.strip()}"

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


def _show_verified_result_in_excel(
    task: AgentTask,
    tool_name: str,
    tool_input: dict,
    result: dict,
) -> None:
    """Reveal an outcome that did not have an existing range before it ran.

    Most structured skills are already shown through the Name Box before they
    edit their target. A newly created sheet does not exist yet, and a bounded
    codegen batch should show its changed range after it has completed.
    """
    if (
        config.VISUAL_ONLY_MODE
        or not config.HYBRID_VISIBLE_MODE
        or not config.ENABLE_VISIBLE_RANGE_NAVIGATION
    ):
        return

    reference = None
    if tool_name == "create_sheet":
        sheet_name = result.get("sheet_name")
        if isinstance(sheet_name, str) and sheet_name.strip():
            escaped = sheet_name.strip().replace("'", "''")
            reference = f"'{escaped}'!A1"
    elif tool_name == "run_excel_code":
        reference = _visible_range_reference(tool_name, tool_input)

    if reference is None:
        return
    try:
        from vision import ui_control

        ui_control.go_to_range(reference)
        task.log_step(f"Showing verified result {reference} in Excel after {tool_name}.")
    except Exception as exc:
        task.log_step(f"Result navigation skipped for {tool_name}: {exc}")


def _live_sheet_names() -> list[str]:
    """Read actual sheet names instead of letting final review invent them."""
    try:
        from skills.excel_shared import get_active_workbook

        return [sheet.name for sheet in get_active_workbook().sheets]
    except Exception:
        return []


def _required_visual_sheet_names(instruction: str) -> list[str]:
    """Extract an explicitly ordered worksheet list from a user request.

    This intentionally recognises only the unambiguous ``worksheets in this
    order`` form.  It is a completion safeguard, not a guesser: ordinary
    requests keep their existing visual workflow, while a structured workbook
    request cannot be signed off against a partial, model-invented list.
    """
    if not isinstance(instruction, str):
        return []
    ordered_block = re.search(
        r"(?:^|\n)\s*create\s+(?:these\s+)?worksheets?\s+in\s+(?:this\s+)?order\s*:\s*"
        r"(.*?)(?=\n\s*before\s+finishing\b|\Z)",
        instruction,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not ordered_block:
        return []

    names = []
    for match in re.finditer(r"(?m)^\s*\d+\s*[.)]\s*([^\r\n]+?)\s*$", ordered_block.group(1)):
        name = " ".join(match.group(1).split())
        if name and name not in names:
            names.append(name)
    return names


def _normalised_sheet_names(sheet_names) -> list[str]:
    if not isinstance(sheet_names, list):
        return []
    return [" ".join(str(name).split()).casefold() for name in sheet_names if str(name).strip()]


def _visual_completion_check_matches_required_sheets(task: AgentTask, step: dict) -> bool:
    """Return true only for a successful completion check of the full promised list."""
    expected = list(getattr(task, "required_visual_sheet_names", []) or [])
    if not expected:
        return True
    if step.get("tool_name") != "verify_task_completion":
        return False
    if step.get("status") != "success":
        return False
    result = step.get("result")
    if not isinstance(result, dict) or result.get("verified") is not True:
        return False
    return _normalised_sheet_names(step.get("input", {}).get("expected_sheets")) == _normalised_sheet_names(expected)


def _has_post_change_visual_completion_check(task: AgentTask, after_index: int = -1) -> bool:
    return any(
        index > after_index
        and step.get("type") == "action"
        and _visual_completion_check_matches_required_sheets(task, step)
        for index, step in enumerate(task.structured_steps)
    )


def _next_required_visual_sheet(task: AgentTask) -> str | None:
    """Return the next worksheet that must be created and verified in order."""
    required = list(getattr(task, "required_visual_sheet_names", []) or [])
    if not required:
        return None
    completed = set()
    for step in task.structured_steps:
        if step.get("type") != "action" or step.get("tool_name") != "create_sheet":
            continue
        if step.get("status") != "success":
            continue
        result = step.get("result")
        if not isinstance(result, dict) or result.get("verified") is not True:
            continue
        name = result.get("sheet_name") or step.get("input", {}).get("sheet_name")
        if isinstance(name, str) and name.strip():
            completed.add(" ".join(name.split()).casefold())
    for sheet_name in required:
        if " ".join(sheet_name.split()).casefold() not in completed:
            return sheet_name
    return None


def _requested_workbook_file_name(instruction: str) -> str | None:
    """Get an explicit local .xlsx filename without accepting a filesystem path."""
    if not isinstance(instruction, str):
        return None
    match = re.search(
        r"\bsave(?:\s+(?:the|this|your|finished))?(?:\s+workbook)?\s+as\s*:?\s*"
        r"(?:\r?\n\s*)?([^\s\\/:*?\"<>|]+\.xlsx)\b",
        instruction,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else None


def _audit_workbook_formula_errors() -> dict:
    """Read every worksheet for displayed Excel errors before completion."""
    try:
        audit = run_skill("inspect_workbook")
    except Exception as exc:
        return {
            "verified": False,
            "status": "formula_audit_failed",
            "error": str(exc),
            "formula_errors": [],
        }
    if not isinstance(audit, dict):
        return {
            "verified": False,
            "status": "formula_audit_invalid_result",
            "error": "inspect_workbook returned an invalid audit result.",
            "formula_errors": [],
        }
    audit.setdefault("formula_errors", [])
    return audit


def _formula_error_summary(errors: list[dict], limit: int = 12) -> str:
    """Format error coordinates for an actionable repair request."""
    summary = []
    for error in errors[:limit]:
        if not isinstance(error, dict):
            continue
        location = f"{error.get('sheet', 'unknown sheet')}!{error.get('address', '?')}"
        value = error.get("error", "Excel error")
        formula = error.get("formula")
        detail = f"{location} = {value}"
        if isinstance(formula, str) and formula:
            detail += f" ({formula})"
        summary.append(detail)
    return "; ".join(summary) or "The workbook audit reported formula errors without usable coordinates."


def _is_unresolved_workbook_action(step: dict) -> bool:
    """Whether an action left a workbook change unresolved.

    A failed observation (for example, version detection) never changes a
    workbook and should not invalidate verified work.  Likewise, code rejected
    by the AST gate has not executed at all.  Both still appear in the task
    log, but only a change that may be missing or unverified belongs in the
    completion warning.
    """
    if step.get("type") != "action" or step.get("tool_name") in _OBSERVATION_TOOL_NAMES:
        return False
    if step.get("status") == "recovered":
        return False

    result = step.get("result")
    if isinstance(result, dict) and result.get("status") == "rejected_by_sandbox":
        return False

    return (
        step.get("status") in {"failed", "retried", "blocked"}
        or (isinstance(result, dict) and result.get("verified") is False)
    )


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
    action_steps = [
        step for step in task.structured_steps if step.get("type") == "action"
    ]
    failed_or_unresolved = [
        step for step in action_steps if _is_unresolved_workbook_action(step)
    ]
    meaningful_verified_actions = [
        step for step in action_steps
        if step.get("tool_name") not in _OBSERVATION_TOOL_NAMES
        and step.get("status") == "success"
        and isinstance(step.get("result"), dict)
        and step["result"].get("verified") is True
    ]

    # A completion paragraph is not evidence that Excel changed.  This also
    # keeps a text-only Gemini response from being shown above a red failure
    # status, which previously made the user see two contradictory results.
    if task.started_in_execution_mode and not meaningful_verified_actions:
        if action_steps:
            detail = "Xelora did not make a verified workbook change."
        else:
            detail = "The model returned a text-only response without running an Excel tool."
        return (
            "INCOMPLETE: " + detail + " "
            "The requested task was not completed and no workbook result should be relied on."
        )

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
    "take_screenshot", "parse_screen", "inspect_popup", "search_cached_elements",
    "get_active_sheet_name", "verify_current_sheet", "get_sheet_info", "get_cell_value",
    "verify_task_completion", "get_execution_capabilities",
}


_FORMULA_REPAIR_FAILURE_STATUSES = {
    "formula_error",
    "formula_blank_result",
    "formula_not_preserved",
    "fill_down_not_preserved",
}


def _pending_formula_repair_blocks_action(task: AgentTask, tool_name: str, tool_input: dict) -> bool:
    """Whether a failed calculation must be repaired before this write.

    Formula errors are different from a cosmetic failure: a summary or chart
    built on top of one is necessarily untrustworthy. We permit read-only
    inspection and repairs on the affected sheet only; all other writes wait
    for a verified repaired formula and a read-back audit.
    """
    pending = getattr(task, "pending_formula_repair", None)
    if not isinstance(pending, dict) or tool_name in _OBSERVATION_TOOL_NAMES:
        return False
    expected_sheet = str(pending.get("sheet_name") or "").strip().casefold()
    supplied_sheet = str(tool_input.get("sheet_name") or "").strip().casefold()
    return not expected_sheet or supplied_sheet != expected_sheet


def _formula_repair_audit_passed(task: AgentTask, tool_name: str, tool_input: dict, result: dict) -> bool:
    """Clear a formula repair hold only after an explicit, clean read-back."""
    pending = getattr(task, "pending_formula_repair", None)
    if not isinstance(pending, dict) or tool_name != "inspect_workbook":
        return False
    if result.get("verified") is not True or not pending.get("formula_rewritten"):
        return False
    expected_sheet = str(pending.get("sheet_name") or "").strip().casefold()
    supplied_sheet = str(tool_input.get("sheet_name") or "").strip().casefold()
    # A workbook-wide audit has no supplied sheet and is stronger evidence.
    if supplied_sheet and supplied_sheet != expected_sheet:
        return False
    return not result.get("formula_errors") and int(result.get("formula_error_count") or 0) == 0

_VISUAL_SAVE_TOOL_NAMES = {"save_workbook"}


def _is_visual_save_attempt(tool_name: str, tool_input: dict) -> bool:
    """Recognise every visual route that could save before verification."""
    if tool_name in _VISUAL_SAVE_TOOL_NAMES:
        return True
    if tool_name == "execute_excel_shortcut":
        return str(tool_input.get("shortcut_name", "")).strip().lower() in {"save", "save_as"}
    if tool_name == "hotkey":
        keys = tuple(str(key).lower().strip() for key in tool_input.get("keys", []))
        return keys in {("ctrl", "s"), ("control", "s")}
    return False


def _visual_save_is_ready(task: AgentTask) -> bool:
    """Allow the final visual save only after a post-change completion check."""
    latest_change = -1
    for index, step in enumerate(task.structured_steps):
        if step.get("type") != "action":
            continue
        if step.get("tool_name") in _OBSERVATION_TOOL_NAMES | _VISUAL_SAVE_TOOL_NAMES:
            continue
        result = step.get("result")
        if step.get("status") == "success" and isinstance(result, dict) and result.get("verified") is True:
            latest_change = index

    # A user may simply ask Xelora to save an existing workbook.  The ordering
    # guard is for tasks that have already made a verified change.
    if latest_change < 0:
        return True
    if getattr(task, "required_visual_sheet_names", None):
        return _has_post_change_visual_completion_check(task, latest_change)
    return any(
        index > latest_change
        and step.get("type") == "action"
        and step.get("tool_name") == "verify_task_completion"
        and step.get("status") == "success"
        and isinstance(step.get("result"), dict)
        and step["result"].get("verified") is True
        for index, step in enumerate(task.structured_steps)
    )

# Code generation is deliberately not a substitute for skills whose safety
# contract cannot be reproduced in the code runner. In particular, formula
# writes must stay in insert_formula, where capability checks and formula
# verification are enforced. Read-only tools also have no workbook change to
# recover, while VBA and workbook-opening failures normally require user
# configuration or a valid path rather than alternate Python syntax.
_CODEGEN_FALLBACK_EXCLUDED_SKILLS = _OBSERVATION_TOOL_NAMES | {
    "insert_formula",
    "check_vba_access",
    "create_vba_macro",
    "delete_vba_macro",
    "list_vba_macros",
    "run_macro",
    "open_workbook",
    "save_as_macro_enabled",
}

_CODEGEN_FALLBACK_PREFLIGHT_STATUSES = {
    "at_column_reference_blocked",
    "destination_folder_not_found",
    "field_not_found",
    "file_not_found",
    "formula_too_complex",
    "formula_values_require_insert_formula",
    "function_not_available_this_excel_version",
    "invalid_fill_target",
    "invalid_headers",
    "invalid_path",
    "invalid_row_shape",
    "invalid_structured_reference",
    "table_name_used_as_sheet_reference",
    "no_data_found",
    "not_found",
    "refused",
    "spill_area_blocked",
    "trust_not_enabled",
    "whole_column_reference_blocked",
}


def _write_table_input_contains_formula_values(tool_input: dict) -> bool:
    """Prevent formulas from being bulk-written before their Table exists.

    A formula that refers to a Table's calculated column cannot be valid until
    the native Table has been created. Sending hundreds of those formulas in
    the initial value matrix is also a common source of Excel's opaque
    0x800A03EC COM error. Formula writes therefore stay on insert_formula's
    verified path after write_table has created the Table.
    """
    rows = tool_input.get("rows") if isinstance(tool_input, dict) else None
    if not isinstance(rows, list):
        return False
    return any(
        isinstance(value, str) and value.lstrip().startswith("=")
        for row in rows if isinstance(row, list)
        for value in row
    )


def _should_schedule_codegen_fallback(
    tool_name: str,
    result: dict,
    execution_layer: str,
) -> bool:
    """Return whether an unsuccessful skill should get one codegen attempt.

    This is intentionally narrower than "every false result". Bad inputs,
    unsupported Excel features, and protected VBA operations cannot become
    correct merely by running generated code. Operational skill failures
    (for example Excel rejecting a large table write) can often be recovered
    by a more targeted xlwings/COM implementation, so those are escalated.
    """
    if (
        config.VISUAL_ONLY_MODE
        or not config.ENABLE_CODEGEN_LAYER
        or tool_name in _CODEGEN_FALLBACK_EXCLUDED_SKILLS
        or not has_skill(tool_name)
        or not isinstance(result, dict)
        or result.get("verified") is not False
        # A known skill can raise before dispatch returns its normal "skill"
        # layer (for example an Excel COM exception). That is still an
        # eligible skill failure, but unknown/visual dispatch errors are not.
        or execution_layer not in {"skill", "error"}
    ):
        return False

    status = str(result.get("status", "")).strip().lower()
    if status in _CODEGEN_FALLBACK_PREFLIGHT_STATUSES or status.startswith("invalid_"):
        return False
    return True


def _schedule_codegen_fallback(task: AgentTask, tool_name: str, tool_input: dict, result: dict) -> None:
    """Record one forced, traceable fallback without duplicating large inputs."""
    task.pending_codegen_fallback = {
        "tool_name": tool_name,
        "tool_input": tool_input,
    }
    result["codegen_fallback"] = {
        "required": True,
        "failed_skill": tool_name,
        "instruction": (
            "Generate a focused run_excel_code call for the same workbook goal. "
            "Use the original skill arguments already present in the tool-call history; "
            "do not repeat the failed skill first. Include fallback_reason naming this verified "
            "failure, one atomic_goal, alternatives_considered, and a valid reveal_reference for the result."
        ),
    }


def _mark_codegen_fallback_recovered(task: AgentTask, fallback: dict | None) -> None:
    """Resolve only the skill attempt that the successful codegen replaced."""
    if not fallback:
        return
    fallback_name = fallback.get("tool_name")
    fallback_input = fallback.get("tool_input")
    for step in reversed(task.structured_steps):
        if (
            step.get("type") == "action"
            and step.get("tool_name") == fallback_name
            and step.get("status") in {"failed", "retried", "fallback_pending"}
            and step.get("input") == fallback_input
        ):
            step["status"] = "recovered"
            step["recovery_note"] = (
                "The code-generation fallback completed and verified this same workbook goal."
            )
            return


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
    unresolved = [step for step in actions if _is_unresolved_workbook_action(step)]
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
    can_start_excel_session = not (
        task.awaiting_approval and task.defer_excel_until_approval
    )
    if config.VISUAL_ONLY_MODE and can_start_excel_session:
        task.required_visual_sheet_names = _required_visual_sheet_names(task.instruction)
        if (
            not config.ALLOW_VISUAL_STRUCTURED_EDITS
            and _visual_only_requires_structured_workbook_automation(task.instruction)
        ):
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
    if not config.VISUAL_ONLY_MODE and can_start_excel_session:
        # A task that asks for a new workbook must not attach to whichever
        # Excel window happens to be active.  Give it one dedicated startup
        # workbook before planning; a later create_new_workbook call saves
        # that same Book1 instead of creating Book2.
        instruction = task.instruction.lower()
        use_existing = bool(re.search(
            r"\b(existing|open|current|my)\s+(excel\s+)?(workbook|spreadsheet|data)\b"
            r"|\buse\s+(the|this|my)\s+(excel\s+)?(workbook|spreadsheet|data)\b",
            instruction,
        ))
        from skills.excel_shared import bind_workbook_context, start_task_workbook
        if not use_existing and not task.workbook_name:
            workbook = start_task_workbook()
            task.workbook_name = workbook.name
            task.excel_app_pid = workbook.app.pid
        else:
            bind_workbook_context(task.workbook_name, task.excel_app_pid)
        _keep_excel_visible(task)

    excel_version_info = _detect_excel_version_once(task) if can_start_excel_session else None
    workbook_state = _inspect_workbook_state_once(task) if can_start_excel_session else None
    # Inspection is the first reliable source of the active workbook identity.
    # Adopt it before the planner can call codegen, otherwise a subprocess can
    # fall back to an unrelated global xlwings active workbook.
    if isinstance(workbook_state, dict):
        _adopt_workbook_from_result(task, workbook_state, db, db_task_id)
    task.execution_capabilities = build_execution_capabilities()
    system_prompt = build_system_prompt(user_preferences, excel_version_info)
    system_prompt += planning_context(workbook_state, excel_version_info)
    if task.awaiting_approval:
        if task.defer_excel_until_approval:
            system_prompt += (
                "\n\nCURRENT MODE: PLANNING ONLY. The user explicitly required approval before "
                "Excel work begins. Do not open, inspect, or modify Excel and do not call any Excel "
                "tool. Summarize the proposed changes and ask the user to reply Confirm before execution."
            )
        else:
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
                result, execution_layer, generated_code = dispatch_action(
                    tool_name, tool_input, workbook_name=task.workbook_name,
                    excel_app_pid=task.excel_app_pid,
                )
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
                result, execution_layer, generated_code = dispatch_action(
                    tool_name, tool_input, workbook_name=task.workbook_name,
                    excel_app_pid=task.excel_app_pid,
                )
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

        # Progress tracking: detect if agent is stuck
        import time
        current_time = time.time()
        if not hasattr(task, '_last_progress_time'):
            task._last_progress_time = current_time
            task._last_step_count = len(task.structured_steps)
            task._stall_count = 0
        
        # Check if progress has been made since last check
        steps_since_last = len(task.structured_steps) - task._last_step_count
        time_since_last = current_time - task._last_progress_time
        
        if steps_since_last == 0 and time_since_last > 30:
            # No progress in 30 seconds
            task._stall_count += 1
            task.log_step(f"⚠️ No progress for {int(time_since_last)}s (stall #{task._stall_count})")
            
            if task._stall_count >= 3:
                # Stalled 3 times - terminate
                task.log_step("🛑 Agent terminated: stuck in a loop with no progress.")
                task.is_done = True
                task.final_response = "INCOMPLETE: Agent terminated due to lack of progress. The task may require manual intervention."
                task.chat_transcript.append({"role": "assistant", "text": task.final_response})
                break
            
            # Force the model to continue with a reminder
            task.messages.append({
                "role": "user",
                "content": (
                    f"You have not made progress for {int(time_since_last)} seconds. "
                    "You MUST call an actual Excel tool to make changes. "
                    "Do not just describe actions - call the tools to perform them. "
                    "If you are stuck, try: execute_excel_shortcut, go_to_range, or type_text."
                ),
            })
            task._last_progress_time = current_time
            continue
        
        if steps_since_last > 0:
            # Progress was made - reset stall counter
            task._stall_count = 0
            task._last_progress_time = current_time
            task._last_step_count = len(task.structured_steps)

        try:
            active_provider = providers.active_provider_name(task)
            if active_provider == "claude":
                tool_calls, text_blocks, stop_reason = providers.call_claude(task, system_prompt)
            elif active_provider == "openrouter":
                tool_calls, text_blocks, stop_reason = providers.call_openrouter(task, system_prompt)
                # Store assistant message with tool_calls for OpenRouter format
                assistant_content = {"tool_calls": tool_calls} if tool_calls else {}
                if text_blocks:
                    assistant_content["text"] = " ".join(text_blocks)
                task.messages.append({
                    "role": "assistant",
                    "content": assistant_content
                })
            else:
                tool_calls, text_blocks, stop_reason = providers.call_gemini(task, system_prompt)
        except Exception as exc:
            if providers.activate_available_provider_fallback(task, exc):
                # The fallback begins from a clean, provider-neutral user turn
                # and must inspect the persisted live workbook before writing.
                # It therefore cannot replay a half-finished tool call from a
                # provider that has just become unavailable.
                continue
            # The workbook can remain perfectly usable when every configured
            # model is temporarily unavailable. End this run honestly instead
            # of letting the worker crash and leaving the UI at "stopped
            # unexpectedly". No keyboard recovery actions are sent here.
            task.is_done = True
            task.final_response = (
                "INCOMPLETE: Xelora could not reach an AI model to continue this task. "
                f"Reason: {exc}. No additional workbook input was sent after this failure; "
                "retry the task after the model service is available."
            )
            task.log_step(task.final_response)
            task.chat_transcript.append({"role": "assistant", "text": task.final_response})
            break

        for text in text_blocks:
            if text:
                task.log_step(f"🤖 {text}")
                task.structured_steps.append({"type": "reasoning", "text": text})

        if not tool_calls:
            if not text_blocks:
                # An empty provider response is not a decision and never
                # means that the requested Excel work is complete. Providers
                # normally filter this themselves; this guard protects every
                # provider and prevents a blank workbook from being reported
                # as a finished task.
                task.is_done = True
                task.final_response = (
                    "INCOMPLETE: The AI provider returned no action and no response text. "
                    "No workbook change was made. Retry after the model service is available."
                )
                task.log_step(task.final_response)
                task.chat_transcript.append({"role": "assistant", "text": task.final_response})
                break
            if task.awaiting_approval:
                task.is_done = True
                task.final_response = text_blocks[-1] if text_blocks else (
                    "I need to understand the requested workbook change before proceeding. "
                    "Please clarify what you would like changed."
                )
                task.chat_transcript.append({"role": "assistant", "text": task.final_response})
                break
            has_attempted_action = any(step.get("type") == "action" for step in task.structured_steps)
            
            # Check if the model claims to have done more actions than it actually did
            text_response = " ".join(text_blocks).lower() if text_blocks else ""
            claims_actions = any(phrase in text_response for phrase in [
                "i have entered", "i have typed", "i have filled", "i have created",
                "i have added", "i have formatted", "the formula", "the table"
            ])
            
            if claims_actions and has_attempted_action:
                # Model claims actions but didn't call tools - force it to continue
                task.log_step("Model claimed actions without tool calls. Forcing continuation.")
                task.messages.append({
                    "role": "user",
                    "content": (
                        "You described actions but did not call the required Excel tools. "
                        "You MUST call the actual tools to make changes. "
                        "Use execute_excel_shortcut for formatting, fill_formula_down for formulas, "
                        "go_to_range for navigation. Do not just describe what you would do - "
                        "actually call the tools to do it."
                    ),
                })
                continue
            
            if not has_attempted_action and not task.text_only_action_retry_used:
                task.text_only_action_retry_used = True
                task.log_step("The model replied without using Excel. Requesting an inspection before completion.")
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
            required_visual_sheets = list(getattr(task, "required_visual_sheet_names", []) or [])
            # A narrow one-step visual action does not need a workbook-wide
            # screenshot.  A structured multi-sheet workbook build does: it
            # must prove the exact sheet list the user requested before Xelora
            # can report success.
            requires_final_verification = (
                not config.VISUAL_ONLY_MODE or bool(required_visual_sheets)
            )
            verification_tool = (
                "verify_task_completion" if config.VISUAL_ONLY_MODE else "inspect_workbook"
            )
            last_workbook_change = max(
                (index for index, step in enumerate(action_steps)
                 if step.get("tool_name") not in read_only_tools | _VISUAL_SAVE_TOOL_NAMES),
                default=-1,
            )
            if config.VISUAL_ONLY_MODE:
                has_final_inspection = _has_post_change_visual_completion_check(
                    task, last_workbook_change
                )
            else:
                has_final_inspection = any(
                    index > last_workbook_change
                    and step.get("tool_name") == verification_tool
                    and step.get("status") == "success"
                    and isinstance(step.get("result"), dict)
                    and step["result"].get("verified") is True
                    and isinstance(step["result"].get("sheet_reports"), list)
                    for index, step in enumerate(action_steps)
                )
            if (requires_final_verification and has_attempted_action
                    and not has_final_inspection and not task.final_verification_requested):
                task.final_verification_requested = True
                task.log_step("Final verification required: requesting a fresh workbook inspection.")
                if config.VISUAL_ONLY_MODE:
                    required_json = json.dumps(required_visual_sheets)
                    verification_request = (
                        "Before giving a final answer, call verify_task_completion with expected_sheets "
                        f"EXACTLY {required_json}. Do not substitute a partial list such as ['Sheet1']. "
                        "It must confirm every required sheet exists after the final workbook change. "
                        "Fix any missing sheets before trying the check again."
                    )
                else:
                    actual_sheet_names = _live_sheet_names()
                    known_sheets = ", ".join(actual_sheet_names) if actual_sheet_names else "(could not read sheet names)"
                    verification_request = (
                        f"Before giving a final answer, call {verification_tool} with NO sheet_name now as the final "
                        "workbook-wide verification step. It must inspect every worksheet and report all formula errors. "
                        "Compare the live state to every requested deliverable. Fix any gaps you find; if you cannot "
                        "fix them, respond INCOMPLETE with the missing items. "
                        f"The live workbook currently contains only these sheet names: {known_sheets}. "
                        "Never inspect or claim a sheet name outside that exact list."
                    )
                task.messages.append({
                    "role": "user",
                    "content": verification_request,
                })
                continue

            requested_file_name = _requested_workbook_file_name(task.instruction)
            if (
                config.VISUAL_ONLY_MODE
                and requested_file_name
                and has_final_inspection
                and not any(
                    index > last_workbook_change
                    and step.get("tool_name") == "save_workbook"
                    and step.get("status") == "success"
                    and isinstance(step.get("result"), dict)
                    and step["result"].get("verified") is True
                    for index, step in enumerate(action_steps)
                )
                and not task.final_save_requested
            ):
                task.final_save_requested = True
                task.log_step("Final verification passed; requesting the one required named workbook save.")
                task.messages.append({
                    "role": "user",
                    "content": (
                        "The required completion check passed. Now call save_workbook exactly once with "
                        f"file_name='{requested_file_name}'. Do not use Save As, Ctrl+S, or any other save route."
                    ),
                })
                continue

            formula_audit = None
            formula_errors = []
            if requires_final_verification and has_attempted_action and has_final_inspection:
                formula_audit = _audit_workbook_formula_errors()
                task.last_formula_error_audit = formula_audit
                task.structured_steps.append({
                    "type": "formula_audit",
                    "result": formula_audit,
                    "status": "success" if formula_audit.get("verified") is True else "failed",
                })
                formula_errors = [
                    error for error in formula_audit.get("formula_errors", [])
                    if isinstance(error, dict)
                ]
                if formula_errors and not task.formula_error_repair_requested:
                    task.formula_error_repair_requested = True
                    error_summary = _formula_error_summary(formula_errors)
                    task.log_step(
                        f"Formula audit found {len(formula_errors)} Excel error(s); requesting repair before completion."
                    )
                    task.messages.append({
                        "role": "user",
                        "content": (
                            "The automatic workbook-wide formula audit found Excel errors. Do not finish. "
                            "Inspect the affected sheets, correct each formula with insert_formula (never codegen), "
                            "then call inspect_workbook with NO sheet_name again. Errors: "
                            + error_summary
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
            elif formula_audit is not None and formula_audit.get("verified") is not True:
                final_text = (
                    "INCOMPLETE: Xelora could not complete its workbook-wide formula-error audit, "
                    "so the workbook cannot be verified.\n\n" + final_text
                )
            elif formula_errors:
                final_text = (
                    "INCOMPLETE: the workbook still contains Excel formula errors: "
                    + _formula_error_summary(formula_errors)
                    + ".\n\n" + final_text
                )
            task.final_response = _build_final_response_reality_check(task, final_text)
            task.chat_transcript.append({"role": "assistant", "text": task.final_response})

            unresolved = [
                step for step in task.structured_steps if _is_unresolved_workbook_action(step)
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

        for tool_call in _order_tool_calls_by_sheet_dependency(tool_calls):
            if task.is_paused:
                task.log_step("Task paused before the next workbook action.")
                break
            # Handle both object (Gemini/Claude) and dict (OpenRouter) formats
            tool_name = tool_call.name if hasattr(tool_call, 'name') else tool_call.get('name', '')
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

            if _pending_formula_repair_blocks_action(task, tool_name, tool_input):
                pending = task.pending_formula_repair or {}
                result = {
                    "verified": False,
                    "status": "formula_repair_required",
                    "error": (
                        f"Formula verification failed on '{pending.get('sheet_name')}' "
                        f"at {pending.get('cell')}. Do not create or edit another worksheet yet. "
                        "Inspect the affected sheet, repair the formula or its source data there, "
                        "then run inspect_workbook to confirm it has no Excel formula errors."
                    ),
                    "failed_formula": pending,
                }
                task.log_step(
                    f"Blocked {tool_name}: formula repair is still required on "
                    f"{pending.get('sheet_name')} before dependent work can continue."
                )
                task.structured_steps.append({
                    "type": "action", "tool_name": tool_name, "execution_layer": "formula_repair_guard",
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

            # A failed workbook action may leave Excel in an unknown partial
            # state. Until that state is read back, do not let a later tool
            # call write elsewhere in the workbook merely because the model
            # continued generating calls. The read-only inspection itself is
            # still allowed so the task can recover rather than looking stuck.
            active_recovery = task.recovery_state or {}
            if (
                active_recovery.get("phase") in {"inspecting_failure", "retry_pending"}
                and tool_name not in _OBSERVATION_TOOL_NAMES
            ):
                task.recovery_guard_block_count += 1
                result = {
                    "verified": False,
                    "status": "recovery_inspection_required",
                    "error": (
                        "The prior Excel action was not verified. Inspect the workbook or popup "
                        "state before attempting another workbook change."
                    ),
                    "blocked_action": tool_name,
                }
                task.log_step(
                    f"Recovery guard blocked {tool_name}; waiting for a read-only workbook or popup inspection."
                )
                task.structured_steps.append({
                    "type": "action", "tool_name": tool_name, "execution_layer": "recovery_guard",
                    "input": tool_input, "result": result, "status": "blocked",
                })
                providers.submit_tool_result(task, tool_call, result)
                if task.recovery_guard_block_count >= 2:
                    task.set_recovery_state(
                        "needs_user_action",
                        "Recovery stopped: the model did not request the required workbook inspection, so Xelora will not keep retrying blocked Excel writes.",
                        tool_name=active_recovery.get("tool_name"),
                        safe_to_continue=False,
                    )
                    task.is_done = True
                    task.final_response = (
                        "INCOMPLETE: Xelora stopped after the model repeatedly skipped the required "
                        "read-only workbook inspection following an unverified Excel action."
                    )
                    task.chat_transcript.append({"role": "assistant", "text": task.final_response})
                continue

            if config.VISUAL_ONLY_MODE and tool_name == "verify_task_completion":
                required_sheets = list(getattr(task, "required_visual_sheet_names", []) or [])
                supplied_sheets = tool_input.get("expected_sheets")
                if (
                    required_sheets
                    and _normalised_sheet_names(supplied_sheets) != _normalised_sheet_names(required_sheets)
                ):
                    result = {
                        "verified": False,
                        "status": "required_sheet_verification_mismatch",
                        "error": (
                            "This structured workbook must be verified against the exact requested sheet list: "
                            + json.dumps(required_sheets)
                            + ". Do not verify a partial or substituted list."
                        ),
                        "required_sheets": required_sheets,
                    }
                    task.log_step("Blocked a partial worksheet-completion check.")
                    task.structured_steps.append({
                        "type": "action", "tool_name": tool_name,
                        "execution_layer": "required_sheet_verification_guard",
                        "input": tool_input, "result": result, "status": "blocked",
                    })
                    providers.submit_tool_result(task, tool_call, result)
                    continue

            if config.VISUAL_ONLY_MODE and tool_name == "create_sheet":
                next_required_sheet = _next_required_visual_sheet(task)
                supplied_sheet_name = " ".join(str(tool_input.get("sheet_name", "")).split())
                if (
                    next_required_sheet
                    and supplied_sheet_name.casefold() != next_required_sheet.casefold()
                ):
                    result = {
                        "verified": False,
                        "status": "worksheet_order_guard",
                        "error": (
                            f"Do not create '{supplied_sheet_name or 'an unnamed sheet'}' yet. "
                            f"First create and verify the required worksheet '{next_required_sheet}'. "
                            "Do not move to a later sheet after a sheet-creation failure."
                        ),
                        "next_required_sheet": next_required_sheet,
                    }
                    task.log_step(
                        f"Blocked out-of-order worksheet creation; '{next_required_sheet}' is not verified yet."
                    )
                    task.structured_steps.append({
                        "type": "action", "tool_name": tool_name,
                        "execution_layer": "worksheet_order_guard",
                        "input": tool_input, "result": result, "status": "blocked",
                    })
                    providers.submit_tool_result(task, tool_call, result)
                    continue

            if config.VISUAL_ONLY_MODE and _is_visual_save_attempt(tool_name, tool_input):
                required_file_name = _requested_workbook_file_name(task.instruction)
                supplied_file_name = str(tool_input.get("file_name", "")).strip()
                if required_file_name and supplied_file_name.casefold() != required_file_name.casefold():
                    result = {
                        "verified": False,
                        "status": "required_filename_mismatch",
                        "error": (
                            f"The user requested the final filename '{required_file_name}'. "
                            "Use save_workbook with that exact file_name after completion verification."
                        ),
                    }
                    task.log_step("Blocked a save that did not use the requested filename.")
                    task.structured_steps.append({
                        "type": "action", "tool_name": tool_name,
                        "execution_layer": "required_filename_guard",
                        "input": tool_input, "result": result, "status": "blocked",
                    })
                    providers.submit_tool_result(task, tool_call, result)
                    continue

            if (
                config.VISUAL_ONLY_MODE
                and _is_visual_save_attempt(tool_name, tool_input)
                and not _visual_save_is_ready(task)
            ):
                result = {
                    "verified": False,
                    "status": "save_deferred_until_verification",
                    "error": (
                        "Do not save yet. Complete all requested work, then call "
                        "verify_task_completion after the last workbook change before the one final save_workbook call."
                    ),
                }
                task.log_step("Blocked an early save; final workbook verification is still required.")
                task.structured_steps.append({
                    "type": "action", "tool_name": tool_name, "execution_layer": "save_order_guard",
                    "input": tool_input, "result": result, "status": "blocked",
                })
                providers.submit_tool_result(task, tool_call, result)
                continue

            if not config.VISUAL_ONLY_MODE and tool_name not in VISUAL_TOOL_NAMES:
                _show_target_in_excel(task, tool_name, tool_input)

            task.log_step(f"⏳ Running: {tool_name} {tool_input}")

            try:
                from vision.ui_control import handle_blocking_dialogs, _get_agent_excel_window
                try:
                    win = _get_agent_excel_window()
                    pre_check = {"status": "clean"}
                    if win and win.handle:
                        pre_check = handle_blocking_dialogs(win.handle)
                        if pre_check.get("status") == "handled":
                            task.log_step("Safely dismissed a classified stale Excel dialog before the next action.")
                        elif pre_check.get("status") in {"popup_requires_workflow", "popup_requires_attention"}:
                            task.log_step(
                                "Excel popup identified before the next action: "
                                + json.dumps(pre_check.get("popups", []), default=str)[:900]
                            )
                except Exception:
                    pre_check = {"status": "clean"}

                popup_actions = {"inspect_popup", "parse_screen", "click_popup_button", "click_popup_control", "set_popup_text", "save_workbook"}
                is_table_completion = (
                    tool_name in {"execute_excel_shortcut", "press_shortcut"}
                    and str(tool_input.get("shortcut_name", "")).strip().lower() == "insert_table"
                )
                complete_delayed_table = _has_pending_create_table_completion(
                    task, pre_check.get("popups", [])
                )
                if complete_delayed_table:
                    from vision import ui_control
                    task.log_step(
                        "Completing the valid Create Table dialog that this task opened after Excel exposed it late."
                    )
                    result = ui_control.create_excel_table()
                    execution_layer, generated_code = "visual_popup_recovery", None
                elif (
                    pre_check.get("status") in {"popup_requires_workflow", "popup_requires_attention"}
                    and tool_name not in popup_actions
                    and not is_table_completion
                ):
                    result = {
                        "verified": False,
                        "status": "popup_gate",
                        "error": (
                            "A classified Excel popup is open. Inspect it and use click_popup_button "
                            "with one visible, policy-approved label before resuming worksheet input. "
                            "If its title is Create Table, click its exact visible OK button; do not send Enter, "
                            "Escape, or find_and_click."
                        ),
                        "popups": pre_check.get("popups", []),
                    }
                    execution_layer, generated_code = "popup_gate", None
                else:
                    result, execution_layer, generated_code = dispatch_action(
                        tool_name, tool_input, workbook_name=task.workbook_name,
                        excel_app_pid=task.excel_app_pid,
                    )
                status = "success"
                is_failure = isinstance(result, dict) and result.get("verified") is False

                if is_failure and _HAS_WINDOW_SAFETY:
                    try:
                        win = _get_agent_excel_window()
                        if win and win.handle:
                            post_check = handle_blocking_dialogs(win.handle)
                            if post_check.get("status") == "handled":
                                task.log_step("Safely dismissed a classified Excel error after the action.")
                                result["interceptor_note"] = "A classified stale Excel dialog was dismissed after the action."
                            elif post_check.get("status") in {"popup_requires_workflow", "popup_requires_attention"}:
                                result["popup_note"] = post_check.get("popups", [])
                    except Exception:
                        pass

            except Exception as e:
                result = {"error": str(e), "verified": False}
                execution_layer, generated_code = "error", None
                status = "success"  # placeholder, corrected by the shared block below
                is_failure = True

            fallback_being_executed = (
                task.pending_codegen_fallback
                if tool_name == "run_excel_code"
                else None
            )

            if is_failure:
                _adopt_recovered_workbook_identity(task, result, db, db_task_id)
                if (
                    tool_name == "insert_formula"
                    and isinstance(result, dict)
                    and result.get("status") in _FORMULA_REPAIR_FAILURE_STATUSES
                ):
                    task.pending_formula_repair = {
                        "sheet_name": tool_input.get("sheet_name"),
                        "cell": tool_input.get("cell"),
                        "formula": tool_input.get("formula"),
                        "status": result.get("status"),
                        "formula_rewritten": False,
                    }
                    task.log_step(
                        "Formula verification failed; downstream worksheet changes are paused until "
                        f"'{tool_input.get('sheet_name')}' is repaired and audited."
                    )
                result.setdefault(
                    "recovery_options",
                    recovery_options(tool_name, execution_layer, result),
                )
                task.log_step(f"⚠️ Not verified: {tool_name} -> {result.get('verification_note', result.get('error', 'no details'))}")
                task.set_recovery_state(
                    "inspecting_failure",
                    "Recovering safely: Excel changes are paused while Xelora checks the failed action and selects a verified next step.",
                    tool_name=tool_name,
                    safe_to_continue=False,
                )
                workbook_lost = _is_lost_task_workbook(result)
                if workbook_lost:
                    status = "failed"
                    task.set_recovery_state(
                        "needs_user_action",
                        "Recovery stopped: the Excel window bound to this task is no longer available. Keep the intended workbook open, then start a new task.",
                        tool_name=tool_name,
                        safe_to_continue=False,
                    )
                    task.log_step(
                        "Excel window lost. Stopping this task without sending recovery shortcuts or opening another workbook."
                    )
                elif _should_schedule_codegen_fallback(tool_name, result, execution_layer):
                    _schedule_codegen_fallback(task, tool_name, tool_input, result)
                    status = "fallback_pending"
                    task.set_recovery_state(
                        "fallback_pending",
                        "Recovering safely: the original action was not verified. Xelora will try one focused alternative and verify the workbook before continuing.",
                        tool_name=tool_name,
                        safe_to_continue=False,
                    )
                    task.log_step(
                        f"🧩 Skill '{tool_name}' could not verify the change; "
                        "escalating this same goal to code generation."
                    )
                else:
                    retry_key = _action_recovery_key(tool_name, tool_input) or action_signature
                    retries_so_far = task.retry_counts.get(retry_key, 0)
                    if retries_so_far < config.MAX_RETRIES_PER_ACTION:
                        task.retry_counts[retry_key] = retries_so_far + 1
                        status = "retried"
                        task.set_recovery_state(
                            "retry_pending",
                            "Recovering safely: Xelora is reviewing the workbook result before deciding whether one compatible retry is safe.",
                            tool_name=tool_name,
                            safe_to_continue=False,
                        )
                        task.log_step(f"🔁 Letting the AI decide whether to retry (attempt {retries_so_far + 1}).")
                    else:
                        status = "failed"
                        task.set_recovery_state(
                            "needs_user_action",
                            "Recovery stopped: this action could not be verified after the allowed attempts. Xelora will not continue dependent Excel changes blindly.",
                            tool_name=tool_name,
                            safe_to_continue=False,
                        )
                        task.log_step(f"❌ Giving up on {tool_name} after {config.MAX_RETRIES_PER_ACTION} attempts.")
            else:
                task.log_step(f"✅ Done: {tool_name} ({execution_layer}) -> {result}")

                pending = getattr(task, "pending_formula_repair", None)
                if (
                    isinstance(pending, dict)
                    and tool_name == "insert_formula"
                    and str(tool_input.get("sheet_name") or "").strip().casefold()
                    == str(pending.get("sheet_name") or "").strip().casefold()
                ):
                    pending["formula_rewritten"] = True
                    task.log_step(
                        "Formula repair was written. A clean workbook inspection is still required "
                        "before work can move to another sheet."
                    )
                if _formula_repair_audit_passed(task, tool_name, tool_input, result):
                    task.pending_formula_repair = None
                    task.log_step("Formula repair audit passed; dependent workbook work may continue.")

            task.structured_steps.append({
                "type": "action", "tool_name": tool_name, "execution_layer": execution_layer,
                "input": tool_input, "result": result, "status": status,
            })

            if status == "success" and isinstance(result, dict) and result.get("verified") is True:
                if fallback_being_executed:
                    _mark_codegen_fallback_recovered(task, fallback_being_executed)
                    task.clear_recovery_state(
                        "A focused alternative completed and the workbook change was verified."
                    )
                elif task.recovery_state and task.recovery_state.get("phase") in {
                    "inspecting_failure", "retry_pending"
                } and tool_name in _OBSERVATION_TOOL_NAMES:
                    task.recovery_guard_block_count = 0
                    task.set_recovery_state(
                        "alternative_selection",
                        "Recovery check complete: Xelora has current workbook evidence and is selecting one compatible next step.",
                        tool_name=task.recovery_state.get("tool_name"),
                        safe_to_continue=False,
                    )
                elif task.recovery_state and task.recovery_state.get("phase") == "alternative_selection":
                    task.clear_recovery_state(
                        "The alternate action completed and its workbook result was verified."
                    )
                _mark_prior_action_recovered(task, tool_name, tool_input)
                _adopt_workbook_from_result(task, result, db, db_task_id)
                if tool_name not in _OBSERVATION_TOOL_NAMES:
                    task.successful_action_signatures.add(action_signature)
                if tool_name not in _OBSERVATION_TOOL_NAMES | _VISUAL_SAVE_TOOL_NAMES:
                    # Any verified edit invalidates an earlier completion
                    # check. A later final response must obtain fresh proof.
                    task.final_verification_requested = False
                    task.final_save_requested = False
                _keep_excel_visible(task)
                _show_verified_result_in_excel(task, tool_name, tool_input, result)
                _capture_visual_checkpoint(task, tool_name)

            if config.VISUAL_ONLY_MODE and status == "success" and tool_name not in READ_ONLY_TOOL_NAMES:
                task.successful_visual_actions.add(action_signature)

            if db is not None and db_task_id is not None:
                _log_action_to_db(db, db_task_id, tool_name, tool_input, execution_layer, generated_code, result, status)

            providers.submit_tool_result(task, tool_call, result)

            if is_failure and _is_lost_task_workbook(result):
                task.is_done = True
                task.final_response = (
                    "INCOMPLETE: The workbook bound to this task became unavailable. "
                    "Xelora stopped safely and did not try another workbook, code generation, or shortcuts. "
                    "Keep the intended workbook open, then start a new task."
                )
                task.chat_transcript.append({"role": "assistant", "text": task.final_response})
                break

            # The fallback is a one-shot recovery attempt. A successful
            # attempt marks the original skill recovered above; a failed one
            # remains visibly unresolved rather than trapping the task in an
            # endless forced-codegen loop.
            if fallback_being_executed:
                task.pending_codegen_fallback = None

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

    # Post-task verification using vision
    if task.is_done and config.VISUAL_ONLY_MODE:
        try:
            from vision.task_verifier import verify_excel_task
            task.log_step("🔍 Running post-task verification...")
            verification = verify_excel_task(task.instruction)
            
            if verification.get("overall_status") == "verified":
                task.log_step("✅ Visible Excel end-state evidence collected.")
            else:
                retry_suggestion = verification.get("retry_suggestion", "Unknown issue")
                task.log_step(f"⚠️ Verification found issues: {retry_suggestion}")
                # Don't mark as failed - just log the issues
        except Exception as e:
            task.log_step(f"⚠️ Verification skipped: {e}")

    return task
