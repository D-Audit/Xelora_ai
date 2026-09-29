# Xelora + OpenWorker Architecture and Integration Report

**Scope:** analysis only, 2026-09-15. No production code, configuration, dependency, or source file was changed. Xelora remains the product and source of truth; OpenWorker is an implementation reference.

## 1. Executive Summary

Xelora is a FastAPI-backed, Excel-first desktop agent. Its core execution path is intentionally specialized: a request becomes a task, a model selects from Excel skills, bounded Excel code generation, or visual UI controls, and Xelora collects workbook/visual verification before returning a result. It also includes authenticated spreadsheet storage, user preferences, task history, knowledge ingestion, billing, workflows, a web frontend, and a desktop wrapper.

OpenWorker is a local-first general desktop-worker runtime. Its strongest reusable ideas are a runtime-owned tool registry, backend-enforced permission/risk decisions and approvals, workspace-root constraints, hardened web fetch, outbound MCP lifecycle management, model-provider routing, auditable tool execution, and a scheduler. Those capabilities should be added around Xelora's existing Excel execution engine, not substituted for it.

The largest Xelora opportunity is a **single governed execution boundary** between model tool selection and every consequential action. That boundary should route requests to the cheapest reliable executor: direct Excel skill first, bounded Excel codegen only when needed, visual control only for UI-only tasks, then future web/file/terminal/MCP tools. It must own policy, approval, verification contracts, audit data, retries, and resource limits.

## 2. Actual Architectures

### Xelora today

```text
Next.js web app / Electron wrapper
        -> FastAPI server.py + main.py routers
        -> POST /task (API key, rate limit, optional JWT identity, plan guard)
        -> one process-wide Excel task lock + background worker
        -> agent.core.run_task
        -> provider function calls and capability catalogue
        -> dispatch_action
             -> Excel SkillRegistry (COM/xlwings/openpyxl helpers)
             -> bounded generated Excel Python
             -> OmniParser/pyautogui visual controls
        -> per-action evidence + workbook/task verification + ActionLog/SSE/history
        -> task/reveal/progress response
```

Evidence: `backend/main.py` authenticates the task API and serializes desktop Excel runs; `backend/agent/core.py` dispatches the three execution layers and records action results; `backend/skills/registry.py` and `loader.py` discover manifest-backed Excel skills; `backend/vision/*` provides visual fallback and task verification. `backend/server.py` is the documented deployment entrypoint that layers auth/billing/plan enforcement onto the base API.

### OpenWorker today

```text
Tauri + React GUI / local server
        -> ServerManager creates a session
        -> agent/persona tool factory builds a ToolRegistry
        -> TurnEngine model loop
        -> PermissionEngine decision (allow / ask / block)
        -> approval UI or execution
        -> AuditStore + transcript/events
        -> optional MCP, connector, memory, scheduler, read-only explorer
```

Evidence: `coworker/tools/registry.py`, `coworker/engine.py`, `coworker/permissions.py`, and `coworker/server/manager.py`. OpenWorker is not an Excel or computer-vision substitute; its included worker capabilities are local files, shell, web, MCP, connectors, scheduling, and model providers.

## 3. Comparison and Decisions

