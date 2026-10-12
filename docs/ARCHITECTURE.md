# Xelora Architecture

Xelora is an Excel-first desktop AI agent. A FastAPI backend runs **on the same
Windows machine as Microsoft Excel**; a Next.js web app (optionally wrapped in
Electron) talks to it. Excel work goes through structured APIs first; general
tools (web, files, terminal, desktop control, MCP) share one governed execution
boundary.

```
Browser / Electron window
  └─ Next.js (frontend)  ── server-side only: BACKEND_URL + BACKEND_API_KEY
       └─ FastAPI  server:app  (backend/server.py → main.py)
            ├─ auth / billing / plan guard / files / workflows / automations
            └─ POST /task → background worker (one Excel task at a time: _TASK_EXECUTION_LOCK)
                 └─ agent/core.py  run_task()
                      ├─ planner preflight + capability route (agent/router.py)
                      ├─ provider tool-call loop (agent/providers.py: Gemini, Claude, OpenRouter + fallback chain)
                      └─ per tool call:
                           get_tool_spec  (agent/tool_registry.py)
                           decide_action  (agent/permissions.py)   → blocked / held for approval / allowed
                           audit.record   (agent/audit.py, logger "xelora.audit", secrets redacted)
                           dispatch_action
                             ├─ Excel skills      skills/library/* (75 skills; COM/xlwings/openpyxl)
                             ├─ Excel codegen     codegen/executor.py (AST-restricted, isolated subprocess, timeout)
                             ├─ Excel visual/UIA  vision/ui_control.py (+ OmniParser via vision/omniparser_client.py)
                             ├─ web               tools/web.py + tools/web_guard.py
                             ├─ user files        tools/filesystem.py
                             ├─ terminal          tools/terminal.py
                             ├─ Cua Driver        vision/cua_driver.py  ─┐
                             └─ external MCP      tools/mcp_external.py ─┴─ tools/mcp_client.py (stdio MCP)
                           verification → structured step → DB ActionLog / SSE / reveal
```

## Routing (which capability for which task)

`agent/router.py` classifies the instruction and adds a short ordered
**CAPABILITY ROUTE** to the system prompt, computed from live configuration:

| Request shape | Route |
|---|---|
| Cells, ranges, formulas, formatting, sort/filter, charts | `excel_skills` |
| Large or complex transformation (thousands of rows, group-by, joins, statistics, synthetic data) — dedicated skills first when one fits (remove_duplicates, unpivot_data, combine_sheets …) | `python_codegen` → `excel_skills` |
| Current facts / URLs | `web_research` (search → fetch) → `excel_skills` if it goes into a sheet |
| CSV/TSV/JSON/TXT the user uploaded | `user_files` → `excel_skills` |
| "terminal", "git status", "run tests" | `terminal` (only if enabled; otherwise stated as unavailable) |
| Buttons, dialogs, ribbon, menus | `excel_skills` → `excel_shortcuts` → `cua_accessibility` → `ui_automation` → `omniparser` |
| MCP / integration | `mcp` (only if configured) |

The route is advisory for the model; **policy is enforced in code** regardless
of what the model chooses. Excel tasks still require verified workbook
evidence to be reported `completed`; tasks whose route never involves Excel
(research, terminal, files, MCP) are judged by their own verified results.

## Tool registry and policy

Every tool has a `ToolSpec`: risk (`read`/`write`/`execute`), execution layer,
input/output schema, permission requirements, verification method, platforms,
timeout, availability. Web/file/terminal provider declarations are generated
from these specs, so the schema the model sees is the one dispatch enforces.

`decide_action` order: unknown → blocked; disabled by configuration → blocked;
file tools without a JWT session → blocked; arguments fail schema → blocked
(the model gets the exact error and can correct it); non-read action while the
task is in planning-only mode → held for the user's "Confirm"; otherwise
allowed. Excel skills keep their established per-skill argument handling.

Tools that cannot change the workbook (Excel reads, web, file reads, terminal,
Cua observation, read-only MCP tools) are *observations*: their failures never
put the task into Excel recovery mode, and their successes are never counted as
workbook evidence.

## Computer use: accessibility first

Order of preference for Excel UI work: Excel API/skills → keyboard shortcuts /
Name Box → Cua accessibility-targeted input → Windows UI Automation (existing
`ui_control.py`) → OmniParser for unlabelled visual elements.

Cua Driver (`vision/cua_driver.py`) is reached over stdio MCP (`cua-driver mcp`)
and only an allowlist of its tools is exposed (`cua__*`). Enforced rules:

* **Observe before act**: input to `(pid, window_id)` is refused unless this
  task already called `cua__get_window_state` on that exact window.
