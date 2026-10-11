# Xelora

AI-powered spreadsheet automation: a FastAPI agent backend, a Next.js web app,
and an Electron desktop app.

```
Xelora_ai/
├── backend/                 FastAPI API + AI agent (entrypoint: server:app)
│   ├── agent/ skills/ vision/ tools/ …   agent packages
│   ├── tests/               pytest suite (fakes in tests/test_support/)
│   ├── scripts/             manual / Windows end-to-end scripts
│   ├── requirements.txt         core deps (any OS, cloud hosts)
│   ├── requirements-local.txt   + Windows desktop control (bundled in Xelora Desktop)
│   ├── requirements-omniparser.txt  + OmniParser local mode (torch, optional)
│   ├── agent_link.py        cloud side of the desktop local agent
│   ├── local_agent.py       desktop local agent (runs tasks next to Excel)
│   └── .env.example
├── frontend/                Next.js web app (website, dashboard, admin)
├── desktop/                 Electron app: web app window + local agent manager (Windows installer)
├── docs/                    architecture, deployment, testing, setup guides
│   ├── backend/             MCP, learning system, changelog
│   └── reports/             historical integration / review reports
├── .github/workflows/       desktop installer build on version tags
└── render.yaml              backend deploy blueprint (Render)
```

## Run locally

**Backend** (Python 3.11+):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt                     # Windows + Excel PC: requirements-local.txt
cp .env.example .env    # set JWT_SECRET_KEY, LOCAL_API_KEY, DATABASE_URL, an AI provider key
uvicorn server:app --reload --port 8000
```

Use `server:app`, not `main:app`. `server.py` adds auth, billing and plan
limits on top of `main.py`. API docs are at `http://localhost:8000/docs`.

**Frontend** (Node 20+):

```bash
cd frontend
npm install
cp .env.example .env.local   # BACKEND_URL=http://localhost:8000, BACKEND_API_KEY=<LOCAL_API_KEY>
npm run dev                  # http://localhost:3000
```

**Desktop** (with the two above running):

```bash
cd desktop
npm install
npm start
```

**Tests:**

```bash
cd backend && pip install -r requirements-dev.txt && python -m pytest -q
cd frontend && npx tsc --noEmit && npm run build
```

## Where Excel automation runs

| Setup | `TASK_EXECUTION` | Who touches Excel |
|---|---|---|
| Everything on one Windows PC | `server` (default) | the backend process |
| Hosted (Render + Vercel) | `agent` | each user's **Xelora Desktop local agent**, on their own PC |

In hosted mode the cloud queues each task for that user's desktop. The local
agent runs it against their Excel and streams progress back, and model calls are
relayed so API keys stay on the server. See `docs/LOCAL_AGENT.md`.

## Docs

| Doc | What it covers |
|---|---|
| `docs/DEPLOYMENT.md` | Free hosting: backend, database, web app, desktop installer |
| `docs/LOCAL_AGENT.md` | How hosted Xelora runs tasks in each user's Excel |
| `docs/ARCHITECTURE.md` | How requests flow; tool registry, permissions, audit |
| `docs/TESTING.md` | Test suite and the Windows acceptance procedure |
| `docs/WINDOWS_CUA_SETUP.md` | Desktop control (Cua Driver) on Windows |
| `docs/OMNIPARSER.md` | OmniParser-only visual Excel mode |
| `docs/SECURITY.md` | Security model |
| `docs/reports/INTEGRATION.md` | What is real vs. still mock, billing modes, first admin |

## Agent capabilities

Structured Excel skills are always tried first. Other capabilities go through
one governed boundary (tool registry → permission policy → audit log →
dispatch → verification).

| Capability | Default | Enable with |
|---|---|---|
| Web search / fetch (SSRF-guarded, 2 MB cap) | on | — |
| User files in `STORAGE_DIR/<user_id>` | on | — |
| Terminal (argv allowlist, no shell, read-only) | off | `ENABLE_TERMINAL_TOOLS=true`, `XELORA_TERMINAL_ROOT=<dir>` |
| Cua Driver desktop control | off | `ENABLE_CUA_DRIVER=true` |
| External MCP servers | off | `ENABLE_MCP_CLIENT=true`, `MCP_SERVERS_FILE=mcp_servers.json` |
| Scheduled workflow runs (≥5 min) | off | `ENABLE_AUTOMATIONS=true` (needs `DATABASE_URL`) |

The backend refuses to start if an enabled capability is misconfigured.