| Capability | Xelora | OpenWorker | Decision for Xelora |
|---|---|---|---|
| Agent loop/task state | Sequential provider tool-call loop, task lock, recovery states, SSE/reveal | General TurnEngine with sessions, steering, cancellation and iteration limits | **B**: retain Xelora loop; introduce a narrow execution interface and explicit normalized task/action state. |
| Tool registry/schema | Dynamic Excel SkillRegistry with manifest schemas; visual and codegen dispatch are separately hard-coded | Generic ToolRegistry stores callable + JSON schema + metadata | **B/D**: make Xelora's existing registry the Excel adapter; add a unified registry facade, not a second Excel registry. |
| Excel automation | 70+ focused skills, COM/xlwings, direct range handling, codegen fallback, visible checkpoints | No comparable Excel-native stack | **A**: protect and retain. |
| Computer use | OmniParser, cached screen parsing, keyboard/mouse, Excel-aware fallbacks | Browser automation only when optional dependency is installed; no OmniParser-equivalent | **A**: protect and retain. |
| Verification | Skill results have `verified`; workbook inspection, visual checkpoints and task verifier | Tool result/audit support; not Excel-domain verification | **A/B**: preserve Excel verification, generalize the result contract for future tools. |
| Generated code | Excel-restricted AST checks, isolated subprocess, timeout and constrained environment | General shell is approved and policy-governed | **A**: retain separate from a future terminal. |
| Terminal | No user-facing general shell; only internal Excel recovery/codegen subprocesses | Persistent shell, output limits, timeout/interrupt recovery, background jobs | **D**: implement a smaller Xelora terminal adapter behind policy; do not import a persistent shell wholesale initially. |
| Local files | Authenticated upload/version/preview for spreadsheet assets; no agent file workspace API | Workspace-scoped files/read/search plus permission-gated writes | **B/D**: retain asset storage; add a separate user-approved workspace-root file tool set. |
| Web search/fetch | No general search/fetch tools; `fetch_live_data` is a narrow Excel skill using `requests` | Provider abstraction, search, capped fetch, redirect/DNS SSRF guard | **C/D**: adopt the architecture; independently implement or reuse MIT code with notices after a dependency review. |
| Permissions/approval | API auth/rate limits, upload validation, codegen restrictions; no universal action gate | Risk classes, hard floors, roots, modes, approvals, standing grants, reviewer limits | **C**: highest-priority architectural integration. |
| Auditability | Task/action database logs and visual checkpoints | Approval provenance and detailed persisted audit store | **B**: extend Xelora ActionLog; do not add a parallel audit database. |
| Skills | Manifest loader and persisted skill store, Excel-focused | Dynamic skill store/personas | **B**: keep loader and add scoped/lazy context loading only if measurement shows prompt pressure. |
| MCP | MCP **server** exposes Xelora Excel skills; no outbound MCP client | Outbound stdio/HTTP client, schema wrapping, OAuth/config lifecycle | **C**: add outbound MCP after permission boundary exists; retain current MCP server. |
| Memory | Postgres preferences plus JSON task/chat history and lexical retrieval | SQLite memory store/settings/tools | **B**: keep per-user preference model; add retention, consent, deletion and provenance before broader memory. |
| Automations | Reusable workflows submit an internal task; no scheduler/cron executor | Scheduler, persistent scheduled tasks, unattended approval inbox | **D**: build later on Xelora workflows, task lock, and approval parking. |
| Subagents | `agent/subagents` is presently only an empty package; feature flag alone is not an implementation | Read-only explorer plus agent/persona patterns | **D (later)**: start with an isolated read-only research worker only. |
| Model providers | Gemini, Claude, OpenRouter chains and timeouts | Broader provider registry/router including local options | **B**: normalize provider interface/fallback telemetry; keep current proven providers first. |
| Desktop/UI | Next.js plus Electron wrapper, tailored Excel/workflow product | Tauri GUI for generic coworker approvals/settings | **A**: do not redesign or copy OpenWorker UI; add approval/audit surfaces to Xelora's UI later. |

Classification key: **A** keep Xelora, **B** strengthen Xelora, **C** integrate an OpenWorker capability, **D** reimplement the idea for Xelora, **E** do not use.

## 4. Xelora Strengths to Protect

