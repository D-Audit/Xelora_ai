# Deploying Xelora (free tiers)

| Piece | Host | Free tier notes |
|---|---|---|
| PostgreSQL | **Neon** (or Supabase) | Free forever, small storage cap. Render's own free Postgres is deleted after 30 days, so don't use it. |
| Backend (`backend/`) | **Render** web service | 512 MB RAM. Sleeps after ~15 min idle; the first request after that takes ~1 min. Disk is wiped on every restart. |
| Web app (`frontend/`) | **Vercel** | Hobby plan. Vercel's terms limit Hobby to **non-commercial** use, so move to Pro before you charge customers. |
| Desktop installer (`desktop/`) | **GitHub Releases** | Built by `.github/workflows/build-desktop.yml`. Free for public repos. |

Free-tier limits change, so check each provider's pricing page before relying on them.

```
user browser / desktop app ──► Vercel (Next.js) ──server-side, X-API-Key──► Render (FastAPI) ──► Neon (Postgres)
```

---

## 1. Database: Neon

1. Sign up at neon.tech → **Create project** (pick the region closest to your Render region).
2. Copy the connection string, e.g.
   `postgresql://user:pass@ep-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`
3. That's your `DATABASE_URL`. The backend creates its tables on first start.

## 2. Backend: Render

1. Push this repo to GitHub.
2. render.com → **New → Blueprint** → select the repo. Render reads `render.yaml`
   (service `xelora-api`, root `backend/`, `pip install -r requirements.txt`,
   `uvicorn server:app --host 0.0.0.0 --port $PORT`).
3. Fill the variables it asks for:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | Neon string from step 1 |
   | `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` | whichever provider `AI_PROVIDER` uses |
   | `ALLOWED_ORIGINS` | your Vercel URL, e.g. `https://xelora.vercel.app` (fill after step 3) |
   | `FRONTEND_URL` | same Vercel URL |
   | `PUBLIC_API_URL` | this service's URL, e.g. `https://xelora-api.onrender.com` |

   `JWT_SECRET_KEY` and `LOCAL_API_KEY` are generated automatically. Open the
   service's **Environment** tab and copy `LOCAL_API_KEY`; Vercel needs it.
4. Deploy. When it's live, `https://xelora-api.onrender.com/` returns
   `{"status": "backend is running", ...}` and `/docs` shows the API docs.

