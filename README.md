# Xelora - Integrated Build

This package contains your **backend** (unmodified, plus an additive
auth/billing layer) and your **frontend** (wired to real endpoints
instead of mock data), ready to run together.

See `INTEGRATION.md` for exactly what was changed/added and why, and
what's honestly still mock. This file is just install + run.

```
xelora-integrated/
├── backend/          FastAPI agent + new auth/billing addon
├── frontend/          xelora/  (Next.js app)
├── README.md          (this file)
└── INTEGRATION.md      (what changed, what's still mock, security notes)
```

---

## 1. Prerequisites

- Python 3.11+
- Node.js 20+ and npm
- PostgreSQL (recommended) - the backend can technically run without a
  database, but accounts/billing/plan-enforcement need one; without it
  registration and login return a clear 503, not a crash.
- Windows + Excel, if you want the agent to actually control a real
  spreadsheet (the desktop-agent side of your existing backend). The
  web API itself (auth, billing, task orchestration) runs fine on any
  OS.

## 2. Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt -r requirements-auth.txt
```

Create your `.env` by combining the two example files:

```bash
cat .env.example .env.auth.example > .env
```

Then edit `.env` and fill in, at minimum:

| Variable | Notes |
|---|---|
| `DATABASE_URL` | e.g. `postgresql://user:pass@localhost:5432/xelora` |
| `LOCAL_API_KEY` | any long random string - shared secret between frontend and backend |
| `JWT_SECRET_KEY` | generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `GEMINI_API_KEY` or `ANTHROPIC_API_KEY` | whichever AI provider your `agent/providers.py` is configured to use |
| `STORAGE_DIR` | where uploaded files are saved (default `./storage`) |

Stripe variables (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
`STRIPE_PRICE_*`) can stay blank for now - billing runs in **dev
mode** (instant, fake activation, no real payment) until you fill
them in. See `INTEGRATION.md` → "Billing modes."

Run it:

```bash
uvicorn server:app --reload --port 8000
```

Note it's `server:app`, **not** `main:app` - `server.py` is the new
entrypoint that adds auth/billing/plan-enforcement on top of your
existing `main.py`. Running `uvicorn main:app` still works exactly as
it did before, just without any of that layer.

Visit `http://localhost:8000/` - you should see the existing health
check response, plus you can hit `http://localhost:8000/docs` for the
full interactive API (original agent routes + new `/auth` and
`/billing` routes together).

## 2A. OmniParser-only visual Excel mode

Xelora can operate Excel like a person: it focuses the visible Excel window,
uses Excel's native **Go To / Name Box** behavior to select a known range, and
then types, pastes, or uses a keyboard shortcut. OmniParser is used only when
Xelora must identify an unknown on-screen control such as a ribbon command or
dialog button.

This profile deliberately disables the Excel skill library, COM/API workbook
operations, and generated Python code. It still keeps the configured AI
provider as the task planner: OmniParser finds screen elements but cannot turn
a natural-language request into a sequence of actions by itself.

### What is used

| Request | Visual action | OmniParser call? |
| --- | --- | --- |
| “Go to `B12`” | Excel Go To / Name Box pathway (`Ctrl+G`) | No |
| “Write Total in `A1`” | Go To `A1`, then type into Excel | No |
| “Paste this table at `A1`” | Go To `A1`, then one atomic clipboard paste | No |
| “Fill this formula down” | Go To, type the formula, then Excel Fill Down | No |
| “Click the Sort button” or handle a dialog | Parse the narrow ribbon/popup area, then click the returned element centre | Yes |

Using the Name Box pathway for known ranges avoids an unnecessary full-screen
parse and is the fastest, most reliable way to write visible cell data.

### Install and start the parser

The parser runs as a **separate local process**. Keep it bound to `127.0.0.1`:
it receives screenshots and does not provide authentication itself.

