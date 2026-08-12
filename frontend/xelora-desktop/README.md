# Xelora Desktop (Electron wrapper)

This is a thin native window around your real Xelora web app - the
exact same integrated app from `frontend/xelora` (real auth, billing,
files, workflows, the AI Agent page) with zero separate logic. There
is no duplicate UI or mock data here; this window just loads a URL.

## How it works

`main.js` opens an Electron `BrowserWindow` and loads
`http://localhost:3000/dashboard` by default - your Next.js dev
server, running the fully-wired dashboard.

## Running it in development

1. Start the backend (`uvicorn server:app --reload` in `backend/`).
2. Start the frontend (`npm run dev` in `frontend/xelora/`) - leave it
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
server, etc.), point the desktop app at it instead of localhost:

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

This uses `electron-builder` (already configured in `package.json`)
to produce a Windows installer under `release/`. Two things to fix
before shipping this to real users:

1. **Hardcode `XELORA_WEB_URL` for production**, or read it from a
   config file - environment variables aren't a great way to
   configure an installed desktop app for end users. The simplest fix
   is changing the default in `main.js` directly to your production
   URL before running `npm run dist`.
2. **Add a real `assets/icon.ico`** - the build config references one
   but it isn't included in this package; `electron-builder` will
   fail without it. Any 256×256 `.ico` file works for testing.

## What this is NOT

This is not a separate product with its own backend integration - the
authentication, billing, plan limits, files, and workflows you see in
this window are the identical ones from the web app, running through
the identical Next.js API routes and FastAPI backend. There's nothing
extra to wire up here; if a feature works in the browser, it works in
this window.

See the root `INTEGRATION.md` for the other desktop-related folders
that were **not** wired up as part of this integration
(`frontend/xelora/apps/desktop/` and `frontend/desktop-runtime/`) and
why.