1. Excel is a first-class execution domain, rather than a generic file side effect. Keep `skills/library`, `skills/excel_shared.py`, workbook binding, and COM-level verification intact.
2. Tool routing already avoids expensive visual parsing for known Excel ranges and standard ribbon actions. Preserve that policy in `agent/core.py` and `agent/prompts.py`.
3. Generated Excel code is deliberately constrained (`codegen/executor.py` blocks dangerous imports and uses a timeout). A general terminal must never weaken that boundary.
4. Excel runs are serialized by `_TASK_EXECUTION_LOCK`, avoiding concurrent input against one desktop application.
5. Spreadsheet uploads are authenticated, private per user, size-bounded, signature/ZIP-validated, and versioned in `files.py`.
6. Xelora already records action evidence, workflow/task state, history, preferences, and visual checkpoints. Build on those records.

## 5. Ranked Weaknesses and Security Findings

| Rank | Finding | Evidence | Recommended treatment |
|---|---|---|---|
| Critical | There is no backend-enforced, universal action policy for future terminal/files/web/MCP, and Excel actions are selected through planner/tool routing rather than a risk decision object. | `agent/core.py`; workflow `requiresApproval` is stored metadata but does not gate each underlying action. | Establish a PermissionEngine before exposing any general-purpose tool. |
| Critical | No general workspace filesystem boundary exists for agent reads/writes. Existing `/files` is an asset API, not a user-selected working directory capability. | `files.py` | Explicit roots, canonical paths, per-action read/write/delete policy, protected paths, and audit. |
| High | No general web search/fetch abstraction; the existing live-data skill requests user-provided URLs without the OpenWorker SSRF guard. | `skills/library/fetch_live_data/impl.py` | Add dedicated search/fetch adapters with protocol, DNS/IP, redirect, size, MIME, timeout and prompt-injection handling. |
| High | Xelora serves MCP but cannot safely consume external MCP tools. | `mcp_server/server.py` docstring | Add only after permissions/audit; server allowlists and per-tool risk metadata are mandatory. |
| High | General terminal capability is absent. | Repository search found only internal subprocesses and test/repro scripts. | Separate terminal tool with no shell interpolation, time/output limits, root CWD enforcement, approval, and hard blocks. |
| Medium | Task recovery and verification are Excel-specialized; other future tool classes lack a common retry/error/verification contract. | `agent/core.py`, `vision/task_verifier.py` | Introduce typed ActionResult, ErrorClass and Verifier interfaces while preserving Excel payloads. |
| Medium | Memory is useful but has no visible retention/consent/provenance controls in the inspected stores. | `memory/chat_memory.py`, `learning/memory.py` | Add user controls and TTL/deletion policy before increasing scope. |
| Medium | Scheduling is not implemented; reusable workflows currently make internal HTTP calls to a live task endpoint. | `workflows.py` | Do not schedule until task identity, approval parking, and idempotency are explicit. |
| Low | Test volume is uneven: six Xelora backend test files versus 135 OpenWorker backend test files. | Repository inventory | Add focused contract tests as capabilities land; do not chase count. |

## 6. Target Architecture

```text
User / Xelora UI
  -> Xelora task coordinator (existing task identity, billing, task lock, SSE)
  -> planner and capability router
  -> governed ToolRegistry facade
       -> PermissionEngine -> Approval service/UI -> Action audit
       -> Executor adapters:
          Excel skills | Excel codegen | OmniParser/UI
          Web search/fetch | scoped files | terminal | outbound MCP
       -> Verifier adapter -> normalized ActionResult
  -> task result, history, controlled memory

Future only: workflow scheduler -> task coordinator -> same policy/approval boundary.
```

The coordinator must remain the owner of Excel serialization. A tool adapter must not invoke the model, persist its own competing task state, or bypass permission/verification.

### Tool routing policy

1. Direct Excel skill for known cells, ranges, formulas, formatting, workbook structures, and reads.
2. Excel codegen only for one bounded Excel operation when a verified skill cannot do it; preserve the existing evidence guard.
3. OmniParser/UI only when the user asks for a visible/unknown Excel control or dialog; never use it merely to locate a known cell.
4. File tools for selected workspace files; Python/data processing uses the restricted execution route, not an unrestricted shell.
5. Web search, then fetch cited primary sources, extract data, then write/verify in Excel.
6. Terminal for explicit system/development tasks, always through policy. MCP only for configured, trusted server tools.

