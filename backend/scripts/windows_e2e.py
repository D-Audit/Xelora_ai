"""Run Xelora's user-level end-to-end scenarios against a live backend.

Run this ON THE WINDOWS MACHINE that has Microsoft Excel and the backend
(`uvicorn server:app --port 8000`). It submits real tasks through POST /task
and polls GET /task/{id}/progress, then prints the tools used, their
verification, and the final status. It does not fake anything: if Excel,
Cua, or a provider is unavailable, the task reports that.

Usage (PowerShell):
    $env:XELORA_API_KEY = "<LOCAL_API_KEY from backend/.env>"
    $env:XELORA_TOKEN   = "<JWT from /auth/login>"   # needed for scenario 10 (user files)
    python scripts\\windows_e2e.py --list
    python scripts\\windows_e2e.py 1 3 4
    python scripts\\windows_e2e.py all
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import requests

SCENARIOS = {
    "1": ("Excel write", "Create a new workbook and write this table into A1:C5 of Sheet1: "
          "Region,Q1,Q2 / North,120,135 / South,98,110 / East,143,150 / West,87,95. Verify the cells."),
    "2": ("Read + summarize", "Read the data on the active sheet and summarize the totals per column in a short answer."),
    "3": ("Formatting", "Format B2:C5 on Sheet1 as currency with 2 decimals and make row 1 bold."),
    "4": ("Formula fill-down", "In D1 write 'Total'. In D2 enter =B2+C2 and fill it down to D5. Verify the results."),
    "5": ("Python/pandas transform", "Use Python/pandas to build a 1,000-row table of synthetic daily sales "
          "(Date, Store, Units, Revenue), aggregate revenue by store, and write the summary to a new sheet 'Summary'."),
    "6": ("Research into Excel", "Find the latest published annual inflation rate for Rwanda from an official or "
          "reputable source, then write Source URL, Year, and Rate into A1:C2 of a new sheet 'Research'."),
    "7": ("UI-only control", "Open the Data tab and click the Sort button, then choose to sort A1:D5 by column D "
          "descending using the Sort dialog. Verify the order."),
    "8": ("GUI recovery", "Click the 'Freeze Panes' ribbon control and freeze the top row. If the first attempt "
          "does not work, observe the window again and use a different method. Verify row 1 is frozen."),
    "9": ("Terminal with permissions", "Run git status in the terminal and tell me the current branch."),
    "10": ("Workspace file", "List my uploaded files and import the first CSV into a new sheet 'Imported'."),
}


def run(base: str, headers: dict, number: str, timeout_s: int) -> str:
    title, instruction = SCENARIOS[number]
    print(f"\n=== Scenario {number}: {title} ===")
    response = requests.post(f"{base}/task", json={"instruction": instruction}, headers=headers, timeout=30)
    if not response.ok:
        print(f"  submit failed: HTTP {response.status_code} {response.text[:300]}")
        return "submit_failed"
    task_id = response.json()["task_id"]
    deadline = time.monotonic() + timeout_s
    snapshot: dict = {}
    confirmed = False
    while time.monotonic() < deadline:
        snapshot = requests.get(f"{base}/task/{task_id}/progress", headers=headers, timeout=30).json()
        if snapshot.get("status") == "awaiting_approval" and snapshot.get("is_done") and not confirmed:
            # Plan approval is a user message on the same conversation.
            print("  plan proposed; approving it with 'Confirm' (as a user would)")
            requests.post(f"{base}/task/{task_id}/resume", json={"correction": "Confirm"}, headers=headers, timeout=30)
            confirmed = True
            time.sleep(2)
            continue
        if snapshot.get("status") not in {"running", "awaiting_approval"}:
            break
        time.sleep(3)
    for line in (snapshot.get("progress_log") or [])[-25:]:
        print(f"  | {str(line)[:200]}")
    status = snapshot.get("status", "timeout")
    print(f"  final status: {status}")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenarios", nargs="*", default=["--list"])
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--base-url", default=os.getenv("XELORA_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--timeout", type=int, default=600, help="seconds per scenario")
    args = parser.parse_args()
    if args.list or args.scenarios in (["--list"], []):
        for number, (title, instruction) in SCENARIOS.items():
            print(f"{number:>2}. {title}: {instruction}")
        return 0
    headers = {"Content-Type": "application/json"}
    if os.getenv("XELORA_API_KEY"):
        headers["X-API-Key"] = os.environ["XELORA_API_KEY"]
    if os.getenv("XELORA_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['XELORA_TOKEN']}"
    selected = list(SCENARIOS) if args.scenarios == ["all"] else args.scenarios
    results = {number: run(args.base_url.rstrip("/"), headers, number, args.timeout) for number in selected if number in SCENARIOS}
    print("\nSummary:")
    for number, status in results.items():
        print(f"  {number:>2}. {SCENARIOS[number][0]:<28} {status}")
    return 0 if all(status == "completed" for status in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
