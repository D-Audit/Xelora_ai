# Integration notes

## What "don't change the backend" meant in practice

Every file under `backend/` that existed in your original upload is
byte-for-byte unchanged: `main.py`, `models.py`, `security.py`,
`config.py`, `database.py`, `agent/`, `skills/`, `codegen/`,
`knowledge/`, `learning/`, `vision/`, `watchers/` - all untouched.

Everything new lives in six new files:

- `auth_billing_models.py` - new DB tables (`AuthUser`, `Subscription`,
  `UsageRecord`, `Invoice`), registered on the same SQLAlchemy `Base`
  your existing tables use.
- `plan_catalog.py` - plan pricing/limits, mirrored from the frontend's
  `mock-plans.ts` numbers.
- `auth.py` - register/login/me, bcrypt + JWT.
- `billing.py` - plans/subscription/invoices/checkout/cancel/webhook.
- `plan_guard.py` - the actual enforcement logic.
- `server.py` - the **new entrypoint**. It imports `main.py`'s `app`
  object and attaches the routers and a middleware to it from the
  outside. `main.py` has zero references to any of this and keeps
  working standalone (`uvicorn main:app`) exactly as before.

### Why AuthUser isn't just a password column bolted onto `models.User`

`Task.user_id` and `UserPreference.user_id` already have a real
foreign-key constraint pointing at `users.id`. Rather than fork a
second, disconnected user concept (which would break the moment a
web-registered user tried to submit an agent task), `AuthUser` is a
1:1 extension table: `AuthUser.id` **is** `models.User.id`, via its own
FK back to `users.id`. Registration creates both rows in one
transaction. Net effect: every web account is also a fully valid agent
user, and `models.py` never had to be edited.

### Why plan-limit enforcement is a middleware, not a route dependency

The idiomatic FastAPI way to protect a route is `Depends(...)` on that
route's signature - but that means editing `main.py`'s `/task` handler,
which was off-limits. Starlette/FastAPI middleware can inspect and
short-circuit any request before it reaches the handler, so
`server.py` registers one that:

1. Only touches `POST /task` - every other route passes through
   untouched, including the new `/auth` and `/billing` routes.
2. Requires a valid JWT (`Authorization: Bearer <token>`).
3. Looks up the caller's subscription and current-period usage.
4. Returns `402` with a clear message if the plan's monthly
   workflow-run quota is used up, or if the subscription isn't
   active/trialing.
5. Otherwise increments the usage counter and lets the request
   through to your original, unmodified `/task` handler.

This is real, server-side protection - it can't be bypassed from the
browser the way a UI-only "upgrade to continue" dialog could be.

## Billing modes

`billing.py` checks `STRIPE_SECRET_KEY` at import time:

- **Set** → `/billing/checkout` creates a real Stripe Checkout Session
  and returns its URL; the frontend redirects the browser to Stripe.
  The subscription only activates when Stripe calls
  `/billing/webhook` back (`checkout.session.completed`), which is the
  correct flow - never trust the client telling you payment succeeded.
- **Unset** → **dev mode**. `/billing/checkout` activates the plan in
  the database immediately, no payment involved. A log line prints
  every time this happens so it's never mistaken for production
  behavior. This is what lets you build/demo the whole flow without a
  Stripe account.

## Frontend changes

New files only add functionality; two files were fully rewritten
because they were pure mock implementations with no real logic to
preserve (`services/auth.ts`, `stores/auth-store.ts` gained one
async change). Everything else that changed is additive:

- `src/lib/backend.ts`, `src/lib/session.ts` - the security-relevant
  part. The backend's shared `LOCAL_API_KEY` is now only ever read
  server-side inside Next.js Route Handlers, never shipped to the
  browser. The user's session JWT lives in an **httpOnly** cookie, not
  `localStorage` - a real fix over the previous mock version, where a
  session token sitting in localStorage would have been readable by
  any injected script.
- `src/app/api/auth/*`, `src/app/api/billing/*`, `src/app/api/task/*` -
  Route Handlers that forward to the backend with the API key attached
  server-side.
- `src/services/agent.ts`, `src/services/billing.ts` - typed client
  wrappers around those routes.
- `src/services/auth.ts` - rewritten to call the real routes; same
  exported function signatures as before so `login`/`register` pages
  and `onboarding/page.tsx` needed no changes.