1. Install [Miniconda or Anaconda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html), then clone the official [Microsoft OmniParser repository](https://github.com/microsoft/OmniParser).
2. In PowerShell, create its separate Python environment and install its dependencies:

```powershell
git clone https://github.com/microsoft/OmniParser.git
cd OmniParser
conda create -n omni python=3.12
conda activate omni
pip install -r requirements.txt
```

3. Download the OmniParser model weights by following the current **Install**
section of the official repository, then start its FastAPI parser server on a
port that is not Xelora's port 8000:

```powershell
cd omnitool\omniparserserver
python -m omniparserserver --host 127.0.0.1 --port 8001
```

4. In a second terminal, confirm the parser is ready:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/probe/
```

It should return an `Omniparser API ready` message. Then set these values in
`backend/.env`:

```env
OMNIPARSER_ONLY_MODE=true
OMNIPARSER_URL=http://127.0.0.1:8001/parse/
OMNIPARSER_TIMEOUT_SECONDS=60
```

The OmniParser-only profile automatically forces `VISUAL_ONLY_MODE=true`,
disables `ENABLE_CODEGEN_LAYER`, and hides every Excel skill from the planner.
Restart Xelora after changing `.env`:

```powershell
cd <your-xelora-folder>\backend
.\venv\Scripts\Activate.ps1
uvicorn server:app --reload --port 8000
```

If `OMNIPARSER_URL` is blank or points to the Xelora backend itself, Xelora
will refuse to start in this profile rather than silently falling back to
skills or generated code.

### Florence clarification and speed

Xelora does **not** run or call Florence directly. The standard upstream
OmniParser server, however, currently starts its Florence2 caption model for
unlabelled icon descriptions. It is not a separate Xelora feature that can be
disabled from `backend/.env`. Do not run an additional Florence service.

If a deployment must avoid Florence entirely, it needs a custom
OmniParser-compatible parser service that returns the same `parsed_content_list`
response using detector/OCR-only output. Xelora will work with that endpoint,
but it will have weaker descriptions for unlabelled icons. For the standard
server, the speed optimisation already in Xelora is to avoid parser calls for
known ranges, keyboard shortcuts, typing, table pastes, formulas, and simple
formatting; it parses only ambiguous visual controls.

## 3. Frontend setup

```bash
cd frontend/xelora
npm install
cp .env.local.example .env.local
```

Edit `.env.local`:

```
BACKEND_URL=http://localhost:8000
BACKEND_API_KEY=<same value as LOCAL_API_KEY in backend/.env>
```

Run it:

```bash
npm run dev
```

Visit `http://localhost:3000`. Register a new account - this now
creates a real row in your Postgres database (via `/auth/register`),
not a mock login. Log in with it on subsequent visits.

## 4. Try the real integration end-to-end

1. Register an account at `/register` → lands on `/onboarding` → `/dashboard`.
2. Go to **Billing → Compare plans**, pick "Starter". In dev mode
   (no Stripe keys) this activates instantly.
3. Go to the new **AI Agent** page in the sidebar, type an instruction,
   click "Run task". This calls your real `/task` endpoint through the
   plan-enforcement middleware - run it enough times to hit your
   plan's monthly workflow-run limit and you'll see the real 402
   upgrade prompt, not a UI-only gate.
4. Upgrade to "Professional" and confirm the limit resets/raises.
5. Try **Files** (upload a real spreadsheet), **Team** (invite an
   email), **Templates** (use one - it creates a real Workflow), and
   **Workflows** (build one, run it - it submits a real task).
6. To see the **Admin** pages, promote your account with the SQL
   command in `INTEGRATION.md` → "Making your first admin", then visit
   `/admin/users`.

## 5. Desktop app

`frontend/xelora-desktop/` is a native window wrapper around the exact
same web app - no separate logic, no separate backend calls. With the
backend and frontend both running (steps 2-3 above):

```bash
cd frontend/xelora-desktop
npm install
npm start
```

A window opens showing your real dashboard. See
`frontend/xelora-desktop/README.md` for pointing it at a deployed URL
and building a Windows installer.

Excel automation runs where the FastAPI backend runs. The wrapper can
control local Excel in the documented development setup because both
the desktop app and backend run on the same Windows PC. Pointing the
wrapper at a deployed web app changes only the UI location; it does not
turn a remote backend into a local Excel agent.

Two other desktop-related folders are included but were **not** wired
up - `frontend/xelora/apps/desktop/` and `frontend/desktop-runtime/`.
See `INTEGRATION.md` → "Desktop app" for why.

## 6. Production notes

- Set `ALLOW_NO_AUTH=false` and a real `LOCAL_API_KEY` before deploying
  - `main.py`'s existing security.py already enforces this; nothing
    new needed there.
- Fill in the Stripe env vars and point `STRIPE_WEBHOOK_SECRET` at a
  webhook endpoint registered for `https://yourdomain.com/billing/webhook`
  subscribed to `checkout.session.completed`, `customer.subscription.updated`,
  `customer.subscription.deleted`, `invoice.paid`.
- Serve the frontend and backend over HTTPS - the session cookie is
  marked `secure` automatically in production (`NODE_ENV=production`).
- Read `INTEGRATION.md`'s "Known gaps" section before calling this
  release-ready - a few frontend areas are still on mock data because
  the backend has no matching concept yet (see that section for the
  full, honest list).