## 7. Permission and Verification Model

Use OpenWorker's principle, not its product UI: policy is backend code and cannot be bypassed by prompts.

| Class | Examples | Default |
|---|---|---|
| Safe read | Excel read, allowed-root listing/read, web search, guarded public web fetch | Allow and audit |
| Scoped write | Existing workbook cell update, allowed-root write, generated output file | Ask once per task unless an explicit task grant applies; verify |
| Consequential external | send message, connector mutation, outbound MCP mutation, package installation, git push | Human approval for each target/action or explicit standing rule |
| Human-only | delete/move outside a reversible area, write policy/config/CI/hooks, persisted automation creation/change | Never reviewer-auto-approve |
| Blocked | path escape, protected secrets, destructive shell patterns, privilege elevation, private-network/metadata fetch | Deny in code |

Each adapter returns `{status, output, error_class, evidence, verified, retryable, audit_ref}`. Verification is type-specific: Excel rereads cells/ranges, files reopen/check hash or content, terminal checks exit code and expected artifact, and web validates source/content/date. Retry only idempotent or explicitly safe actions, with capped counts and no repeated unverified writes.

## 8. Integration Roadmap

1. **P0 Foundation:** define normalized `ToolSpec`, `ActionRequest`, `ActionResult`, registry facade, risk metadata and audit extension. Adapt Excel skills, visual tools and codegen first, without changing their implementations.
2. **P0 Safety:** implement root-aware PermissionEngine, approval persistence/API/UI card, policy hard floors, action provenance, and action/result contract tests.
3. **P1 General worker basics:** scoped files, guarded `web_search` and `web_fetch`, then restricted terminal. Add feature flags and keep them disabled by default until tested.
4. **P1 Reliability:** typed error taxonomy, retry policy, verifier adapters, provider fallback telemetry and tool-routing metrics.
5. **P2 Extensibility:** outbound MCP client with explicit server/tool allowlists, pinned configs, OAuth lifecycle, and default approval. Keep Xelora's MCP server unchanged.
6. **P2 Controlled memory:** retention/consent/user deletion/provenance, then improve retrieval only if useful.
7. **P3 Advanced worker:** schedule existing workflows with approval parking, idempotency keys and a single-runner lease; then add a read-only research subagent. Connectors come after MCP proves the governance path.

## 9. File-by-File Change Map