- `src/stores/auth-store.ts` - `initialize()` is now `async` (it awaits
  a real `/api/auth/me` call). Every call site was already inside a
  `useEffect`, so this required no other changes.
- `src/app/dashboard/billing/page.tsx`, `.../billing/plans/page.tsx`,
  `.../billing/invoices/page.tsx` - rewritten to fetch real
  subscription/plan/invoice data and perform real checkout/cancel
  actions, instead of reading `mock-billing.ts`/`mock-plans.ts`.
- `src/app/dashboard/agent/page.tsx` (new) + sidebar link - a page that
  didn't exist before, because nothing in your frontend called your
  backend's actual core feature (task submission, progress polling,
  pause/resume, reveal). This page is also the one place you can watch
  the plan-limit protection fire in the UI: run tasks until you hit
  your plan's monthly limit and you'll see the real 402 message with
  an upgrade link, not a client-side simulation.

## Desktop app

**Update:** the AI Agent page (chat-style prompt UI, running tasks) is
now **desktop-only by design**. The web dashboard no longer shows it
at all - the sidebar hides it, and the page itself shows a friendly
"desktop feature" message if someone reaches the URL directly on the
web. This is intentional, not a bug: `frontend/xelora-desktop/`'s
`preload.js` exposes `window.xeloraDesktop.isDesktopApp = true`, and
`src/lib/is-desktop.ts` checks for that flag to decide what to show.
The AI Agent page itself was also redesigned as a chat interface
(message bubbles, input pinned at the bottom) rather than the earlier
form-style layout.

Your original upload had three desktop-related locations. Here's what
happened to each:

- **`frontend/xelora-desktop/`** - a thin Electron `BrowserWindow`
  wrapper (`main.js`) that just loads a URL. It originally pointed at
  `/desktop`, a separate mock-only "workbench" page inside the Next.js
  app (chat-thread task UI, fake spreadsheet view, none of it backed
  by real endpoints). I changed the one line pointing it at
  `/dashboard` instead - the real, fully-integrated app this whole
  delivery wired up. Nothing else about this folder needed touching;
  it has no logic of its own, it's just a window. See
  `frontend/xelora-desktop/README.md` for running/building it.
- **`frontend/xelora/apps/desktop/`** - a completely separate,
  self-contained Electron + Vite + React application, with its own
  renderer, its own mock auth service (`src/renderer/lib/mock.ts`),
  its own file service, its own store. This is not a thin wrapper - it's
  a second, parallel implementation of a desktop product UI that
  happens to duplicate what the web app does. Wiring this up for real
  would mean redoing the entire integration a second time against a
  different codebase (its own auth calls, its own file calls, etc.),
  not "adding what's needed" on top of the work already done. It's
  included in the zip unmodified, in case you want to develop it
  separately, but nothing in it was touched or wired to the backend.
- **`frontend/desktop-runtime/`** - just a `package.json` scaffold
  (build scripts, dependencies) with no source files behind it at all
  in your original upload - not a working app in its current state,
  so there was nothing to wire up. Included unmodified.

**The practical takeaway:** if you want an installable desktop app
right now, use `frontend/xelora-desktop/` - it already shows your real
dashboard with everything working (auth, billing, files, workflows,
the AI Agent page). The other two are separate, unfinished
implementations that would each need their own dedicated integration
pass if you decide you want them instead of (or alongside) the
wrapper approach.

## What's now real (this round)

Every product area that used to read from `src/data/mock-*.ts` is now
backed by real endpoints, all additive to the backend exactly like the
auth/billing layer:

- **Files** (`files.py`) - real upload to local disk (`STORAGE_DIR`),
  bounded CSV/TSV/XLSX metadata extraction, safe sample previews, and
  immutable version history. Files can be reprocessed, a specific version
  can be downloaded, and the final remaining version cannot be removed.
  Swap for S3/GCS later without touching the frontend - it only ever talks
  to `/files`, never a disk path.
- **Team** (`team.py`) - single-owner-team model. Invite by email,
  role, remove. Seat count is enforced against the plan's
  `team_members` limit from `plan_catalog.py`. If an invitee later
  registers with the invited email, they're auto-linked the next time
  the list loads.
