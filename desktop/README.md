# Xelora Desktop (Electron wrapper)

This is a thin native window around your real Xelora web app - the
exact same integrated app from `frontend/` (real auth, billing,
files, workflows, the AI Agent page) with zero separate logic. There
is no duplicate UI or mock data here; this window just loads a URL.

## How it works

`main.js` opens an Electron `BrowserWindow` and loads
`http://localhost:3000/dashboard` by default - your Next.js dev
server, running the fully-wired dashboard.

## Running it in development

1. Start the backend (`uvicorn server:app --reload` in `backend/`).
2. Start the frontend (`npm run dev` in `frontend/`) - leave it
   running at `http://localhost:3000`.
3. In this folder:
   ```bash
   npm install
   npm start
   ```
   A native window opens showing your real dashboard - log in with a
   real account exactly as you would in a browser.

## Pointing it at a deployed app

Once your frontend is deployed somewhere real (Vercel, your own
server, etc.), you can point the desktop app at it instead of localhost
for the dashboard UI:

```bash
# macOS/Linux
XELORA_WEB_URL=https://app.yourdomain.com/dashboard npm start

# Windows PowerShell
$env:XELORA_WEB_URL="https://app.yourdomain.com/dashboard"; npm start
```

## Building an installer

```bash
npm run dist
```

On Windows with [uv](https://docs.astral.sh/uv/) installed, this first runs
`scripts/bundle-agent.ps1` (Python runtime + backend into `build/agent/`), then
`electron-builder` produces the installer under `release/`. Before building for real users, set
`xelora.webUrl` in `package.json` to your deployed dashboard URL - installed
builds load that URL, while `npm start` loads `http://localhost:3000/dashboard`.
`XELORA_WEB_URL` still overrides both.

Releases are built by `.github/workflows/build-desktop.yml` whenever a
`v*.*.*` tag is pushed; the installer is attached to the GitHub Release and
installed copies auto-update from there.

## What this is NOT

This is not a separate product with its own backend integration - the
authentication, billing, plan limits, files, and workflows you see in
this window are the identical ones from the web app, running through
the identical Next.js API routes and FastAPI backend.

It also runs the **local agent** (`agent.js`), which executes the user's
tasks in Excel on this PC when the backend is hosted (`TASK_EXECUTION=agent`).
Pairing is automatic after sign-in. See `docs/LOCAL_AGENT.md`.
