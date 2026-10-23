Excel reliability audit — 2026-10-23
===================================

The audit covers request routing, planning, workbook observation, chart behavior,
and the existing backend suite. It does not certify every feature against native
Excel or prove that a live language model will always select the right actions.

Changes made
------------

- Clear spreadsheet requests and local file paths reach the Excel workflow instead
  of receiving a quick-chat refusal. Follow-ups can recover from a prior refusal.
- Planning hints reference registered skills, match whole words, avoid unsolicited
  duplicate removal, and preserve explicit dependency edges. Generic edits no
  longer suggest scenario analysis; summary text no longer matches “sum”.
- Analysis guidance distinguishes additive measures from IDs, dates and rates,
  preserves source data, reconciles summaries, selects suitable charts, and keeps
  narrow edits within scope. Guidance is advisory, not proof of execution.
- Range reads preserve two-dimensional shape and expose Excel errors as strings.
  Formula audits understand COM tuple matrices, report individual cell addresses,
  and count all detected errors even when the returned error preview is capped.
- Chart creation rejects unsupported types and duplicate names, cleans up failed
  creations, and verifies the resulting type. Chart edits use consistent scatter
  semantics and support linked titles through Excel's Formula property.
- Removed a pre-existing syntax error preventing the codegen package from importing.

Verification and limits
-----------------------

All 75 registered Excel skills have matching Python parameters and input schemas,
including required arguments. This is a catalogue contract check, not a live test
of all 75 operations. Backend coverage includes routing, provider tool schemas,
formula guards, data import, dashboard layout, code sandboxing, file ownership,
desktop/cloud relay, and memory storage. Excel objects and AI providers are
simulated where appropriate; real database and AI credentials were disabled.

The broad run passed 436 tests and skipped 5, with one failure in a restart test
whose fixture did not create the persisted Task row. After supplying the temporary
SQLite configuration and the row normally created by /task, that test passed on
rerun. New judgment regressions are in backend/tests/test_excel_judgment.py.
Frontend TypeScript checking passed with --noEmit --incremental false.

Native Windows release check (still required)
--------------------------------------------

Use a copy of a workbook with known expected totals. Include a single-column sheet,
leading-zero IDs, repeated categories, blanks, dates, and a deliberate =1/0 error.

1. Connect the rebuilt desktop agent and request analysis using a quoted local
   path containing spaces. Confirm it opens that file and uses its actual sheets.
2. Ask for a summary, pivot and dashboard. Complete the app's normal confirmation
   flow. Compare totals with independently calculated expected values; check that
   source rows and identifiers remain intact and that chart objects do not overlap.
3. Ask for a small cell edit. Confirm unrelated sheets and formatting stay intact.
4. Ask to inspect the single-column sheet and deliberate error. Confirm row shape
   and the exact error cell, then repair it and check recalculation.
5. Create and modify line, column and scatter charts. Link a chart title to a cell,
   change that cell, and confirm the title updates. Request an unsupported chart
   and confirm Xelora explains the limitation instead of substituting a column chart.
6. Save, close and reopen the result. Verify formulas, charts, pivots and source data.
   Restart the backend, then continue the conversation and confirm it reaches the
   desktop agent with the correct workbook context.
7. Exercise enabled installation-specific features separately: VBA trust/macros,
   PDF export, slicers, Power Query/database connectors, web providers and visual
   automation. Validate each against the installed Excel version and credentials.

Deploy the backend and ship a newly bundled desktop agent to deliver these fixes.
No release, push, deployment, or live Windows certification was performed by this audit.
