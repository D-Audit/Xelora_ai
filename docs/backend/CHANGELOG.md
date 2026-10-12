# What changed in this update

Straight list - what was actually done, what was NOT done and why, no
in-between.

## 2026-10-12 (3) - professional frontend, real sign-in flows

**Done**

- **Design.** Neutral palette with green as the accent; calmer buttons and
  inputs; outline icons without tinted backgrounds.
- **Landing page** rebuilt around what the product really does (product shot,
  capabilities, examples, how it works, security, pricing, FAQ). Removed false
  claims (AES-256, offline mode, undo of any step, batch processing).
  `/features`, `/how-it-works`, `/solutions`, `/resources` and the mock
  `/desktop` preview now redirect.
- **Pages:** Pricing (real plans, no fake checkout), Security, Download (live
  GitHub release), Status (live checks), Contact, and new Terms, Privacy,
  Acceptable Use and Cookie policies (`components/legal`). Business details
  come from `NEXT_PUBLIC_*` settings in `lib/site.ts`.
- **Auth:** form-only sign-in and sign-up pages; real forgot/reset password
  and email confirmation (`auth.py` + `emailer.py`, Resend or SMTP); working
  "Keep me signed in"; profile and password changes; Google accounts can set a
  password. Google sign-in from Xelora Desktop opens the system browser and
  hands the session back via `xelora://` (`lib/desktop-handoff.ts`).
- **App:** new sidebar (New chat, sections, recents, real usage, account
  menu); chat page with Markdown, work steps, sources and status lines; chat
  available on the web too; real Settings, Task history, Usage, workflow
  editing and invitations; short honest onboarding. No user-facing page uses
  mock data any more (admin pages still do).
- **Fixes:** website plan limits now match the backend catalog; timestamps
  without a timezone are read as UTC ("2h ago" bug); quick answers are saved
  as "answered".

**Not done**

- Admin pages still show mock data.
- Account deletion and data export are handled by email, not in the app.

## 2026-10-12 (2) - conversations, speed, signed installer

**Done**

- **The agent remembers the conversation.** A follow-up used to start the
  model with only the new message, so "make it bold" or "use the Sales sheet"
  had no context. `AgentTask.resume` now prefixes the recent turns
  (`conversation_context`, last 8, bounded) while still dropping old tool history.
- **"hi" no longer opens Excel.** Messages reaching `/task` that need no workbook
  (greetings, general questions) are answered directly (`main._answer_directly`)
  with status `answered`, saved to history, without starting Excel or waiting
  for Xelora Desktop. Replies inside an Excel conversation, answers to the
  agent's questions, and plan confirmations always go to the agent.
- **Smarter routing.** Questions about the user's own workbook ("total in
  column C?", "summarise my sheet") go to the agent; how-to and general
  questions get a quick answer; spreadsheet-style requests ("create a budget")
  run as tasks. The server decides the context from the saved conversation.
- **Excel opens only when needed.** `run_task` asks the capability router first;
  research or file-only requests no longer create a blank workbook.
- **Models.** Excel tasks lead with `gemini-3.5-flash` (most capable in the
  chain); quick chat uses `QUICK_CHAT_GEMINI_MODEL` (fast) with one fallback.
- **Installer.** Xelora icon on app/installer/uninstaller, "Xelora" product and
  company details, `Xelora-Setup-<version>.exe`, and a signing hook
  (`desktop/scripts/sign.js`: Azure Trusted Signing in CI, or a certificate on
  your PC) with an optional "refuse unsigned releases" switch.

**Not done**

- "Unknown publisher" only goes away with a code-signing certificate, which
  has to be bought from a certificate authority after identity checks
  (docs/CODE_SIGNING.md). Everything else is ready for it.

## 2026-10-12 - memory, file storage, web search

**Done**

- **Quick chat works and is used.** `config.py` never defined the
  `FAST_CHAT_*` settings `quick_chat.py` reads, so every non-greeting reply
  failed with "try again". Added them. The web chat page also never called
  `/api/chat`: every message, even "hi", became an Excel task. It now asks
  `/chat` first and only starts a task for workbook requests.
