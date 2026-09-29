# Testing Xelora

## What runs anywhere (Linux/macOS/Windows)

```bash
cd backend
python -m venv .venv && . .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-auth.txt -r requirements-dev.txt
python -m pytest -q -rs
```

`conftest.py` supplies a throwaway `JWT_SECRET_KEY` for tests only.

| File | Covers |
|---|---|
| `test_cua_router_mcp.py` | Cua adapter over a **real stdio MCP transport** against `test_support/fake_cua_driver.py`: health ready/unavailable/unresponsive, allowlisting, accessibility observation, window-not-found, target required/not observed/wrong window/desktop scope, click and keyboard failures, malformed verification, act→verify success, retry success, bounded retry exhaustion. Outbound MCP (allowlist, read/write results, policy, bad config, unavailable server). Router decisions. Policy/validation. Completion status for non-Excel tasks. Terminal hardening. Audit redaction. |
| `test_integration_capabilities.py` | Terminal policy and execution, file-tool scoping and escapes, registry contracts, planning-mode holds, Cua gating, capability catalogue. |
| `test_codegen_sandbox.py` | Code-generation sandbox: dunder/COM/`ExecuteExcel4Macro`/file-I/O escapes rejected, pandas analysis accepted, one-source-one-target sheet rule, secrets absent from the subprocess, real subprocess runs (pandas, crash, timeout, missing evidence). |
| `test_excel_capabilities.py` | Excel argument guards (bad `write_table` rows, file types/locations, read-only SQL), bulk file import (type coercion, leading zeros, formula-injection neutralised, overwrite refusal, storage scope), `copy_range`, fixed `delete_chart`/`import_from_database` — against `test_support/fake_excel.py`, not real Excel. |
| `test_web_guard.py` | SSRF guard (loopback/private/metadata/redirects), size caps, fetch/search parsing. |
| `test_automation_reliability.py` | Excel task-loop behaviour with fakes (recovery, verification, visual routing). Four tests need Windows and are **skipped** elsewhere. |
| `test_gemini_reliability.py`, `test_quick_chat.py`, `test_dashboard_layout.py`, `test_file_processing.py` | Provider handling, chat, layout, upload parsing. |
| `test_learning.py` | Live script; **skipped** unless a backend is running on :8000. |

The fake Cua driver proves Xelora's adapter contract. It is **not** evidence
that the real Cua Driver or Excel behave the same way.

Frontend:

```bash
cd frontend/xelora && npm install
npx tsc --noEmit && npm run build          # production build
npm run lint                               # see "Known lint findings" below
cd apps/desktop && npm install && npm run typecheck && npm run build
```

Known lint findings: React Compiler rules (`react-hooks/set-state-in-effect`)
flag data-loading effects in several dashboard pages; they are not build
errors. `apps/desktop` has no unit tests yet (`npm test` reports "No test
files found").

## Windows + Excel runtime validation (must be done on Windows)

Nothing in this section has been executed by the Linux CI/agent run. It is the
procedure for the real acceptance test.

1. **Prerequisites**: Windows 10/11, desktop Microsoft Excel (not WPS), Python
   3.11+, Node 20+, PostgreSQL (for accounts/files), an AI provider key.
2. **Backend**
   ```powershell
   cd backend
   python -m venv .venv; .venv\Scripts\activate
   pip install -r requirements.txt -r requirements-auth.txt -r requirements-dev.txt
   copy .env.example .env      # then fill JWT_SECRET_KEY, LOCAL_API_KEY, DATABASE_URL, provider key
   python -m pytest -q -rs     # the 4 Windows-only tests must now RUN and pass
   uvicorn server:app --port 8000
   ```
3. **Health**
   ```powershell
   $h = @{ "X-API-Key" = "<LOCAL_API_KEY>" }
   Invoke-RestMethod http://localhost:8000/ -Headers $h
   Invoke-RestMethod http://localhost:8000/agent/cua/health -Headers $h
   Invoke-RestMethod http://localhost:8000/agent/tools -Headers $h | Select tool_count, risk_counts
   ```
4. **Frontend**: `cd frontend\xelora; copy .env.example .env.local` (set
   `BACKEND_API_KEY`), `npm install`, `npm run dev`, sign up / log in at
   http://localhost:3000, upload a small CSV on the Files page.
5. **Scenarios** (driven through the real `/task` API):
   ```powershell
   cd backend
   $env:XELORA_API_KEY = "<LOCAL_API_KEY>"
   $env:XELORA_TOKEN   = "<JWT: POST /auth/login, response field 'token'>"
   python scripts\windows_e2e.py --list
   python scripts\windows_e2e.py 1 2 3 4 5 6 10          # Excel, codegen, web, files
   ```
   Then enable and run the optional layers:
   * Scenario 7/8 (UI controls, recovery): set `ENABLE_VISUAL_FALLBACK=true`,
     and for Cua follow `docs/WINDOWS_CUA_SETUP.md` (`ENABLE_CUA_DRIVER=true`),
     restart, `python scripts\windows_e2e.py 7 8`.
   * Scenario 9 (terminal): `ENABLE_TERMINAL_TOOLS=true`,
     `XELORA_TERMINAL_ROOT=<a git checkout>`, restart, `python scripts\windows_e2e.py 9`.
     Also confirm a refusal: ask "delete all files in the terminal" and check the
     step shows `permission_denied`.
6. **What to record per scenario**: the tools in the progress log, whether each
   action shows verified evidence, the final status, and what Excel actually
   shows. For 7/8 confirm in the `xelora.audit` log lines that
   `cua__get_window_state` preceded any Cua input and that a
   `verify_state`/`cua_act_and_verify` confirmed the result.
7. **Desktop app**: `cd frontend\xelora; npm run desktop:dev` with backend and
   frontend running; check login, task progress, and that closing the window
   leaves the backend running.

## Expected results per scenario

| # | Scenario | Expected route / tools | Verification |
|---|---|---|---|
| 1 | Write A1:C5 | `excel_skills`: `create_new_workbook`/`write_table` | skill read-back `verified: true` |
| 2 | Read + summarize | `inspect_workbook`, `read_range` | answer matches the sheet |
| 3 | Format range | `format_range` (or `apply_formatting`) | read-back of number format / font |
| 4 | Formula fill-down | `insert_formula` / fill | formula results audited |
| 5 | Python/pandas transform | `run_excel_code` then skills | executor read-back + final audit |
| 6 | Research → Excel | `web_search` → `web_fetch` → `write_table` | source URL in sheet; write read back |
| 7 | UI-only control | shortcuts → `cua__get_window_state` → `cua_act_and_verify` → UIA/OmniParser | `verify_state` satisfied, sheet order checked |
| 8 | GUI recovery | as 7, with a failed first attempt | bounded retries, re-observe, alternate method |
| 9 | Terminal | `run_terminal ["git","status"]` | exit code 0, `succeeded: true` |
| 10 | Workspace file | `list_workspace_files` → `import_workspace_file_to_sheet` | upload shown as `uploaded_as`; first/last rows read back |