- **Devices** (`devices.py`) - list/revoke devices authorised under an
  account. Nothing auto-registers a device yet (the web app isn't a
  "device" in the agent sense) - a real desktop build would call
  `POST /devices` on first run. The page is honestly empty until that
  happens; see the note on the page itself.
- **Notifications** (`notifications.py` + `notify.py`) - list, mark
  read, mark all read. Real notifications are now created on
  registration (welcome), plan changes (checkout), and hitting a plan
  limit (with a link straight to the upgrade page) - not a static mock
  list.
- **Workflows** (`workflows.py`) - full CRUD for named, multi-step,
  reusable workflows (what the frontend's builder UI expects). This is
  the one place a genuine design decision was made: the backend's
  agent only understands one natural-language instruction per task, so
  running a workflow joins its enabled steps into one instruction and
  submits it to the real `/task` endpoint via an internal HTTP call
  (not a duplicated copy of the agent's orchestration code) - meaning
  it goes through the exact same plan-limit middleware a direct
  `/task` call would. `WorkflowRun` rows link to the resulting task id
  and sync their status by reading that task's live progress.
- **Templates** (seeded by `seed_templates.py`, served from
  `workflows.py`) - a few starter templates ship out of the box;
  "use template" clones one into a new Workflow for the account.
- **Admin** (`admin.py`) - gated by `AuthUser.is_admin` (see "Making
  your first admin" below). Real user list with live plan overrides,
  real subscription inventory, and a stats endpoint. `admin/system`,
  `admin/releases`, and `admin/usage` (platform-wide usage charts,
  infra diagnostics, release notes) are intentionally left on mock
  data - they're operational/marketing content, not product data tied
  to a user's account, and wiring them means picking a metrics/logging
  stack rather than "adding what's needed" for the product itself.

## Making your first admin

No endpoint can safely make the *first* admin (anyone could call it).
After registering your own account, promote it directly in the
database:

```sql
UPDATE auth_users SET is_admin = true WHERE id = (SELECT id FROM users WHERE email = 'you@example.com');
```

From then on, that admin can promote others via
`POST /admin/users/{id}/role`.

## Known gaps - read this before calling it "fully integrated"

Being direct about what's still intentionally out of scope:

- **`admin/system`, `admin/releases`, `admin/usage`** - see above;
  still mock, deliberately (infra/marketing content, not user data).
- **Onboarding answers** (primary use, experience level, objectives)
  are kept in local UI state only; `AuthUser` doesn't have columns for
  them yet. Easy follow-up: add the columns to
  `auth_billing_models.py` and a small `PATCH /auth/me` endpoint.
- **Invoice PDF download** - the invoices table is populated from
  Stripe webhook data, but downloading an actual PDF needs Stripe's
  Customer Portal or the Invoice PDF API, not wired up here.

## Quick sanity checklist after you pull this down

- [ ] `uvicorn server:app --reload` starts with no import errors
- [ ] `POST /auth/register` (via `/docs`) returns a token
- [ ] Frontend register page creates that same account
- [ ] `/dashboard/billing/plans` shows real plans and completes a dev-mode checkout
- [ ] `/dashboard/agent` starts a task and shows live progress
- [ ] Running tasks past your plan's limit returns the 402 upgrade prompt
- [ ] `/dashboard/files` uploads and lists a real file
- [ ] Open a file from `/dashboard/files`, wait for its metadata/preview,
  upload a second version, and download either version
- [ ] `/dashboard/team` sends a real invite
- [ ] `/dashboard/workflows/new` saves, and running it starts a real task
- [ ] `/dashboard/templates` "use template" creates a workflow
- [ ] After promoting yourself to admin, `/admin/users` loads and a plan override sticks

## File uploads and versioning

If you hit an upload error before this update, two real issues were
fixed:

1. `STORAGE_DIR` now defaults to a folder next to the backend code
   itself, not "wherever you happened to run `uvicorn` from" - a
   relative `./storage` path could silently end up in the wrong place
   depending on your terminal's current directory. If your existing
   `.env` still has `STORAGE_DIR=./storage` from an earlier version of
   this package, either delete that line (so the safer default takes
   over) or replace it with a full absolute path.
2. Disk-write and database-save failures during upload now return a
   clear error message instead of crashing with a raw Python
   traceback.

Files are streamed to a private per-user folder, checked against their
declared spreadsheet structure, and recorded with a SHA-256 checksum. The
response initially reports `processing`; a FastAPI background task then
extracts metadata for CSV, TSV, and XLSX files and changes it to
`completed`, `needs_review`, or `failed`. XLS and ODS are safely stored and
versioned but intentionally report `needs_review` because this package does
not bundle a parser for them.

Set these optional limits in `backend/.env` to tune local deployments:

| Variable | Default | Purpose |
| --- | ---: | --- |
| `MAX_UPLOAD_MB` | 100 | Maximum compressed upload size. |
| `MAX_ARCHIVE_UNCOMPRESSED_MB` | 300 | Rejects highly-compressed XLSX/ODS archives that expand beyond this size. |
| `MAX_FILE_PARSE_ROWS` | 100000 | Maximum rows inspected per sheet/file. |
| `MAX_FILE_PARSE_COLUMNS` | 500 | Maximum columns retained for metadata and preview. |
| `MAX_FILE_PREVIEW_ROWS` | 20 | Number of non-header rows included in the authenticated preview. |

If uploads still fail for you, the exact error message (from the
browser toast, or the backend terminal) is needed to diagnose further
- "it doesn't work" isn't enough to go on without reproducing your
exact environment.

## Google / Microsoft sign-in

Now implemented for real - standard OAuth 2.0 authorization-code flow,
client secrets held only by the backend (`oauth.py`), never exposed to
the browser. New file: `frontend/xelora/src/lib/session.ts` gained
CSRF-protection helpers used by the new
`frontend/xelora/src/app/api/auth/{google,microsoft}/{start,callback}/route.ts`
routes.

**How it works:** clicking "Continue with Google" sends the browser to
`/api/auth/google/start`, which redirects to Google's consent screen;
Google redirects back to `/api/auth/google/callback`, which verifies a
CSRF token, exchanges the code with Google via the backend, and signs
the user in - creating a new account automatically if the email isn't
already registered (linked by email, since Google/Microsoft have
already verified that email belongs to the person signing in).

### Getting your Google credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/) →
   create or select a project.
2. **APIs & Services → OAuth consent screen** - fill in the basics
   (app name, support email). "External" user type is fine for
   testing.
3. **APIs & Services → Credentials → Create Credentials → OAuth
   client ID** → Application type: **Web application**.
4. Under **Authorized redirect URIs**, add:
   ```
   http://localhost:3000/api/auth/google/callback
   ```
   (add your production URL too once you deploy, e.g.
   `https://app.yourdomain.com/api/auth/google/callback`)
5. Copy the **Client ID** and **Client secret** it gives you.

### Getting your Microsoft credentials

1. Go to [Azure Portal](https://portal.azure.com/) → **App
   registrations** → **New registration**.
2. Name it anything; under **Supported account types**, choose
   "Accounts in any organizational directory and personal Microsoft
   accounts" (matches `MICROSOFT_TENANT=common` below) unless you want
   to restrict sign-in to one organization.
3. Under **Redirect URI**, platform: **Web**, add:
   ```
   http://localhost:3000/api/auth/microsoft/callback
   ```
4. After registration, copy the **Application (client) ID** from the
   Overview page.
5. Go to **Certificates & secrets → New client secret**, create one,
   and copy its **Value** immediately - Azure only shows it once.

### Where the keys go

All four values go in `backend/.env` only (never the frontend):

```
GOOGLE_CLIENT_ID=<your Google client ID>
GOOGLE_CLIENT_SECRET=<your Google client secret>
MICROSOFT_CLIENT_ID=<your Microsoft application (client) ID>
MICROSOFT_CLIENT_SECRET=<your Microsoft client secret value>
MICROSOFT_TENANT=common
```

Restart the backend after adding these. Leaving any provider's keys
blank simply disables that one button gracefully (clicking it shows
"sign-in is not available right now" instead of erroring the whole
app) - you don't need both providers configured to use either one.

### A note on trust

OAuth-created accounts are linked to an existing account by email
automatically. This is safe specifically because Google/Microsoft
have already verified the person owns that email address before
redirecting back to you - it is not the same as blindly trusting an
email address a user typed into a form.