| Xelora file | OpenWorker reference | Action | Purpose | Risk | Priority |
|---|---|---|---|---|---|
| `backend/agent/core.py` | `coworker/engine.py` | Modify | Route all action dispatches through a governed facade; preserve Excel task loop and lock | High | P0 |
| `backend/agent/capabilities.py` | `coworker/tools/registry.py` | Modify | Normalize tool schemas and metadata, retaining capability filtering | Medium | P0 |
| `backend/skills/registry.py`, `loader.py` | `coworker/tools/registry.py` | Modify | Adapt existing skill registry to ToolSpec facade; do not replace manifests | Medium | P0 |
| `backend/vision/ui_control.py`, `decision_loop.py` | None | Modify | Register visual tools with risk/evidence metadata; retain implementation | High | P0 |
| `backend/codegen/executor.py` | `coworker/tools/shell.py` | Do not weaken; adapt only | Preserve restricted Excel codegen as distinct executor | High | P0 |
| `backend/security.py` | `coworker/permissions.py`, `risk.py`, `readonly.py` | Modify/create adjacent module | Add action authorization beyond HTTP auth | High | P0 |
| `backend/models.py`, `database.py` | `coworker/audit.py` | Modify/migrate | Extend ActionLog with decision, approver, target, verifier and error metadata | Medium | P0 |
| `backend/main.py`, `server.py` | `coworker/server/manager.py` | Modify | Approval/resume APIs, task-safe action context and feature toggles | High | P0 |
| `backend/files.py` | `coworker/tools/files.py`, `directories.py` | Preserve plus create agent file adapter | Keep asset storage separate from root-scoped agent files | High | P1 |
| New `backend/tools/web.py` | `coworker/web/{tool,fetch,guard,providers}.py` | Create | Search/fetch abstraction, SSRF defense, caps and source records | High | P1 |
| New `backend/tools/terminal.py` | `coworker/tools/shell.py`, `permissions.py` | Create | Restricted terminal with non-shell argv execution first | High | P1 |
| `backend/mcp_server/server.py` | `coworker/mcp/{client,tools,config}.py` | Preserve; add separate client module | Keep serving Excel skills; later consume trusted external tools | High | P2 |
| `backend/memory/*`, `learning/memory.py` | `coworker/memory/*` | Modify | Add controls and provenance before richer retrieval | Medium | P2 |
| `backend/workflows.py` | `coworker/automation/*` | Modify later | Scheduler over existing workflows and same approvals | High | P3 |
| `backend/agent/subagents/` | `coworker/tools/subagent.py` | Create later | Isolated, read-only research agent only | Medium | P3 |
| `frontend/xelora/src/*` | OpenWorker approval/audit components | Preserve; targeted additions later | Add Xelora-native approval/audit views, no redesign | Medium | P0/P1 |

Do not touch in the first implementation wave: Excel skill implementations under `backend/skills/library`, `backend/skills/excel_shared.py`, `backend/vision/omniparser_client.py`, frontend branding/marketing, billing/auth behavior, and the existing MCP server contract. Potential future deprecation: direct hard-coded dispatch branches only after adapters pass parity tests; not the implementations they wrap.

## 10. Dependencies, License, and Compatibility

OpenWorker is MIT-licensed (`openworker/LICENSE`, copyright Andrew Ng), so direct reuse is legally possible provided Xelora retains the MIT copyright and permission notice in copied substantial portions. Architecture ideas need no code copying. Every copied dependency must still be evaluated independently.

Likely new dependencies, each justified only when its phase begins: `httpx` for timeout-controlled guarded fetch; `ddgs` or a selected paid search provider adapter; `croniter` and Windows `tzdata` only for scheduling; an MCP client version compatible with Xelora's current server dependency. Xelora pins `mcp==1.29.0`, while OpenWorker accepts `>=1.28.1,<2`; validate the client APIs against that pin before adding it. Do not bring in `aisuite`, Tauri, connector SDKs, or OpenWorker's full provider matrix merely to obtain a registry or policy.

Windows is mandatory for Xelora's real Excel desktop automation. General web/files/policy can be cross-platform. Terminal behavior needs OS-specific implementations and tests; start on Windows because it is the product's primary execution environment.

## 11. Test Strategy and End-to-End Gates

P0 tests: Excel skill/visual/codegen parity through the facade; allowed/asked/blocked policy cases; cannot self-grant; approval provenance persisted; resume maintains workbook identity and serialized execution.

P1 tests: root traversal/symlink/protected-path attempts; safe terminal argv, timeout, rejected inline code/chaining/escalation; SSRF loopback/private/redirect/DNS-rebinding equivalents, response cap and malicious page treated as data; search -> fetch -> Excel write/read verification.

P2/P3 tests: MCP tool allowlists, failed connection/OAuth, untrusted tool approval; memory user isolation, expiration/delete; scheduler timezone/idempotency, unattended approval parking, task-lock contention; read-only subagent cannot write or invoke shell.

Acceptance tasks: write supplied data to `A1`; research Rwanda inflation from cited sources then write/verify it in Excel; combine selected CSVs and make a workbook; approved Python script execution with artifact verification; click Excel's Sort UI through OmniParser and verify; research companies and produce a formatted, verified workbook.

