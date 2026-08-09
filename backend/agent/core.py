"""
agent/core.py
"""

import concurrent.futures
import json
import os

import config
from skills.registry import has_skill, run_skill
from codegen.executor import run_generated_code
from agent import providers
from agent.prompts import build_system_prompt

VISUAL_TOOL_NAMES = {"screenshot_active_window", "click_at", "type_text", "press_key"}

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKILL_TIMEOUT_SECONDS = 15


def _run_skill_with_timeout(tool_name: str, tool_input: dict, timeout: int = SKILL_TIMEOUT_SECONDS):
    """On timeout: attempts ONE recovery via force_restart_excel_and_reopen,
    which itself now enforces a per-task restart cap and a real
    responsiveness check (see excel_shared.py). If recovery itself raises
    (cap exceeded, or the new instance never became responsive), that
    failure is returned as a clear, final message - not another silent
    retry loop."""
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = ex.submit(run_skill, tool_name, **tool_input)
    timed_out = False
    try:
        result = future.result(timeout=timeout)
        from skills.excel_shared import save_active_workbook_best_effort
        save_active_workbook_best_effort()
        return result
    except concurrent.futures.TimeoutError:
        timed_out = True
        future.cancel()

        from skills.excel_shared import force_restart_excel_and_reopen
        try:
            _, killed_note = force_restart_excel_and_reopen()
            return {
                "error": f"'{tool_name}' timed out after {timeout}s. {killed_note} Excel is "
                         f"responsive again. Actions since the last successful save may need "
                         f"to be redone - do not simply retry the exact same call if it "
                         f"involved a complex formula; simplify it first.",
                "verified": False,
                "status": "timeout_recovered",
            }
        except RuntimeError as recovery_error:
            return {
                "error": f"'{tool_name}' timed out, AND automatic recovery failed: "
                         f"{recovery_error}",
                "verified": False,
                "status": "unrecoverable",
            }
    finally:
        ex.shutdown(wait=not timed_out, cancel_futures=True)


_EXCEL_ACTION_TERMS = (
    "add", "apply", "build", "calculate", "clean", "create", "delete", "edit", "filter",
    "format", "insert", "make", "move", "organize", "remove", "rename", "replace", "sort",
    "summarize", "update", "write", "formula", "pivot", "chart", "graph", "table", "column",
    "row", "cell", "sheet", "worksheet", "workbook", "spreadsheet", "data", "duplicate",
)


def is_excel_action_request(instruction: str) -> bool:
    """Only allow the execution loop for a clear workbook instruction.

    The chat is also used for greetings, questions, and planning. Those messages
    must never open, inspect, or modify Excel merely because an agent task was
    created for them.
    """
    text = " ".join((instruction or "").lower().split())
    if not text:
        return False
    if text.startswith(("how do ", "how can ", "what is ", "what are ", "can you explain", "tell me about")):
        return False
    return any(term in text for term in _EXCEL_ACTION_TERMS)


def conversational_response(instruction: str) -> str:
    text = " ".join((instruction or "").strip().split())
    if text.lower() in {"hi", "hello", "hey", "hey there", "good morning", "good afternoon", "good evening"}:
        return "Hi — I’m ready when you are. Tell me what you’d like to change, analyse, or create in your workbook."
    return (
        "I can help with that without changing your workbook. "
        "When you want an Excel action, tell me the specific change you want made—for example, “remove duplicate rows” or “create a sales chart.”"
    )


class AgentTask:
    def __init__(self, instruction: str, user_id: int = None, workbook_name: str = None):
        self.instruction = instruction
        self.user_id = user_id
        self.workbook_name = workbook_name
        self.messages = [{"role": "user", "content": instruction}]
        self.is_paused = False
        self.is_done = False
        self.final_response = None
        self.progress_log = []
        self.structured_steps = []
        self.retry_counts = {}
        self.gemini_model_index = 0

    def pause(self):
        self.is_paused = True

    def resume(self, correction: str = None):
        self.is_paused = False
        if correction:
            self.messages.append({"role": "user", "content": correction})

    def log_step(self, message: str):
        self.progress_log.append(message)
        print(message)


def dispatch_action(tool_name: str, tool_input: dict):
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


def _restore_calculation_mode_safety_net():
    try:
        from skills.excel_shared import get_active_workbook, set_calculation_mode
        wb = get_active_workbook()
        set_calculation_mode(wb.app, "automatic")
    except Exception:
        pass


def run_task(task: AgentTask, db=None, db_task_id: int = None, user_preferences: dict = None):
    if not is_excel_action_request(task.instruction):
        task.final_response = conversational_response(task.instruction)
        task.structured_steps.append({"type": "reasoning", "text": "No workbook action requested; replied without accessing Excel."})
        task.log_step("No workbook action requested. Replied without accessing Excel.")
        task.is_done = True
        return task

    system_prompt = build_system_prompt(user_preferences)
    steps_taken = 0

    from skills.excel_shared import bind_workbook_context
    bind_workbook_context(task.workbook_name)

    from knowledge.rag import bind_user_context
    bind_user_context(task.user_id)

    while not task.is_done and not task.is_paused:
        if steps_taken >= config.MAX_STEPS_PER_TASK:
            task.log_step("⚠️ Reached the maximum number of steps for this task. Stopping for safety.")
            task.is_done = True
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
            final_text = "\n\n".join(text.strip() for text in text_blocks if text and text.strip())
            if final_text:
                task.final_response = final_text
            task.is_done = True
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
                task.log_step("⚠️ Task stopped with unresolved failures: " + ", ".join(failed_names) + ". Do not treat this run as fully complete.")
            else:
                task.log_step("✅ Task complete.")
            break

        for tool_call in tool_calls:
            tool_name = tool_call.name
            tool_input = dict(tool_call.input) if config.AI_PROVIDER == "claude" else providers.gemini_tool_input(tool_call)

            task.log_step(f"⏳ Running: {tool_name} {tool_input}")

            try:
                result, execution_layer, generated_code = dispatch_action(tool_name, tool_input)
                status = "success"

                if isinstance(result, dict) and result.get("verified") is False:
                    task.log_step(f"⚠️ Not verified: {tool_name} -> {result.get('verification_note', result.get('error', 'no details'))}")
                    if result.get("status") == "unrecoverable":
                        status = "failed"
                        task.log_step(f"🛑 Auto-recovery gave up on {tool_name} - manual intervention needed.")
                    else:
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

            except Exception as e:
                result = {"error": str(e), "verified": False}
                execution_layer, generated_code, status = "error", None, "failed"
                task.log_step(f"❌ Failed: {tool_name} -> {e}")

            task.structured_steps.append({
                "type": "action", "tool_name": tool_name, "execution_layer": execution_layer,
                "input": tool_input, "result": result, "status": status,
            })

            if db is not None and db_task_id is not None:
                _log_action_to_db(db, db_task_id, tool_name, tool_input, execution_layer, generated_code, result, status)

            if config.AI_PROVIDER == "claude":
                providers.submit_claude_tool_result(task, tool_call, result)
            else:
                providers.submit_gemini_tool_result(task, tool_call, result)

        steps_taken += 1

    _restore_calculation_mode_safety_net()
    return task
