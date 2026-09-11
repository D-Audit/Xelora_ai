"""Thread-safe Server-Sent Events support for task progress."""

from __future__ import annotations

import asyncio
import json
import queue
import threading
import time
from collections import defaultdict
from typing import Any, AsyncIterator


class TaskProgressStreamer:
    """Publish task events from worker threads to async SSE clients."""

    def __init__(self, history_limit: int = 250):
        self._clients: dict[int, list[queue.Queue]] = defaultdict(list)
        self._history: dict[int, list[dict[str, Any]]] = defaultdict(list)
        self._history_limit = history_limit
        self._lock = threading.RLock()

    def add_client(self, task_id: int, client_queue: queue.Queue) -> None:
        with self._lock:
            self._clients[task_id].append(client_queue)

    def remove_client(self, task_id: int, client_queue: queue.Queue) -> None:
        with self._lock:
            clients = self._clients.get(task_id, [])
            if client_queue in clients:
                clients.remove(client_queue)
            if not clients:
                self._clients.pop(task_id, None)

    def emit(self, task_id: int, event: str, data: dict[str, Any]) -> None:
        message = {"event": event, "data": data, "timestamp": time.time()}
        with self._lock:
            history = self._history[task_id]
            history.append(message)
            del history[:-self._history_limit]
            clients = list(self._clients.get(task_id, []))
        for client_queue in clients:
            try:
                client_queue.put_nowait(message)
            except queue.Full:
                self.remove_client(task_id, client_queue)

    def emit_step(self, task_id: int, step_type: str, text: str, **extra: Any) -> None:
        self.emit(task_id, "step", {"type": step_type, "text": text, **extra})

    def emit_action(self, task_id: int, tool_name: str, status: str, result: dict | None = None) -> None:
        self.emit(task_id, "action", {"tool": tool_name, "status": status, "result": result})

    def emit_completion(self, task_id: int, success: bool, response: str) -> None:
        self.emit(task_id, "complete", {"success": success, "response": response})

    def emit_error(self, task_id: int, error: str) -> None:
        self.emit(task_id, "error", {"message": error})

    def get_history(self, task_id: int) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._history.get(task_id, []))

    def client_count(self, task_id: int) -> int:
        with self._lock:
            return len(self._clients.get(task_id, []))


streamer = TaskProgressStreamer()

def _format_event(event: dict[str, Any]) -> str:
    return f"event: {event['event']}\ndata: {json.dumps(event['data'], default=str)}\n\n"


async def task_event_generator(task_id: int) -> AsyncIterator[str]:
    """Yield retained and live events, including periodic SSE keepalives."""
    client_queue: queue.Queue = queue.Queue(maxsize=100)
    streamer.add_client(task_id, client_queue)
    try:
        for event in streamer.get_history(task_id):
            yield _format_event(event)
        while True:
            try:
                event = await asyncio.to_thread(client_queue.get, True, 25)
            except queue.Empty:
                yield f": keepalive {time.time()}\n\n"
                continue
            yield _format_event(event)
            if event["event"] == "complete":
                return
    finally:
        streamer.remove_client(task_id, client_queue)
