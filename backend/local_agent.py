"""local_agent.py - the Xelora Desktop local agent.

Runs on the user's Windows PC next to Excel (Xelora Desktop starts it; it
can also be run by hand) and executes that user's tasks from the cloud API:

    python local_agent.py --api-url https://xelora-api.onrender.com --token xa_...

or with XELORA_API_URL / XELORA_AGENT_TOKEN in the environment.

Loop: claim a job (long poll) -> rebuild the AgentTask from the job's state ->
run_task() locally against Excel -> push progress every second -> push the
final state. Model calls go through the cloud's relay with this agent's
token, so no provider key is needed (or stored) on this PC.

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


def configure_environment(api_url: str, token: str) -> None:
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
    })
    os.environ.setdefault("JWT_SECRET_KEY", "local-agent-does-not-issue-tokens")


class CloudClient:
    """Thin HTTP client for /agent-link. ``http`` is any requests-like object."""

    def __init__(self, api_url: str, token: str, http=None):
        import requests

        self.base = api_url.rstrip("/")
        self.headers = {"X-Agent-Token": token}
        self.http = http or requests.Session()

    def _post(self, path: str, *, json=None, timeout: float = 30):
        response = self.http.post(self.base + path, json=json, headers=self.headers, timeout=timeout)
        if response.status_code == 401:
            raise TokenRejected(response.text)
        response.raise_for_status()
        return response.json()

    def claim(self, wait: float = 20) -> dict | None:
        return self._post(f"/agent-link/claim?wait={wait}", timeout=wait + CLAIM_HTTP_TIMEOUT_SECONDS - 20)["job"]

    def push(self, task_id: int, state: dict, final: bool = False) -> dict:
        return self._post(f"/agent-link/tasks/{task_id}/push", json={"state": state, "final": final})


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
    # Cloud-uploaded files are not on this PC; keep the cloud file tools off.
    task.has_authenticated_user = False
    # Use only providers the cloud relay holds keys for.
    providers = job.get("providers") or [task.active_provider]
    if task.active_provider not in providers:
        task.active_provider = providers[0]
    config.AI_PROVIDER = task.active_provider
    config.AI_PROVIDER_FALLBACK_CHAIN = [name for name in providers if name != task.active_provider]
    log(f"task {task_id}: started - {task.instruction[:120]}")

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
    cloud = CloudClient(args.api_url, args.token)
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