- **Web search when Xelora doesn't know.** Quick chat can call `web_search` /
  `web_fetch` itself (up to `QUICK_CHAT_MAX_TOOL_ROUNDS`), on Gemini and Claude,
  with today's date in the prompt. Replies cite `[n]` and the UI lists those
  sources as links. Search tries Tavily, Brave, then Serper (whichever keys are
  set), then DuckDuckGo, with a 10-minute cache. The desktop agent searches
  through the cloud (`/agent-link/web-search`), so keys stay on the server, and
  falls back to searching from the PC. The agent prompt now says to search
  instead of guessing current facts.
- **Memory is used, not just written.** Related past tasks and learned skills
  go into the agent's system prompt (`memory/context.py`) and into quick chat,
  labelled as context, not instructions. Matching ignores stopwords; a past
  task no longer counts as relevant just because it succeeded.
- **Memory is safe under concurrency and bounded.** `update_records()` does
  read-modify-write under a lock (a row lock in Postgres), so two tasks
  finishing together no longer overwrite each other. Lists are capped
  (`MEMORY_MAX_*`), large tool results are trimmed, and a task's actions are
  logged in one write instead of one per action.
- **Fixed a deadlock in desktop memory sync** (cloud memory endpoints now use
  `read_stored`/`write_stored`, never the remote route), plus a test fixture
  bug; `test_agent_link.py` had been hanging.
- **Uploads survive restarts.** `blob_store.py` keeps file contents in
  Postgres (`FILE_STORAGE=database`, the Render default) or an S3/R2 bucket
  (`FILE_STORAGE=s3`); local disk becomes a cache restored on demand. If
  durable storage fails, the upload is rejected rather than half-saved.
- **Every message is saved in chat history.** A quick answer is stored in the
  open conversation (or starts a new one in the sidebar), with its sources.
  An Excel request later in that conversation continues it, and the agent sees
  the preceding quick answers ("put that rate in B2" works).

**Not done**

- Files uploaded before `FILE_STORAGE` was switched are not migrated; they
  must be uploaded again.
- With no search key on a cloud host, DuckDuckGo usually blocks the request;
  Xelora then says it could not search. A key is the real fix.

## Earlier update

### Done

**Skill architecture rebuilt.** Every skill moved out of large flat files
(`skills/excel_write.py`, etc. - deleted) into `skills/library/<name>/`:
a `SKILL.md` (name, category, description, JSON input schema - human- and
AI-readable) plus a small `impl.py` (one `run()` function). 66 skills total.
`skills/loader.py` discovers and loads them at startup; `skills/registry.py`,
`agent/core.py`, and `mcp_server/server.py` needed ZERO changes - they still
talk to the same `SKILL_REGISTRY` dict, just populated a different way.

**Skill-loading security.** `skills/library/_manifest.json` pins a SHA-256
hash of every skill's `SKILL.md` and `impl.py`. A folder not in the
manifest, or one whose hash doesn't match, is refused at load time and
logged loudly. Verified this actually works (tampered a hash, confirmed the
skill was refused and every other skill still loaded fine; regenerated the
manifest, confirmed it loaded again). Run `tools/generate_skill_manifest.py`
after any legitimate skill add/edit.

**VBA reliability fixes**, in `skills/excel_shared.py`:
- `display_alerts = False` (save-format prompts)
- `AutomationSecurity = 3` (macro-security popups - matters now that
  `create_vba_macro` writes real macros)
