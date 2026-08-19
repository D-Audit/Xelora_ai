# Xelora

Xelora is an AI-assisted Excel automation platform. A user describes a spreadsheet task in plain language, reviews the proposed plan, and confirms it before Xelora changes the workbook. The project combines a Windows Excel agent with a web dashboard for accounts, files, reusable workflows, teams, usage limits, and billing.

> [!IMPORTANT]
> Xelora is under active development. The core agent and most dashboard APIs are implemented, but several screens and production concerns remain unfinished. See [Current project status](#current-project-status) before treating the project as release-ready.

## Why Xelora exists

Spreadsheet work often involves more than generating one formula. Users need to clean data, combine sheets, build charts and pivots, import external information, apply consistent formatting, and repeat the same process later. Xelora aims to turn those multi-step jobs into reviewable, reusable workflows while preserving the native Excel workbook.

Example requests:

- "Clean this sales workbook, remove duplicate orders, and highlight late payments."
- "Combine the monthly sheets and create a regional revenue pivot table."
- "Import this PDF table, add variance formulas, and format an executive summary."
- "Repeat my weekly reporting workflow and use my preferred chart style."

## Core capabilities

- **Natural-language task planning:** the agent converts an instruction into a plan and waits for explicit approval before making changes.
- **Native Excel automation:** 69 registered skills cover workbook inspection, formulas, formatting, charts, pivots, filters, validation, VBA, Power Query, imports, and exports.
- **Three execution layers:** Xelora prefers tested skills, can generate allow-listed Excel code in a separate process for unsupported operations, and can optionally use screen vision as a last resort.
- **Verification and recovery:** actions record verification results; timed-out Excel operations trigger recovery, and unresolved failures are surfaced instead of being reported as success.
- **Reusable workflows:** users can build, save, run, and monitor multi-step workflows or start from seeded templates.
- **Context and memory:** document ingestion and a local TF-IDF knowledge base can ground tasks, while user preferences can influence future plans.
- **SaaS workspace:** authentication, OAuth, files, teams, devices, notifications, plans, usage enforcement, billing, and administration are exposed through the web dashboard.
- **Task visibility:** running tasks can be paused, resumed with a correction, and inspected through progress and reveal endpoints.
- **Live observer mode:** Excel changes occur in the open workbook while the desktop panel reports the active native Excel operation and completed, verified actions with sub-second updates. Floating mode keeps the controls visible beside Excel.

## How it works

```text
Browser / Electron shell
          |
          v
Next.js 16 dashboard and server-side API routes
          |
          | JWT + server-held API key
          v
FastAPI integrated service (server.py)
   |          |             |
   |          |             +-- Accounts, billing, files, teams, workflows
   |          +-- Task history, preferences, knowledge base
   v
Agent: plan -> approval -> execute -> verify -> correct
   |                 |                    |
   v                 v                    v
Skill library   Generated code    Optional visual fallback
   |                 |                    |
   +-----------------+--------------------+
                     |
                     v
              Microsoft Excel on Windows
```

The integrated backend entry point is `backend/server.py`. It extends the agent API in `backend/main.py` with authentication, billing, workspace routes, and plan-limit middleware.

## Technology stack

| Area | Main technologies |
| --- | --- |
| Web application | Next.js 16, React 19, TypeScript, Tailwind CSS, Zustand, Radix UI |
| Desktop | Electron; Windows is required for real Excel control |
| API | Python, FastAPI, Uvicorn, Pydantic |
| Data | PostgreSQL, SQLAlchemy; local filesystem storage during development |
| AI providers | Google Gemini or Anthropic Claude |
| Excel control | xlwings, openpyxl, optional PyAutoGUI/pywinauto/OmniParser fallback |
| Document intelligence | pdfplumber, Tesseract OCR, python-docx, scikit-learn |
| Payments and identity | Stripe, JWT, Google OAuth, Microsoft OAuth |

## Repository layout

```text
Xelora_ai/
|-- backend/                       FastAPI API and Excel agent
|   |-- agent/                     Planning, provider, and execution loop
|   |-- skills/library/            Excel skill implementations
|   |-- codegen/                   Generated-code execution layer
|   |-- vision/                    Optional UI vision and control
|   |-- knowledge/ and ingestion/  Document grounding and retrieval
|   |-- learning/                  Preferences and pattern mining
|   |-- main.py                    Standalone agent API
|   `-- server.py                  Full integrated API (recommended)
|-- frontend/xelora/               Next.js web application
|   `-- apps/desktop/              Separate Electron/Vite prototype (still mock-backed)
|-- frontend/xelora-desktop/       Thin Electron wrapper around the real web app
|-- INTEGRATION.md                 Detailed integration history and known gaps
`-- CODE_REVIEW_REPORT.md          Earlier technical review
```

## Getting started

### Prerequisites

- Windows 10 or 11 with desktop Microsoft Excel for live workbook automation
- Python 3.11 or newer
- Node.js 20 or newer and npm
- PostgreSQL for accounts, billing, history, workflows, and memory
- A Gemini or Anthropic API key

The API can run on another operating system, and workbook files can be handled with `openpyxl`, but live Excel control and the visual fallback depend on Windows and a visible desktop session.

### 1. Configure and run the backend

From PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-auth.txt
```

Create `backend/.env` (the repository currently does not include an example file):

```dotenv
# Required for the integrated application
DATABASE_URL=postgresql://postgres:password@localhost:5432/xelora
LOCAL_API_KEY=replace-with-a-long-random-secret
JWT_SECRET_KEY=replace-with-another-long-random-secret
AI_PROVIDER=gemini
GEMINI_API_KEY=your-key
# ANTHROPIC_API_KEY=your-key

# Local development
ALLOW_NO_AUTH=false
ALLOWED_ORIGINS=http://localhost:3000
FRONTEND_URL=http://localhost:3000
INTERNAL_BASE_URL=http://localhost:8000
STORAGE_DIR=D:/path/to/xelora-storage

# Optional agent layers
ENABLE_CODEGEN_LAYER=true
ENABLE_VISUAL_FALLBACK=false
VISUAL_ONLY_MODE=false
OMNIPARSER_URL=http://127.0.0.1:8000/parse/

# Optional OAuth
# GOOGLE_CLIENT_ID=
# GOOGLE_CLIENT_SECRET=
# MICROSOFT_CLIENT_ID=
# MICROSOFT_CLIENT_SECRET=
# MICROSOFT_TENANT=common

# Optional Stripe production billing
# STRIPE_SECRET_KEY=
# STRIPE_WEBHOOK_SECRET=
# STRIPE_PRICE_STARTER_MONTHLY=
# STRIPE_PRICE_STARTER_ANNUAL=
# STRIPE_PRICE_PROFESSIONAL_MONTHLY=
# STRIPE_PRICE_PROFESSIONAL_ANNUAL=
```

Generate secrets with `python -c "import secrets; print(secrets.token_hex(32))"`. Use a separate generated value for each secret.

Start the complete API:

```powershell
uvicorn server:app --reload --port 8000
```

Open `http://localhost:8000/docs` for interactive API documentation. `uvicorn main:app` starts only the agent API and omits the integrated authentication, workspace, billing, and plan-enforcement layer.

### 2. Configure and run the web application

In a second PowerShell window:

```powershell
cd frontend\xelora
npm install
```

Create `frontend/xelora/.env.local`:

```dotenv
BACKEND_URL=http://localhost:8000
BACKEND_API_KEY=the-same-value-as-LOCAL_API_KEY
XELORA_APP_URL=http://localhost:3000
```

Then run:

```powershell
npm run dev
```

Open `http://localhost:3000`, register an account, complete onboarding, and sign in.

### 3. Run a desktop client

There are currently two desktop approaches:

1. `frontend/xelora-desktop` is a thin wrapper around the integrated Next.js application. Use this when testing the existing SaaS dashboard in an Electron window.
2. `frontend/xelora/apps/desktop` is a richer standalone Electron/Vite prototype, but its renderer still uses mock authentication and AI responses. It should not yet be presented as the integrated product.

To run the integrated wrapper after starting the backend and web application:

```powershell
cd frontend\xelora-desktop
npm install
npm start
```

See [`frontend/xelora-desktop/README.md`](frontend/xelora-desktop/README.md) for packaging notes.

## Suggested end-to-end check

1. Register a user and sign in.
2. Select a plan. If Stripe is not configured, checkout uses an explicitly logged development mode and activates the plan without payment.
3. Upload an `.xlsx` file from **Files**.
4. In the desktop-only agent view, submit a task and review its proposed plan.
5. Confirm the plan, then watch its progress and inspect the workbook after completion.
6. Create a reusable workflow or clone a seeded template and run it.
7. Verify that history, notifications, and usage reflect the run.

## Current project status

| Area | Status | Notes |
| --- | --- | --- |
| Agent loop and Excel skills | Implemented, needs broader testing | Planning, approval, execution, verification, retry, and recovery exist. Real Excel behavior varies by workbook and Excel version. |
| Integrated API | Implemented | `server.py` composes agent, auth, billing, files, teams, devices, notifications, workflows, and admin routes. |
| Web authentication | Implemented | Password login and Google/Microsoft OAuth paths exist; provider credentials are required. |
| Billing | Development and Stripe modes implemented | Stripe webhook configuration and production validation are still operator responsibilities. |
| Files and workflows | Partially complete | Upload/list/download and workflow CRUD/run exist; file parsing status and per-file version history are not fully wired. |
| Web dashboard | Mixed | Core account and workspace areas use APIs; admin system, releases, usage, and some detail views still use mock content. |
| Thin Electron wrapper | Integrated | Displays the deployed or local web application. |
| Standalone Electron/Vite app | Prototype | Polished UI exists, but authentication and AI behavior are mock-backed. |
| Automated quality coverage | Early | A small learning test and desktop test command exist; the repository lacks comprehensive agent, API, integration, and end-to-end coverage. |
| Deployment | Not production-ready | No complete container/orchestration setup, managed object storage, observability stack, or documented migration pipeline is included. |

For a more granular inventory, read [`INTEGRATION.md`](INTEGRATION.md).

## Competitive landscape

Xelora enters a crowded category that ranges from native Excel copilots to AI-first spreadsheet replacements. The comparison below is directional and based on each product's public documentation as of August 2026; it is not a claim of feature parity.

| Product | Public positioning | Competitive pressure on Xelora | Potential Xelora angle |
| --- | --- | --- | --- |
| [Microsoft Copilot in Excel](https://support.microsoft.com/en-us/office/edit-with-copilot-in-excel-a2fd6fe4-97ac-416b-b89a-22f4d1357c7a) | Builds and edits native workbooks with formulas, charts, PivotTables, and multi-step plans inside Excel. | It has first-party Excel integration, Microsoft distribution, enterprise trust, and a very similar natural-language editing experience. | Provider choice, extensible skills, explicit execution logs, reusable cross-workbook workflows, and deployable/self-managed components could differentiate Xelora. |
| [Rows AI](https://rows.com/ai) | An AI-first collaborative spreadsheet with connectors, analysis, transformations, charts, and automation. | Stronger cloud collaboration, connectors, scheduled refresh, mobile access, and an integrated spreadsheet surface. | Xelora can focus on automating existing native Excel workbooks rather than asking users to migrate to a new spreadsheet product. |
| [Formula Bot](https://www.formulabot.com/product) | Natural-language analysis across spreadsheets, PDFs, and databases, plus dashboards, scheduled reports, and data enrichment. | Broad data-source support and polished analysis/reporting workflows compete with Xelora's ingestion and reusable workflows. | Xelora's live workbook modification, approval gate, skill/code/vision execution stack, and detailed action verification are a distinct automation story. |
| [Bricks](https://www.thebricks.com/ai-spreadsheet) | An AI spreadsheet centered on fast dashboards, reports, charts, cleaning, and collaborative presentation. | Stronger report design, dashboard creation, sharing, and browser-first collaboration. | Xelora can specialize in operational Excel automation, workbook fidelity, VBA/Power Query tasks, and repeatable desktop workflows. |

The largest strategic competitor is Microsoft itself. Xelora should avoid positioning as simply "Copilot, but separate." A defensible direction would emphasize auditable automation, user-controlled model/provider choice, organization-specific skills and knowledge, reusable workflow operations, and support for legacy or complex Excel environments.

## Development constraints and challenges

### Reliability and safety

- **LLM output is nondeterministic.** A fluent plan can still choose the wrong range, formula, or transformation. Every mutating skill needs deterministic validation, clear failure states, and regression fixtures.
- **Spreadsheet state is fragile.** Active sheet, selection, hidden/protected sheets, merged cells, external links, macros, calculation mode, locale, and version-specific features can change an operation's result.
- **Generated code increases risk.** The code-generation layer expands coverage but also creates a security and data-loss boundary. Isolation, allow-listing, resource limits, backups, and audit logs need further hardening.
- **Vision is inherently brittle.** DPI scaling, window position, themes, dialogs, latency, and UI updates can invalidate screen coordinates. It should remain a monitored fallback, not the default execution path.
- **User approval is not enough by itself.** Plans should show affected files, sheets, ranges, destructive actions, and expected outputs, with backup and rollback support before production use.

### Platform and architecture

- **Windows and Excel are hard dependencies** for full live automation. Headless cloud workers cannot directly reproduce a user's interactive Excel session without dedicated Windows hosts or virtual desktops.
- **Desktop architecture is duplicated.** Maintaining both a thin web wrapper and a separate Electron/Vite product will split engineering effort until one becomes canonical.
- **In-memory task state limits scaling.** Live tasks are held in process and background work uses daemon threads. Multiple API replicas, restarts, cancellation, and durable retries require a real job queue and shared state.
- **Local file storage does not scale horizontally.** Production needs object storage, malware scanning, retention rules, signed downloads, quotas, and lifecycle cleanup.
- **Database lifecycle is incomplete.** SQLAlchemy models exist, but production requires versioned migrations, backup/restore procedures, connection management, and tested upgrades.

### Security, privacy, and compliance

- Workbooks may contain payroll, financial, customer, health, or proprietary data. Encryption, tenant isolation, data residency, deletion, retention, access logs, and vendor data-processing terms must be designed explicitly.
- API keys, OAuth secrets, JWT signing keys, and Stripe webhooks require managed secret storage and rotation—not developer `.env` files—in production.
- VBA, external data connections, generated code, file uploads, OCR, and desktop UI control each introduce separate injection or arbitrary-execution risks.
- Enterprise adoption may require SSO/SAML, role-based authorization beyond the current model, administrator policies, SOC 2 evidence, and GDPR/POPIA controls.

### Product and operations

- AI and vision calls introduce variable latency and cost; usage limits must reflect actual provider and infrastructure costs.
- Provider models and SDKs change frequently. Model names, tool schemas, rate limits, and deprecations need compatibility tests and controlled upgrades.
- Users will judge Xelora by workbook correctness, not chat quality. A benchmark suite of representative, difficult workbooks is more valuable than prompt-only tests.
- Support will need reproducible action traces that avoid leaking workbook contents while still explaining what failed.
- Competitors already cover basic formula generation and charts. Product focus and a specific initial customer segment are necessary to avoid an overly broad roadmap.

## Recommended development priorities

1. Choose one canonical desktop architecture and connect it end to end.
2. Build workbook backups, dry-run previews, affected-range summaries, and rollback.
3. Add a durable queue and persistent task state before running more than one backend instance.
4. Create automated skill tests against a versioned corpus of Excel fixtures and supported Excel versions.
5. Replace remaining mock screens and add file processing/version-history APIs.
6. Add Alembic migrations, object storage, structured logs, metrics, error reporting, and production deployment documentation.
7. Threat-model generated code, uploads, VBA, OAuth, tenant access, and provider data flows.
8. Define the initial market wedge—for example, auditable recurring Excel operations for finance teams—and measure task success on that workflow set.

## Production checklist

- Set `ALLOW_NO_AUTH=false` and use unique, rotated secrets.
- Serve the web application and API over HTTPS.
- Restrict `ALLOWED_ORIGINS` to deployed application origins.
- Configure PostgreSQL backups and schema migrations.
- Replace local file storage with protected object storage.
- Configure Stripe webhook signature verification and real price IDs.
- Configure OAuth redirect URLs for the deployed domain.
- Sign the Windows installer and establish an update channel.
- Add centralized logs, metrics, alerts, and privacy-safe task tracing.
- Run security, recovery, tenancy, load, and workbook regression tests.

## Additional documentation

- [`INTEGRATION.md`](INTEGRATION.md) — integration decisions, real versus mock features, and detailed gaps
- [`backend/SECURITY.md`](backend/SECURITY.md) — backend security notes
- [`backend/LEARNING_SYSTEM.md`](backend/LEARNING_SYSTEM.md) — preference memory and pattern learning
- [`backend/MCP_SETUP.md`](backend/MCP_SETUP.md) — MCP server setup
- [`frontend/xelora-desktop/README.md`](frontend/xelora-desktop/README.md) — thin desktop wrapper

## License

No license file is currently included. Until a license is added, the project should be treated as all rights reserved rather than assumed to be open source.
