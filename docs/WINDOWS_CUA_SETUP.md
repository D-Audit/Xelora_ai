# Cua Driver on the Windows Excel host

Cua Driver gives Xelora accessibility-first control of desktop windows
(window state / accessibility tree, element-targeted clicks, typing, keys,
value setting, and postcondition checks). It is optional: without it Xelora
uses Excel APIs, keyboard shortcuts, Windows UI Automation and OmniParser.

It must run **on the same Windows machine and interactive desktop session as
Excel and the Xelora backend**. A remote server cannot drive a user's local
Excel.

## Install (from the official Cua documentation)

Source: https://cua.ai/docs/how-to-guides/driver/install and
https://cua.ai/docs/cua-driver/reference/mcp-tools

```powershell
irm https://cua.ai/driver/install.ps1 | iex
cua-driver autostart kick
```

Requirements per Cua: Windows 10/11 or Windows Server **with an interactive
desktop session**.

## Diagnose

```powershell
cua-driver --version
cua-driver doctor
cua-driver status
cua-driver call list_apps
```

All four must succeed before enabling Xelora's integration.

## Enable in Xelora

In `backend\.env`:

```env
ENABLE_CUA_DRIVER=true
# Only if cua-driver is not on PATH (use the location `cua-driver doctor` reports):
CUA_DRIVER_COMMAND=
CUA_DRIVER_ARGS=mcp
# Keep both false unless you have a specific need:
CUA_ALLOW_DESKTOP_SCOPE=false
CUA_ALLOW_OTHER_APPS=false
```

Restart the backend, then:

```powershell
Invoke-RestMethod http://localhost:8000/agent/cua/health -Headers @{ "X-API-Key" = "<LOCAL_API_KEY>" }
```

Expected: `status: ready`, `mcp_reachable: true`, and a `tools` list with
`cua__get_window_state`, `cua__verify_state`, `cua__click`, `cua__set_value`, ….
If `status` is `unavailable`, `errors` and `setup_hint` say whether the
executable is missing or the MCP server did not answer.

## What Xelora exposes and enforces

Exposed (only if the running Driver offers them): `list_apps`, `list_windows`,
`get_desktop_state`, `get_screen_size`, `get_cursor_position`,
`get_window_state`, `verify_state`, `click`, `double_click`, `right_click`,
`drag`, `scroll`, `type_text`, `press_key`, `hotkey`, `set_value`,
`invoke_menu`, `set_window_frame`, `move_cursor`, `clipboard_read`,
`clipboard_write`, plus Xelora's `cua_act_and_verify`. Never exposed: app
launch/kill, recording, config, browser, extension install, and any tool not
listed.

Enforced in code: observe (`get_window_state`) before acting on a window;
input only to the task's Excel process; no desktop-scope input by default;
only satisfied `verify_state` predicates count as verification; at most 3
act→verify attempts.

## Validation checklist (Windows)

1. Open Excel with a workbook; start a Xelora task "click the Sort button on
   the Data tab and sort A1:D5 by column D descending".
2. In the backend log, filter `xelora.audit`: confirm `cua__list_windows` /
   `cua__get_window_state` precede any `cua__click`/`cua_act_and_verify`.
3. Confirm a `verify_state` result `verified: true`, and that the sheet order
   changed.
4. Negative checks: ask Xelora to click in Notepad → expect `wrong_window`;
   stop the Driver (`cua-driver` process) mid-task → expect a
   `driver_error`/`unavailable` step and a clear final message, not a crash.
