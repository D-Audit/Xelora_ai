"""local_agent.py - the Xelora Desktop local agent.

Runs on the user's Windows PC next to Excel (Xelora Desktop starts it; it
can also be run by hand) and executes that user's tasks from the cloud API:

    python local_agent.py --api-url https://xelora-api.onrender.com --token xa_...

or with XELORA_API_URL / XELORA_AGENT_TOKEN in the environment.

Loop: claim a job (long poll) -> rebuild the AgentTask from the job's state ->
sync the user's cloud files into the local workspace -> run_task() locally
against Excel -> push progress every second -> upload changed files, record
what the task learned (in the user's cloud memory) -> push the final state.
Model calls go through the cloud's relay with this agent's token, so no
provider key is needed (or stored) on this PC.

Exit codes: 0 stopped, 2 bad arguments, 3 token rejected (pair again).
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

PUSH_INTERVAL_SECONDS = 1.0
CLAIM_HTTP_TIMEOUT_SECONDS = 40
MAX_BACKOFF_SECONDS = 30
EXIT_TOKEN_REJECTED = 3


class TokenRejected(Exception):
    pass


def _local_app_dir() -> str:
    base = os.getenv("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "Xelora")


def default_workspace_dir() -> str:
    return os.path.join(_local_app_dir(), "workspace")


def default_data_dir() -> str:
    """Writable home for the agent's runtime data (knowledge index, memory,
    reports, checkpoints). The install directory - typically under Program
    Files - is read-only for the user, so nothing may be written next to the code."""
    return os.path.join(_local_app_dir(), "data")


def configure_environment(api_url: str, token: str, workspace_dir: str | None = None) -> None:
    """Point the backend's config at the relay. Must run before importing config."""
    relay = f"{api_url.rstrip('/')}/agent-link/llm"
    os.environ.update({
        "ANTHROPIC_API_KEY": token,
        "GEMINI_API_KEY": token,
        "OPENROUTER_API_KEY": token,
        "ANTHROPIC_BASE_URL": f"{relay}/anthropic",
        "GEMINI_BASE_URL": f"{relay}/gemini",
        "OPENROUTER_BASE_URL": f"{relay}/openrouter",
        # Tasks run right here; nothing local is persisted to a database.
        "TASK_EXECUTION": "server",
        "DATABASE_URL": "",
        # Local mirror of the user's cloud files (see agent_workspace.py).
        "STORAGE_DIR": workspace_dir or os.getenv("XELORA_WORKSPACE_DIR") or default_workspace_dir(),
    })
    os.environ.setdefault("XELORA_DATA_DIR", default_data_dir())
    os.environ.setdefault("JWT_SECRET_KEY", "local-agent-does-not-issue-tokens")
    driver = bundled_cua_driver()
    if driver:
        # Xelora Desktop ships the Cua Driver beside the backend: turn on
        # accessibility-based desktop control unless the user opted out.
        os.environ.setdefault("ENABLE_CUA_DRIVER", "true")
        os.environ.setdefault("CUA_DRIVER_COMMAND", driver)


