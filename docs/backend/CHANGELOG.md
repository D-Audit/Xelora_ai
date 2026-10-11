# What changed in this update

Straight list - what was actually done, what was NOT done and why, no
in-between.

## Done

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

## NOT done, and exactly why

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

## One thing worth testing first, honestly

This was built and verified in a Linux sandbox - the skill loader,
manifest/hash security, and Python syntax of every file were run and
confirmed working end-to-end. The actual Excel/COM calls inside each
`impl.py` (xlwings `.api.*` calls) could NOT be executed here, since that
needs real Windows + real Excel. A few of the newer, more unusual COM calls
(`SparklineGroups.Add`, `DropDowns().Add`, `Shapes.AddShape`) are correct per
the documented Excel object model but haven't been run against a live
workbook - test those specific ones first on your machine before relying on
them for anything important.
