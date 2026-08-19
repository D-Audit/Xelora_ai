"""
agent/core.py
The brain of the system. Goal -> Planning -> Execution -> Verification
-> Correction -> Completion, dispatching each action to one of three
layers: skill library, code generation, or visual fallback.
"""

import concurrent.futures
import json
import os
from datetime import datetime, timezone

import config
from skills.registry import has_skill, run_skill
from codegen.executor import run_generated_code
from agent import providers
from agent.prompts import build_system_prompt

VISUAL_TOOL_NAMES = {"take_screenshot", "parse_screen", "click", "double_click", "type_text", "press_key", "hotkey", "scroll"}
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
        self.awaiting_approval = True

    def pause(self):
        self.is_paused = True

    def resume(self, correction: str = None):
        self.is_paused = False
        self.is_done = False
        self.final_response = None
        if correction:
            if self.awaiting_approval and _is_explicit_approval(correction):
                self.awaiting_approval = False
            self.messages.append({"role": "user", "content": correction})
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


def dispatch_action(tool_name: str, tool_input: dict):
    if config.VISUAL_ONLY_MODE:
        if tool_name not in VISUAL_TOOL_NAMES:
            return {"error": "VISUAL_ONLY_MODE blocks Excel API and code-generation tools.", "verified": False}, "blocked", None
        from vision import ui_control
        return getattr(ui_control, tool_name)(**tool_input), "visual", None

    if has_skill(tool_name):
        return _run_skill_with_timeout(tool_name, tool_input), "skill", None

    if tool_name == "run_excel_code":
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
        name = step.get("tool_name", "unknown")
        if name not in failed_names:
            failed_names.append(name)

    warning = (
        "⚠️ VERIFIED STATUS CHECK: this task had unresolved problems. The following actions "
        f"did not complete successfully: {', '.join(failed_names)}. Only {len(attempted_tools)} "
        f"distinct tool(s) were actually attempted this run. Do not treat the summary below as "
        f"fully complete - check your workbook directly before relying on it.\n\n"
    )
    return warning + ai_final_text


def run_task(task: AgentTask, db=None, db_task_id: int = None, user_preferences: dict = None):
    excel_version_info = _detect_excel_version_once(task)
    system_prompt = build_system_prompt(user_preferences, excel_version_info)
    if task.awaiting_approval:
        system_prompt += (
            "\n\nCURRENT MODE: PLANNING ONLY. You may use only read-only workbook tools "
            "to understand the request and workbook. Do not change Excel. Summarize the "
            "proposed changes and ask the user to reply Confirm before execution."
        )
    else:
        system_prompt += "\n\nCURRENT MODE: EXECUTION APPROVED. Apply only the plan the user confirmed."
    steps_taken = 0

    if not config.VISUAL_ONLY_MODE:
        from skills.excel_shared import bind_workbook_context
        bind_workbook_context(task.workbook_name)

    from knowledge.rag import bind_user_context
    bind_user_context(task.user_id)

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
            verification_tool = "parse_screen" if config.VISUAL_ONLY_MODE else "inspect_workbook"
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
            if has_attempted_action and not has_final_inspection and not task.final_verification_requested:
                task.final_verification_requested = True
                task.log_step("Final verification required: requesting a fresh workbook inspection.")
                task.messages.append({
                    "role": "user",
                    "content": (
                        f"Before giving a final answer, call {verification_tool} now as the final verification "
                        "step. Compare the live state to every requested deliverable. Fix any gaps you "
                        "find; if you cannot fix them, respond INCOMPLETE with the missing items."
                    ),
                })
                continue
            task.is_done = True
            final_text = text_blocks[-1] if text_blocks else "Task complete."
            if has_attempted_action and not has_final_inspection:
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
            tool_name = tool_call.name
            tool_input = dict(tool_call.input) if config.AI_PROVIDER == "claude" else providers.gemini_tool_input(tool_call)

            if task.awaiting_approval and tool_name not in READ_ONLY_TOOL_NAMES:
                result = {
                    "verified": False,
                    "error": "Workbook changes are locked until the user explicitly confirms the proposed plan.",
                }
                task.structured_steps.append({
                    "type": "action", "tool_name": tool_name, "execution_layer": "approval_gate",
                    "input": tool_input, "result": result, "status": "blocked",
                })
                if config.AI_PROVIDER == "claude":
                    providers.submit_claude_tool_result(task, tool_call, result)
                else:
                    providers.submit_gemini_tool_result(task, tool_call, result)
                continue

            task.log_step(f"⏳ Running: {tool_name} {tool_input}")

            # Make the in-flight action observable before the potentially slow
            # Excel call begins. The same dictionary is updated on completion,
            # so progress readers see a clean running -> terminal transition.
            action_step = {
                "type": "action", "tool_name": tool_name,
                "execution_layer": "dispatching", "input": tool_input,
                "result": None, "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            task.structured_steps.append(action_step)

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

            action_step.update({
                "execution_layer": execution_layer, "result": result, "status": status,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })

            if db is not None and db_task_id is not None:
                _log_action_to_db(db, db_task_id, tool_name, tool_input, execution_layer, generated_code, result, status)

            if config.AI_PROVIDER == "claude":
                providers.submit_claude_tool_result(task, tool_call, result)
            else:
                providers.submit_gemini_tool_result(task, tool_call, result)

        steps_taken += 1

    return task
