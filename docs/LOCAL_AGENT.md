# Xelora Desktop local agent

Excel lives on the user's PC; the API lives in the cloud. The local agent
connects the two, so a hosted Xelora can still drive each user's own Excel.

```
 Web app / Xelora Desktop window              Cloud API (Render)                 User's Windows PC
 ───────────────────────────────              ──────────────────                 ─────────────────
 "Add a totals row"  ──POST /task──────────►  queue for that user  ◄──claim───  local agent
                                              (TASK_EXECUTION=agent)            (bundled Python)
                                                                                 │ run_task()
                                                                                 │ ├─ Excel (xlwings, UI, Cua)
                                              /agent-link/llm/*  ◄──model calls──┤ └─ model calls
                                              adds server API key ──► Gemini/Claude
 progress / status / reveal  ◄──polls──────   mirror of the task  ◄──push every 1s─┘
 Pause  ──POST /task/{id}/pause──────────►    pause flag ──────────(next push)──► stops
```

## What happens, step by step

1. **Pairing (automatic).** The user signs in inside Xelora Desktop. The page
   (`LocalAgentBridge`) asks the cloud for an agent token
   (`POST /agent-link/pair`) and passes it to Electron. Electron stores the token
   encrypted with Windows DPAPI (`safeStorage`) in
   `%APPDATA%\Xelora\agent-link.json` and starts the agent. If a different user
   signs in, the desktop re-pairs for them.
2. **Waiting for work.** The agent long-polls `POST /agent-link/claim`, which also
   serves as its heartbeat. The "Excel agent connected" badge on the AI Agent page
   shows that this connection is live.
3. **A task arrives.** In agent mode, `POST /task` (and `/resume`) queue the task
   for that user instead of running it on the server. If no agent is online, the
   chat shows *"Waiting for Xelora Desktop…"*, and the task starts as soon as the
   desktop connects.
4. **Running locally.** The agent rebuilds the `AgentTask` from the job and runs
   the normal `run_task()`: the same skills, verification and Cua/visual layers as
   a local install, against the Excel on this PC.
5. **Model calls.** The agent has no provider keys. Its model SDKs point at
   `/agent-link/llm/<provider>/…` and authenticate with the agent token. The
   cloud adds the real key and forwards only generation endpoints. It relays only
   while one of that user's tasks is running.
6. **Progress.** Every second the agent pushes the task's steps, status and
   transcript. The cloud copies them onto its in-memory task, so the existing
   `/task/{id}/progress`, `/status` and `/reveal` endpoints serve the web UI
   unchanged. Pause sets a flag that the agent picks up on its next push.
7. **Finish.** The final push carries the full task state. The cloud saves the
   transcript to the database, so history and follow-up messages work.

## Configuration

| Where | Setting | Value |
|---|---|---|
| Cloud (Render) | `TASK_EXECUTION` | `agent` (already in `render.yaml`) |
| Cloud | `PUBLIC_API_URL` | your API URL, e.g. `https://xelora-api.onrender.com` |
| Cloud | `DATABASE_URL` | required (agent tokens live in `agent_tokens`) |
| Desktop | `xelora.webUrl` in `desktop/package.json` | your Vercel dashboard URL |

A single-PC install keeps the default `TASK_EXECUTION=server`. The backend then
runs tasks itself, and the desktop never pairs.

## Building the installer with the agent

`desktop/scripts/bundle-agent.ps1` (run by CI, or `npm run dist` on Windows)
creates `desktop/build/agent/`:

- `python/` is a relocatable CPython 3.12 (python-build-standalone, via `uv`)
  with `requirements-local.txt` installed. Torch/OmniParser are not included.
- `backend/` is the backend source without tests, scripts, runtime data or `.env`.

electron-builder ships it as `resources/agent`. The installed app runs
`resources\agent\python\python.exe -I resources\agent\backend\local_agent.py`.

## Running the agent by hand (development)

```powershell
cd backend
pip install -r requirements-local.txt
python local_agent.py --api-url https://xelora-api.onrender.com --token xa_...
```

Get a token from `POST /agent-link/pair` (signed in), or let Xelora Desktop pair
and use `npm start` in `desktop/`. In development it runs the repo's
`backend/local_agent.py` with `python` on PATH, or `XELORA_AGENT_PYTHON`.

Agent options such as `ENABLE_CUA_DRIVER` or `VISUAL_ONLY_MODE` come from
`resources\agent\backend\.env` in an installed app, or `backend/.env` in development.

## Logs and troubleshooting

| Symptom | Check |
|---|---|
| Badge says "not connected" | Signed in? Cloud has `TASK_EXECUTION=agent` and a database? |
| Badge says "restarting" | `%APPDATA%\Xelora\logs\agent.log` |
| Task stuck on "Waiting for Xelora Desktop" | Desktop app open on the PC with Excel; `GET /agent-link/status` shows `online` |
| "Model calls are relayed only while…" | The agent is calling outside a task; check the agent log |

## Limits (current version)

- **Queue is in memory.** A cloud restart drops tasks that no agent has claimed
  yet. Claimed tasks recover, because the agent's next push rebuilds the mirror.
  Free Render instances sleep when idle, but a connected agent keeps polling and
  keeps the instance awake.
- **One task at a time per PC**, the same rule as a local install.
- **Files uploaded in the web app stay in the cloud.** The agent works with the
  workbooks open on the PC, and cloud file tools are off for agent runs.
- **Learning/memory** (skill extraction, task history) is not recorded for agent runs yet.
- **Unpairing:** `DELETE /agent-link/tokens/{id}` revokes a token; the agent then
  exits and the desktop shows "not connected" until the user signs in again.
