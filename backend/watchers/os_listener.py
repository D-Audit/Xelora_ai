"""
watchers/os_listener.py
OS-Level Event Listener: watches file-system changes and (on Windows)
which window currently has focus, and calls back into your code when
something happens - the foundation for "the agent notices you switched
to Excel" or "the agent notices a file just landed in a watched folder"
type behavior.

This is a STANDALONE building block, not wired into agent/core.py's
task loop by default - deciding what the agent should DO in response to
a given OS event (auto-start a task? just log it? ask the user first?)
is a product decision specific to your use case, not something to guess
at generically here. Wire OnFileEvent/OnWindowChange into main.py or
agent/core.py once you've decided that behavior.

Requires a real desktop with a display, same as vision/ui_control.py -
won't do anything meaningful on a headless server.
"""

import threading
import time

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _HAS_WATCHDOG = True
except Exception:
    _HAS_WATCHDOG = False

try:
    import win32gui
    _HAS_WIN32 = True
except Exception:
    _HAS_WIN32 = False


class _Handler(FileSystemEventHandler if _HAS_WATCHDOG else object):
    def __init__(self, on_file_event):
        self.on_file_event = on_file_event

    def on_created(self, event):
        if not event.is_directory:
            self.on_file_event("created", event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self.on_file_event("modified", event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self.on_file_event("deleted", event.src_path)


class OSEventListener:
    """
    Usage:
        listener = OSEventListener(
            watch_folder="C:/Users/me/Documents/Incoming",
            on_file_event=lambda event_type, path: print(event_type, path),
            on_window_change=lambda title: print("focused:", title),
        )
        listener.start()
        ...
        listener.stop()
    """

    def __init__(self, watch_folder: str = None, on_file_event=None,
                 on_window_change=None, poll_interval_seconds: float = 1.0):
        self.watch_folder = watch_folder
        self.on_file_event = on_file_event or (lambda event_type, path: None)
        self.on_window_change = on_window_change or (lambda title: None)
        self.poll_interval_seconds = poll_interval_seconds

        self._observer = None
        self._window_thread = None
        self._stop_flag = threading.Event()
        self._last_window_title = None

    def start(self):
        if self.watch_folder:
            if not _HAS_WATCHDOG:
                raise RuntimeError("watchdog is not installed - run 'pip install watchdog'.")
            self._observer = Observer()
            self._observer.schedule(_Handler(self.on_file_event), self.watch_folder, recursive=True)
            self._observer.start()

        if _HAS_WIN32:
            self._stop_flag.clear()
            self._window_thread = threading.Thread(target=self._poll_window_focus, daemon=True)
            self._window_thread.start()

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join()
        self._stop_flag.set()
        if self._window_thread:
            self._window_thread.join(timeout=self.poll_interval_seconds + 1)

    def _poll_window_focus(self):
        while not self._stop_flag.is_set():
            try:
                title = win32gui.GetWindowText(win32gui.GetForegroundWindow())
                if title and title != self._last_window_title:
                    self._last_window_title = title
                    self.on_window_change(title)
            except Exception:
                pass
            time.sleep(self.poll_interval_seconds)

    def is_available(self) -> dict:
        return {"file_watching": _HAS_WATCHDOG, "window_focus_tracking": _HAS_WIN32}