def bundled_cua_driver() -> str | None:
    """Path of the Cua Driver shipped in the desktop install (agent/cua/)."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cua", "cua-driver.exe")
    return path if os.path.isfile(path) else None


def cua_driver_status() -> str:
    """One log line saying whether Cua desktop control is usable on this PC."""
    try:
        from vision.cua_driver import health_check
        health = health_check(force_refresh=True)
    except Exception as exc:
        return f"Cua desktop control unavailable: {exc}"
    if health.get("status") == "ready":
        return f"Cua desktop control ready ({health.get('version') or 'cua-driver'}, {health.get('tool_count')} tools)"
    if health.get("status") == "disabled":
        return "Cua desktop control off"
    return "Cua desktop control unavailable: " + "; ".join(health.get("errors") or ["not reachable"])


def excel_engine_status() -> str:
    """One log line saying whether Excel automation is usable on this PC."""
    try:
        from skills.excel_shared import require_excel_engine
        require_excel_engine()
    except Exception as exc:
        return f"Excel automation unavailable: {exc}"
    return "Excel automation ready"


class CloudClient:
    """Thin HTTP client for /agent-link. ``http`` is any requests-like object."""

    def __init__(self, api_url: str, token: str, http=None):
        import requests

        self.base = api_url.rstrip("/")
        self.headers = {"X-Agent-Token": token}
        self.http = http or requests.Session()

    def _send(self, method: str, path: str, *, timeout: float = 30, **kwargs):
        response = getattr(self.http, method)(self.base + path, headers=self.headers, timeout=timeout, **kwargs)
        if response.status_code == 401:
            raise TokenRejected(response.text)
        response.raise_for_status()
        return response

    def _post(self, path: str, *, json=None, timeout: float = 30):
        return self._send("post", path, json=json, timeout=timeout).json()

    def claim(self, wait: float = 20) -> dict | None:
        return self._post(f"/agent-link/claim?wait={wait}", timeout=wait + CLAIM_HTTP_TIMEOUT_SECONDS - 20)["job"]

    def push(self, task_id: int, state: dict, final: bool = False) -> dict:
        return self._post(f"/agent-link/tasks/{task_id}/push", json={"state": state, "final": final})

    # Learning memory (memory/_store.py remote backend).
    def read_memory(self, kind: str) -> list:
        return self._send("get", f"/agent-link/memory/{kind}").json()["records"]

    def write_memory(self, kind: str, records: list) -> None:
        self._send("put", f"/agent-link/memory/{kind}", json={"records": records})

    # Web search through the cloud's search API keys (tools/web.py remote hook).
    def web_search(self, query: str, max_results: int) -> dict:
        return self._post("/agent-link/web-search", json={"query": query, "max_results": max_results})

    # Workspace files (agent_workspace.py).
    def list_files(self) -> list[dict]:
        return self._send("get", "/agent-link/files").json()["files"]

    def download_file(self, file_id: str, destination) -> None:
        response = self._send("get", f"/agent-link/files/{file_id}/download", timeout=300)
        with open(destination, "wb") as handle:
            handle.write(response.content)

    def upload_file(self, path, file_id: str | None = None) -> dict:
        data = {"file_id": str(file_id)} if file_id else {}
        with open(path, "rb") as handle:
            return self._send("post", "/agent-link/files", files={"upload": (Path(path).name, handle)},
                              data=data, timeout=300).json()


def run_job(job: dict, cloud: CloudClient, *, run=None, log=print) -> None:
    """Run one claimed job to completion, mirroring progress to the cloud."""
    import config
    from agent_link import PROGRESS_FIELDS, apply_state, export_state
    from agent.core import AgentTask
    from agent.core import run_task as default_run

    run = run or default_run
    task_id = job["task_id"]
    state = job.get("state") or {}
    task = AgentTask(str(state.get("instruction") or ""), user_id=state.get("user_id"))
    apply_state(task, state)
    # Use only providers the cloud relay holds keys for.
    providers = job.get("providers") or [task.active_provider]
    if task.active_provider not in providers:
        task.active_provider = providers[0]
    config.AI_PROVIDER = task.active_provider
    config.AI_PROVIDER_FALLBACK_CHAIN = [name for name in providers if name != task.active_provider]
    log(f"task {task_id}: started - {task.instruction[:120]}")
    workspace = _sync_files(cloud, task, "pull", log)

    def _work():
        try:
            run(task, db=None, db_task_id=None, user_preferences={})
        except Exception as exc:  # same contract as main._start_task_in_background
            task.log_step(f"Task stopped unexpectedly: {exc}")
            task.is_done = True
            task.final_response = (
                "INCOMPLETE: The task stopped before its result could be verified. "
                f"Reason: {exc}"
            )
            task.chat_transcript.append({"role": "assistant", "text": task.final_response})

    worker = threading.Thread(target=_work, name=f"xelora-task-{task_id}", daemon=True)
    worker.start()
    while worker.is_alive():
        worker.join(PUSH_INTERVAL_SECONDS)
        if not worker.is_alive():
            break
        try:
            control = cloud.push(task_id, export_state(task, PROGRESS_FIELDS))
        except TokenRejected:
            raise
        except Exception as exc:  # a missed push is retried on the next tick
            log(f"task {task_id}: progress push failed ({exc})")
            continue
        if control.get("pause_requested") and not task.is_paused:
            log(f"task {task_id}: pause requested")
            task.pause()

    if workspace is not None:
        _sync_files(cloud, task, "push", log, workspace)
    try:
        from memory.outcome import record_task_outcome
        record_task_outcome(task, task.user_id)
    except TokenRejected:
        raise
    except Exception as exc:
        task.log_step(f"Task learning was unavailable: {exc}")
    final_state = export_state(task)
    for attempt in range(5):
        try:
            cloud.push(task_id, final_state, final=True)
            break
        except TokenRejected:
            raise
        except Exception as exc:
            log(f"task {task_id}: final push failed ({exc}); retrying")
            time.sleep(min(2 ** attempt, MAX_BACKOFF_SECONDS))
    log(f"task {task_id}: finished ({'paused' if task.is_paused else 'done'})")


def _sync_files(cloud: CloudClient, task, direction: str, log, workspace=None):
    """Mirror the user's cloud files before a task ("pull") and send changes after ("push")."""
    from agent_workspace import WorkspaceSync

    if task.user_id is None:
        return None
    try:
        workspace = workspace or WorkspaceSync(cloud, os.environ["STORAGE_DIR"], task.user_id, log=log)
        counts = workspace.pull() if direction == "pull" else workspace.push()
    except TokenRejected:
        raise
    except Exception as exc:  # files are a convenience; the Excel task still runs
        task.log_step(f"Your Xelora files could not be synced ({type(exc).__name__}: {exc}).")
        return workspace
    changed = {key: value for key, value in counts.items() if value}
    if changed:
        task.log_step(f"Files {'synced from' if direction == 'pull' else 'saved to'} Xelora: "
                      + ", ".join(f"{value} {key}" for key, value in changed.items()))
    return workspace