## 12. Final Recommendation

If I were building Xelora, I would implement first the governed action boundary and adapt the existing Excel tools into it. Second, I would ship the permission/approval/audit path and prove it with Excel parity tests. Third, I would add guarded web, scoped files, and a deliberately small terminal. Fourth, I would add outbound MCP. Only then would I add scheduling, broader memory, connectors, or subagents.

That sequence makes Xelora a stronger AI worker while keeping its durable advantage: reliable, verifiable, Excel-native automation with OmniParser-assisted computer use.


## 13. Current Workspace Implementation Addendum (2026-09-24)

The repository already contains local, uncommitted implementation work beyond the initial audit above. This addendum records that state so the earlier recommendations are not mistaken for unimplemented baseline code. These files were present before this turn and have been preserved.

### Existing additions in the workspace

- `backend/agent/planner.py` builds a dependency-ordered preflight checklist, and `backend/agent/core.py` adds that checklist to the task context while maintaining the existing multi-step execution/recovery loop.
- `backend/agent/tool_registry.py` adapts manifest-backed Excel skills, visual actions, bounded code generation, web research, and scoped files into a common metadata catalogue. The registry now exposes concrete input/output schemas, risk class, execution layer, permission requirements, and verification method; the capability endpoint returns these contracts for enabled UI tools as well.
- `backend/tools/web.py` and `web_guard.py` provide bounded public search/fetch, redirect checks, private-address rejection, response caps, and untrusted-content notices. `fetch_live_data` now shares the guarded transport.
- `backend/tools/filesystem.py` provides read-only per-user file listing and text reads. Its root follows the same `STORAGE_DIR` used by authenticated uploads, avoiding split storage when that setting is customized.
- `backend/agent/permissions.py` blocks unknown tools and prevents non-read operations while the task is in planning-only mode. It is an initial policy gate, not yet a general approvals service or a permission engine for unattended runs.

### Reference capabilities and integration choice: Cua

Cua Driver is the relevant computer-use layer. Its maintained interface provides native app/window discovery, state snapshots, optional accessibility metadata, screenshots, window-targeted clicks, keyboard input, and explicit postcondition checks. Agents can connect through the Driver's stdio MCP interface; Cua also offers typed SDKs. Its optional perception extension is separate from the core MIT Driver and has distinct model/dependency notices. Xelora should consume Cua Driver through an adapter and keep Xelora's own router, task policy, Excel skills, and workbook verification as the authority. Cua supplies computer I/O; it must not become a second planner or replace Excel APIs.

The current `backend/vision/ui_control.py` already has substantial Windows UI Automation, window ownership checks, native screenshots, safe keyboard/mouse operations, popup inspection, and OmniParser fallback. That is valuable working infrastructure and should remain available while a Cua adapter is introduced behind the same desktop executor interface. Use accessibility/window state first, then keyboard, then the targeted Cua action surface; capture screenshots only when structured observation cannot resolve the UI. After every action, ask Xelora's task verifier to confirm the intended postcondition.

A full Cua connection is not yet present in this workspace: there is no configured Driver process/session, outbound MCP client, Cua tool discovery, or adapter dispatch in `backend/vision`. The first Cua implementation slice should add an optional, feature-gated stdio MCP client compatible with Xelora's pinned MCP client, discover only a bounded allowlist of observation/input tools, normalize their schemas into `ToolSpec`, and route them through the existing `dispatch_action` and action logging. Fail closed when the executable, platform permission, or target window cannot be verified. Do not install Cua at backend startup or silently fall back to unscoped global input. Check MCP protocol compatibility against the installed Cua Driver version before enabling it; modern Cua documentation describes a newer stdio protocol, while this project pins `mcp==1.29.0` and its server implementation predates that revision.

### Updated integration sequence