* **Right window**: once the task is bound to an Excel process, input to any
  other process is refused (`CUA_ALLOW_OTHER_APPS` widens this).
* **No blind desktop input**: `scope="desktop"`/`move_cursor` refused unless
  `CUA_ALLOW_DESKTOP_SCOPE=true`.
* **Verification**: a Driver acknowledgement is never success. Only
  `verify_state` with every predicate `satisfied` verifies; `unknown` does not.
* **Bounded retry**: `cua_act_and_verify` runs action → `verify_state` in one
  session, retries only while verification fails, at most 3 attempts, and
  stops immediately if the Driver rejects the action itself.

OmniParser is **kept** as the last-resort fallback: Cua's accessibility tree
covers named controls, but unlabelled icons and custom-drawn surfaces still
need visual parsing. It is only offered when `OMNIPARSER_URL` or
`OMNIPARSER_LOCAL_MODE` is configured and the visual layer is enabled.

## Excel layer

* **Skills** (75, `skills/library/<name>/{SKILL.md,impl.py}`; every folder
  with both files is loaded, and one that fails to load is logged and
  skipped). Each writes through xlwings, saves, reads the result back
  and returns `verified`.
* **Argument guards** (`agent/excel_guards.py`, enforced by the policy layer):
  file types per path-taking skill and no hidden/system folders; read-only
  SQL for `import_from_database`; `write_table` rows must match the header
  width (the error names the row), no formulas in data rows, ≤20,000 cells.
  A refused call never executed, so it is not counted as an unverified change.
* **Bulk import** (`import_workspace_file_to_sheet`, `tools/workspace_import.py`):
  CSV/TSV/TXT/XLSX from the signed-in user's storage straight into a sheet in
  5,000-row chunks (≤200,000 rows). Leading-zero codes, `+` phone numbers and
  >15-digit IDs stay text; values that would become formulas are stored as
  text; existing cells are not overwritten unless asked; first/last rows are
  read back.
* **Code generation** (`codegen/executor.py`): separate process, time limit,
  secrets removed from its environment. Imports: xlwings, pandas, numpy and a
  few stdlib modules. Refused: dunder access, `open`/`eval`/`getattr`, every
  pandas/numpy file/URL/SQL/pickle function and `query`/`eval`, Excel COM
  members that run macros or programs or open/save other files
  (`ExecuteExcel4Macro`, `Run`, `Workbooks`, `SaveAs`, … case-insensitive),
  saving, direct formula writes (use `insert_formula`), and more than one
  source + one target sheet. Results count only with `verified: true` and a
  non-empty `verification_note`.
* **Decision guide**: `agent/prompts.py` maps request types to tools; the
  router adds a per-task ordered route.

## General tools

| Tool | Boundary |
|---|---|
| `web_search`, `web_fetch` | http(s) only; every redirect re-validated; loopback/private/CGNAT/link-local/metadata rejected; 2 MB cap; binary types refused; output labelled untrusted. Known limit: DNS is checked before connecting (no IP pinning), so DNS-rebinding is mitigated, not eliminated. |
| `*_workspace_file` | Only `STORAGE_DIR/<user_id>` (same root as uploads); JWT session required; relative paths only; symlinks/traversal refused; text types; 1 MB; create never overwrites; update is atomic and read back. Listings show original upload names (`uploaded_as`). |
| `run_terminal` | Off by default. argv only, no shell; program names (not paths) from an allowlist; read-only commands unless `TERMINAL_WRITE_TOOLS`; cwd/paths inside `XELORA_TERMINAL_ROOT`; secrets stripped from the child environment; batch-script arguments restricted; timeout ≤120 s; output capped. `pwd`/`ls`/`dir` are answered in-process for Windows parity. |
| `mcp__<server>__<tool>` | Off by default. Only tools allowlisted per server in `MCP_SERVERS_FILE`; write tools are policy "write" risk; secrets only via `pass_env`; output untrusted. |

## Other subsystems

* **Automations** (`automation.py`): opt-in interval scheduler over the user's
  own workflows; atomic claim per due tick; submits through `/task`. Needs a
  database.
* **Memory**: per-user preferences (Postgres), task/chat history JSON under
  `MEMORY_STORE_DIR`, learned skills. Per-user keyed; no retention controls yet.
* **Subagents** (`agent/subagents`): specialist wrappers around skills exist as
  a library but are **not called by the task loop**. They are intentionally
  not wired in, because they would bypass the per-call policy gate.
* **MCP server** (`mcp_server/server.py`): exposes Xelora's Excel skills to
  other MCP clients (unchanged).