Optional: Stripe (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_*`)
and OAuth (`GOOGLE_CLIENT_ID`, …). Without Stripe keys, billing runs in dev mode
and activates plans instantly without payment. See `backend/.env.example` for every variable.

**Uploaded files:** Render's disk (`STORAGE_DIR=/tmp/xelora-storage`) is wiped on
every restart and sleep, so `render.yaml` sets `FILE_STORAGE=database`: every upload
is also saved in Postgres and restored to disk on demand. Neon's free tier is small
(0.5 GB), so for many or large files use an S3-compatible bucket instead, e.g.
Cloudflare R2 (10 GB free):

| Variable | Value |
|---|---|
| `FILE_STORAGE` | `s3` |
| `S3_BUCKET` | your bucket name |
| `S3_ENDPOINT_URL` | `https://<account-id>.r2.cloudflarestorage.com` |
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | an R2 API token with read/write on that bucket |

Files uploaded before switching backends stay where they were saved; re-upload them
if they show "The stored copy of this file is missing".

**Memory:** learned skills, task history and chat memory are stored in Postgres
(`memory_records`) whenever `DATABASE_URL` is set, so they survive restarts too.
The desktop agent reads and writes the same memory through the API.

**Web search:** set `TAVILY_API_KEY` (free tier at tavily.com), or
`BRAVE_SEARCH_API_KEY` / `SERPER_API_KEY`. Without a key Xelora falls back to
DuckDuckGo, which usually blocks requests from cloud servers, so answers that need
current facts will say they could not search. Desktop agents use the server's key
through the API; the key never ships in the app.

## 3. Web app: Vercel

1. vercel.com → **Add New → Project** → import the repo.
2. **Root Directory: `frontend`**. Vercel detects Next.js.
3. Environment variables:

   | Variable | Value |
   |---|---|
   | `BACKEND_URL` | `https://xelora-api.onrender.com` |
   | `BACKEND_API_KEY` | the `LOCAL_API_KEY` from Render |
   | `XELORA_APP_URL` | this Vercel URL, e.g. `https://xelora.vercel.app` (needed for Google sign-in) |
   | `NEXT_PUBLIC_LEGAL_NAME` | your registered business name (shown in the Terms and Privacy Policy) |
   | `NEXT_PUBLIC_CONTACT_EMAIL` | the support address shown on the site |
   | `NEXT_PUBLIC_GOVERNING_LAW` | e.g. `the Republic of Rwanda` (Terms of Service) |
   | `NEXT_PUBLIC_LEGAL_ADDRESS` | optional business address for the legal pages |

4. Deploy. Then go back to Render and set `ALLOWED_ORIGINS` / `FRONTEND_URL` to
   the Vercel URL.
5. Register an account. To make yourself admin, follow
   `docs/reports/INTEGRATION.md` → "Making your first admin" (run the SQL in
   Neon's SQL editor).

### Sign in with Google

1. console.cloud.google.com → create a project → **APIs & Services → OAuth consent
   screen**: User type *External*, app name *Xelora*, your support email, the
   logo, and links to `/privacy` and `/terms`. Publish the app when ready.
2. **Credentials → Create credentials → OAuth client ID → Web application**.
   Authorised redirect URI: `https://<your-vercel-app>/api/auth/google/callback`
   (exactly; add `http://localhost:3000/api/auth/google/callback` for local use).
3. Put the client ID and secret on Render as `GOOGLE_CLIENT_ID` and
   `GOOGLE_CLIENT_SECRET`, and set `XELORA_APP_URL` on Vercel. Also set
   `GOOGLE_CLIENT_ID` (the ID only, never the secret) on Vercel so the
   Google screen opens without waiting for the backend to wake up.

In Xelora Desktop, the button opens the user's normal browser (Google blocks
sign-in inside app windows), and the session comes back to the app through a
`xelora://` link that the installer registers.

### Email (password reset and email confirmation)

Create a free account at resend.com, verify your domain, and set
`RESEND_API_KEY` and `EMAIL_FROM` (e.g. `Xelora <no-reply@yourdomain.com>`) on
Render, plus `FRONTEND_URL` = your Vercel URL so links point to the site.
Any SMTP server works instead (`SMTP_HOST`, `SMTP_USER`, ...). Until one is set,
"Forgot password" emails are only printed in the Render logs.

**Cold starts:** while Render is asleep, the first login can time out. Open the
backend URL once to wake it, or use a free uptime pinger (e.g. UptimeRobot,
every 10 min) to keep it awake.

## 4. Desktop app: GitHub Releases

1. In `desktop/package.json`, set `"xelora": { "webUrl": "https://<your-vercel-app>/dashboard" }`.
   Installed builds load this URL.
2. Bump `"version"` in `desktop/package.json` (the app reads it from there).
3. Commit, then tag and push:
   ```bash
   git tag v1.3.1
   git push origin main --tags
   ```
4. GitHub Actions bundles the local agent (`desktop/scripts/bundle-agent.ps1`),
   builds `Xelora Setup x.y.z.exe` on Windows and attaches it,
   with `latest.yml`, to the GitHub Release. Installed copies auto-update from new releases.
5. The web app's `/download` page links to the latest release asset
   (`frontend/src/lib/desktop-release.ts`, repo `D-Audit/Xelora_ai`). That works
   only if the repo is **public**. For a private repo, attach the installers
   to a separate public "releases" repo and change `GITHUB_REPO`.

Before real users install it:
- Add `desktop/assets/icon.ico` (256×256). Without it, the app uses Electron's default icon.
- The installer is unsigned, so Windows SmartScreen will warn ("Unknown publisher").
  Code signing (e.g. Azure Trusted Signing) removes this but is not free.

## 5. How Excel automation works when hosted

Render has no Excel, so `render.yaml` sets `TASK_EXECUTION=agent`: every task
runs on the user's own PC through the **Xelora Desktop local agent**, which is
bundled in the installer and needs no Python install.

1. The user installs Xelora Desktop and signs in. The app pairs itself with your
   API and shows **"Excel agent connected"** on the AI Agent page.
2. Tasks sent from the desktop window, or from any browser signed into the same
   account, run in the Excel on that PC. Progress streams back to the web UI.
3. Model calls go through your API (`/agent-link/llm/*`), so your Gemini/Claude
   keys never leave Render.

Set `PUBLIC_API_URL` on Render to the service's URL (step 2), so paired desktops
connect to the right address. Details, logs and limits: `docs/LOCAL_AGENT.md`.