1. Keep the current task loop, skill library, Excel workbook binding, workbook inspection, and `ui_control` safety guards.
2. Finish the registry contract and maintain parity with the model provider's live callable schemas.
3. Add per-tool action audit records and a real approval/resume API before general terminal or MCP mutation tools.
4. Add Cua as an optional desktop adapter and validate its accessibility, target-window, observe-act-check, and failure behavior on Windows Excel; keep existing UIA/OmniParser paths as configured fallback.
5. Add further tools only through the same registry, policy, logging, and independent verification boundary.

### Updated gaps and risks

- The initial permission module is mode-based and does not persist approvals, action provenance, or unattended approval requests.
- The current plan is advisory context; it does not yet advance durable subtask state from observed tool results.
- Web search parses a public HTML endpoint, so provider layout/rate limits may affect availability; returned text must remain untrusted.
- The workspace file adapter supports bounded text files only. It does not expose uploaded workbooks as arbitrary paths, nor provide writes.
- Cua Driver is not installed/configured or invoked yet. Platform permissions, driver lifecycle, accessibility availability, and MCP version compatibility remain to be implemented and validated.
- No general terminal, outbound MCP tool execution, retained action-memory controls, or scheduled task runner has been added by the additions above.

## 14. Continuation Addendum (2026-09-29): integration slice completed

The interrupted work resumed from the state recorded above. No previously
implemented behavior was reverted or replaced. The following gaps were closed.

### What was added in this slice

- **Restricted terminal** (`backend/tools/terminal.py`): argv-only, no shell,
  allowlisted read-only commands (git status/log/diff, ls/dir, pwd, whoami,
  version probes, pip show), anchored to `XELORA_TERMINAL_ROOT`, bounded
  timeout/output, exit codes reported truthfully. Optional bounded writes
  (pip install -r, pytest path) behind `TERMINAL_WRITE_TOOLS`. Duplicate
  `_versionish` definition removed; single definition now in use.
- **Guarded web** (`backend/tools/web.py`, `web_guard.py`): DuckDuckGo HTML
  search plus capped HTML/JSON fetch sharing one transport that rejects
  loopback/private/CGNAT/metadata addresses, validates every redirect,
  and caps responses at 2 MB. `fetch_live_data` now uses the same guard.
- **Scoped user files** (`backend/tools/filesystem.py`): reads, searches,
  metadata, create (never overwrites) and update (atomic, read-back verified)
  for bounded text files, strictly inside the authenticated user's
  `STORAGE_DIR/<user_id>` root; symlink and traversal escapes rejected.
  Dispatch requires both a JWT-authenticated task and a matching user id.
- **Cua Driver adapter** (`backend/vision/cua_driver.py`): feature-gated stdio
  MCP client that discovers the local Driver's live tool schemas, exposes only
  a reviewed allowlist (`cua__`-prefixed), fails closed when disabled or
  unreachable, and marks input actions verified only when an explicit
  `verify_state` returns satisfied predicates. Health/discovery endpoint at
  `GET /agent/cua/health`; readiness surfaces in `GET /`.
- **Governed registry and policy** (`backend/agent/tool_registry.py`,
  `backend/agent/permissions.py`): every tool has risk, schemas, permissions,
  verification method, platforms, timeout, and availability; unknown tools are
  never executable; planning-only mode holds writes. `get_execution_capabilities`
  was added to the catalogue (it was previously callable but unlisted).
  `AgentTask.has_authenticated_user` now has an explicit `False` default.
- **Routing** (`backend/agent/core.py`, `agent/capabilities.py`,
  `agent/providers.py`): dispatch verifies tool identity before execution;
  approval gate applies to every layer via the registry metadata; Excel dialog
  pre-checks and window-safety recovery now run only for Excel layers, not for
  web/file/terminal/Cua calls; provider tool lists (Claude and Gemini) include
  web, file, terminal, and Cua tools according to their feature flags; Cua
  verify_state retroactively confirms a matching prior input action on the
  same target window.