- `AskToUpdateLinks = False`, `AlertBeforeOverwriting = False`
- Never-saved workbook is auto-saved to a real path on first connection
  (fixes the "stuck on insert_formula" hang - that was Excel's native
  Save-As dialog, not an Excel alert, which is why `display_alerts` alone
  didn't fix it)
All wrapped in try/except per-setting since not every property exists on
every Excel version.

**Formula-writing contradiction fixed**, in `agent/prompts.py`. The old
prompt told the AI two different things in the same system prompt: never
assign `.formula`/`.formula2` directly (correct), but write ALL formulas via
`.value = "..."` in generated code (wrong, and the actual cause of
intermittent SORT/UNIQUE/FILTER failures via codegen - `.value` is the least
reliable path for dynamic arrays). The contradictory block is gone; one
consistent rule now: formulas go through the `insert_formula` skill, period.

**Mandatory end-of-task self-review**, also in `agent/prompts.py`. The AI
must now re-read the user's original instruction, check off each requested
item against actual tool results (not intentions), compare any
expected/answer-key values the user gave against what was actually
calculated, and separate "fully succeeded" from "attempted but wrong" from
"skipped and why" in its final message - rather than declaring success
because nothing threw an exception.

**Baseline formatting hygiene.** Added a standing rule: call
`auto_fit_columns` after writing any table/dataset, even if the user didn't
ask - don't leave `####` or truncated text as the default output.

**Security hardening** (new `security.py`, `main.py` updated):
- Every endpoint now requires the API key (constant-time comparison) -
  `/knowledge/*` previously had NO auth check at all; fixed.
- App refuses to start with no API key configured, unless `ALLOW_NO_AUTH=true`
  is set explicitly - no more silently-open-by-omission.
- Basic in-memory rate limiting (60 req/60s default, configurable) on every
  endpoint.
- `/knowledge/add`'s `file_path` is now confined to
  `KNOWLEDGE_INGEST_ALLOWED_DIR` - closes a path-traversal / arbitrary-file-
  read hole that existed before.
- CORS is opt-in via `ALLOWED_ORIGINS` (empty by default - no cross-origin
  browser access unless you explicitly list origins).

**24 new skills**, closing every gap identified over this conversation:
structure - `delete_row`, `delete_column`, `merge_cells`, `unmerge_cells`,
`clear_range`, `copy_sheet`, `set_sheet_visibility`, `reorder_sheet`,
`unprotect_sheet`, `open_workbook`, `create_new_workbook`,
`group_rows_columns`; formatting - `add_hyperlink`, `add_comment`,
`set_page_layout`; dashboard - `refresh_pivot_table`, `modify_chart`,
`delete_chart`, `add_sparkline`, `insert_picture`, `add_shape`,
`add_dropdown_control`; data - `set_autofilter`; VBA - `list_vba_macros`,
`delete_vba_macro`.

**All 66 skills verified to actually load** through the manifest-checked
loader (ran it, confirmed the count, confirmed tamper detection blocks a
corrupted one and lets the other 65 through fine).

### NOT done, and exactly why

**Application-level undo.** Excel's own `Application.Undo` is unreliable
after automation touches a workbook (documented Excel/COM behavior, not
fixable by more code). A real fix means recording "before" state per action
in `ActionLog` and adding a reverse-action mechanism - that's a genuine
architecture change (skills would need DB/task access they don't currently
have), not a quick addition, so it's being named here rather than faked with
something that doesn't actually work.

**Solver integration.** Requires the Solver add-in installed and enabled on
the specific machine running Excel - no code path can install an Office
add-in for a user. Not attempted.

**Password cracking/removal without the password.** Not attempted, by
design - this isn't a capability gap, it's a line that shouldn't be crossed.

**Ribbon/Quick Access Toolbar customization.** Lives in separate `customUI`
XML outside the COM object model entirely - would need `zipfile`-level
`.xlsm` editing, which isn't in the codegen sandbox's import allowlist. Not
built; rare enough in practice that it wasn't prioritized this round.

**Cloud-only/Excel Online-exclusive features, OAuth-gated Power Query first-
logins, WPS Office support.** All structural - this system drives desktop
Windows Excel via COM specifically. None of these are reachable from that
foundation no matter how many skills get added; documented, not solved.

**Codegen was NOT changed to call skill functions internally** - by explicit
decision partway through this conversation. `run_excel_code` stays fully
self-contained, writing its own raw `.api`/xlwings calls; the skill-first,
codegen-fallback routing in `agent/core.py`'s `dispatch_action` is unchanged.

### One thing worth testing first, honestly

This was built and verified in a Linux sandbox - the skill loader,
manifest/hash security, and Python syntax of every file were run and
confirmed working end-to-end. The actual Excel/COM calls inside each
`impl.py` (xlwings `.api.*` calls) could NOT be executed here, since that
needs real Windows + real Excel. A few of the newer, more unusual COM calls
(`SparklineGroups.Add`, `DropDowns().Add`, `Shapes.AddShape`) are correct per
the documented Excel object model but haven't been run against a live
workbook - test those specific ones first on your machine before relying on
them for anything important.