def serve(cloud: CloudClient, *, stop: threading.Event | None = None, run=None, log=print) -> None:
    stop = stop or threading.Event()
    backoff = 1
    connected = False
    while not stop.is_set():
        try:
            job = cloud.claim()
            backoff = 1
            if not connected:
                log(f"Xelora local agent connected to {cloud.base}")  # Xelora Desktop waits for this line
                connected = True
        except TokenRejected:
            raise
        except Exception as exc:
            log(f"cloud unreachable ({type(exc).__name__}); retrying in {backoff}s")
            stop.wait(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
            continue
        if job:
            run_job(job, cloud, run=run, log=log)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Xelora Desktop local agent")
    parser.add_argument("--api-url", default=os.getenv("XELORA_API_URL", ""))
    parser.add_argument("--token", default=os.getenv("XELORA_AGENT_TOKEN", ""))
    args = parser.parse_args(argv)
    if not args.api_url or not args.token:
        parser.error("--api-url and --token (or XELORA_API_URL / XELORA_AGENT_TOKEN) are required")
        return 2

    configure_environment(args.api_url, args.token)
    print(excel_engine_status(), flush=True)
    print(cua_driver_status(), flush=True)
    cloud = CloudClient(args.api_url, args.token)
    from memory import _store
    _store.use_remote(cloud.read_memory, cloud.write_memory)  # learn into the user's cloud memory
    from tools import web
    web.use_remote(cloud.web_search)  # search with the cloud's keys; falls back to this PC
    try:
        serve(cloud, log=lambda message: print(message, flush=True))
    except TokenRejected:
        print("The cloud rejected this agent's token. Pair Xelora Desktop again.", flush=True)
        return EXIT_TOKEN_REJECTED
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