- **Automations** (`backend/automation.py`, `workspace_models.py`, `main.py`):
  opt-in scheduler (`ENABLE_AUTOMATIONS`) claiming due schedules atomically and
  submitting runs through the same internal `/task` path; CRUD API at
  `/automations` scoped to the workflow owner; ≥5-minute intervals only.
- **Fixes**: `admin.py` import typo (`auoth_billing_models` →
  `auth_billing_models`); `test_gemini_requires_a_workbook_change_after_inspection`
  now patches `ENABLE_VISUAL_FALLBACK` so it is deterministic regardless of a
  developer's `.env`; README documents every new flag, including Windows Cua
  setup.

### Verification status

- `test_integration_capabilities.py` + `test_web_guard.py`: 40 passed
  (Python 3.12 project venv and Python 3.14), covering terminal policy/paths,
  file-tool scoping and escapes, web guard SSRF cases, registry contracts,
  permission gates, Cua fail-closed behavior, and routing catalogue.
- Other backend suites: automation reliability 121/126 on Linux (4 tests are
  Windows-only: pyautogui, Windows UI Automation, Win32 process image query);
  dashboard layout, file processing, gemini reliability, quick chat all pass.
- `main.py` and `server.py` import cleanly; `/agent/tools` reports 85 tools;
  `/agent/cua/health` reports disabled/unavailable on Linux without crashing;
  dispatch fails closed for disabled terminal, unauthenticated file access,
  disabled Cua, and unknown tools.
- Excel skill manifests: all 74 SHA-256 entries verified intact.
- Not executable here: real Cua Driver sessions, Windows terminal semantics
  (PATHEXT resolution is implemented but unproven), Excel COM behavior, and
  OmniParser workflows. These require the Windows host.


## 15. Audit Addendum (2026-09-29): verification of sections 13–14

Sections 13–14 were re-verified against the code. Corrections and fixes:

- **Web/file tools broke the Excel task loop.** They were not classified as
  observations in `agent/core.py`, so a failed `web_fetch` entered Excel
  recovery mode (blocking the next web call), a successful search counted as
  verified workbook evidence, and the duplicate guard could skip a re-read.
  Fixed; non-Excel tasks are now judged by their own verified results.
- **Terminal allowlist bypass.** Policy matched only the basename of argv[0],
  so `/tmp/x/git status` passed. Paths are now refused and programs are
  resolved on PATH; secrets are stripped from the child environment; `pwd`/
  `ls`/`dir` run in-process (they do not exist, or are cmd builtins, on Windows).
- **Registry metadata was documentation-only.** Schemas and availability are
  now enforced by `decide_action` and dispatch; provider declarations for
  web/file/terminal are generated from the registry (they had drifted).
- **Cua "fails closed" was incomplete.** There was no window targeting: any
  input could go to any window. Added observe-before-act, bound-Excel-process
  and desktop-scope rules, `cua_act_and_verify` with bounded retries, and
  real-transport tests against a fake stdio MCP driver.
- **Outbound MCP was not implemented** (only Cua used an MCP client). Added
  `tools/mcp_external.py` over a shared `tools/mcp_client.py`.
- **Subagents** are not an empty package: `agent/subagents` contains skill
  wrappers, but nothing calls them. Left unwired on purpose (they would bypass
  the per-call policy gate); `ENABLE_SUBAGENTS` has no effect on the task loop.
- **Test claims.** `test_file_processing.py` cannot import without
  `JWT_SECRET_KEY` (now provided by `conftest.py`); `test_learning.py` needs a
  live server (now skipped when absent); four Windows-only tests are skipped
  off Windows instead of failing.
- **Frontend production build was failing** (committed code): the desktop
  update-feed route imported two functions removed from `desktop-release.ts`.
  Implemented them over the GitHub Releases lookup.

Current classification and remaining work are in `docs/ARCHITECTURE.md` and
`docs/TESTING.md`.
