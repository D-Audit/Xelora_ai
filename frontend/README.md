# Xelora Web — Frontend

**Automate spreadsheets. Stay in control.**

Xelora is an AI-powered spreadsheet automation platform. This repository contains the complete SaaS web frontend plus a simulated Xelora Desktop interface built with Next.js, React, TypeScript, and Tailwind CSS.

---

## Quick start

```bash
# 1. Install dependencies
npm install

# 2. Copy the environment example
cp .env.example .env.local

# 3. Start the development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Demo credentials

| Role  | Email                   | Password   | Redirects to          |
|-------|-------------------------|------------|-----------------------|
| User  | `liliane@xelora.app`    | `Demo123!` | `/dashboard`          |
| Admin | `admin@xelora.app`      | `Admin123!`| `/admin`              |

All authentication is simulated using localStorage. No real backend is required.

---

## Build for production

```bash
npm run build
npm start
```

TypeScript strict-mode is enabled. The build must complete with zero errors before any PR is merged.

---

## Main routes

### Public marketing
| Route           | Description                              |
|-----------------|------------------------------------------|
| `/`             | Landing page with all sections           |
| `/features`     | Full feature detail page                 |
| `/how-it-works` | Step-by-step journey                     |
| `/solutions`    | Use-case solutions by industry           |
| `/pricing`      | Pricing tiers with feature comparison    |
| `/security`     | Privacy and security information         |
| `/download`     | Desktop app download page                |
| `/resources`    | Help, tutorials, templates overview      |

### Authentication
| Route               | Description             |
|---------------------|-------------------------|
| `/login`            | Sign in                 |
| `/register`         | Create account          |
| `/forgot-password`  | Request reset link      |
| `/reset-password`   | Set new password        |
| `/verify-email`     | Email verification      |

### Onboarding
| Route         | Description                    |
|---------------|--------------------------------|
| `/onboarding` | 7-step onboarding wizard       |

### User dashboard
| Route                             | Description                    |
|-----------------------------------|--------------------------------|
| `/dashboard`                      | Overview, usage, recent files  |
| `/dashboard/workflows`            | Workflow library               |
| `/dashboard/workflows/new`        | Interactive workflow builder   |
| `/dashboard/workflows/[id]`       | Workflow detail                |
| `/dashboard/workflows/[id]/edit`  | Workflow editor                |
| `/dashboard/files`                | File management                |
| `/dashboard/files/[id]`           | File detail & version history  |
| `/dashboard/history`              | Automation run history         |
| `/dashboard/history/[id]`         | Run detail with timeline       |
| `/dashboard/templates`            | Template library               |
| `/dashboard/usage`                | Usage charts and table         |
| `/dashboard/billing`              | Subscription management        |
| `/dashboard/billing/invoices`     | Invoice history                |
| `/dashboard/billing/plans`        | Plan comparison                |
| `/dashboard/devices`              | Device management              |
| `/dashboard/team`                 | Team members                   |
| `/dashboard/team/invitations`     | Pending invitations            |
| `/dashboard/team/roles`           | Role permissions matrix        |
| `/dashboard/notifications`        | Notification centre            |
| `/dashboard/settings`             | Profile, security, AI prefs    |
| `/dashboard/help`                 | Help centre                    |

### Xelora Desktop simulation
| Route      | Description                                          |
|------------|------------------------------------------------------|
| `/desktop` | Full simulated Xelora Desktop app (web-based preview)|

The Desktop page simulates the complete Codex-inspired three-panel interface:
- Permanent left icon rail (Home, Workbooks, Tasks, Workflows, Reports, History, Templates, Notifications, Settings)
- Collapsible contextual sidebar with task list / workbook list
- Main workspace with welcome state, task thread, approval review, spreadsheet editor, settings
- Ctrl+K command palette
- Status bar with live task indicators

### Admin
| Route                 | Description                |
|-----------------------|----------------------------|
| `/admin`              | Platform overview          |
| `/admin/users`        | User management            |
| `/admin/plans`        | Plan configuration         |
| `/admin/subscriptions`| Subscription management    |
| `/admin/usage`        | Platform usage analytics   |
| `/admin/templates`    | Template moderation        |
| `/admin/releases`     | Desktop release management |
| `/admin/system`       | Service health status      |

---

## Folder structure

```
src/
├── app/                     # Next.js App Router pages
│   ├── (auth)/              # Login, register, password reset
│   ├── (marketing)/         # Public website pages
│   ├── admin/               # Admin dashboard
│   ├── dashboard/           # User SaaS dashboard
│   ├── desktop/             # Xelora Desktop simulation
│   └── onboarding/          # Multi-step onboarding
├── components/
│   ├── admin/               # Admin sidebar, topbar
│   ├── dashboard/           # Sidebar, topbar, page-header
│   ├── desktop/             # Desktop icon rail, sidebar, workspace, palette
│   ├── marketing/           # Nav, footer, all landing sections
│   ├── site/                # Shared site helpers (StatePanel, MockWindow)
│   └── ui/                  # Design system components
├── data/                    # All mock data files
├── lib/                     # Utility functions (utils.ts)
├── services/                # Mock async service layer
│   ├── auth.ts              # Login, register, session management
│   └── dashboard.ts         # All dashboard data services
├── stores/                  # Zustand stores (auth-store, ui-store)
├── types/                   # Shared TypeScript types (index.ts)
└── styles/                  # Global CSS (globals.css)
```

---

## Where mock data is stored

All mock data lives in `src/data/`:

| File                  | Contents                              |
|-----------------------|---------------------------------------|
| `mock-users.ts`       | Demo users including admin            |
| `mock-plans.ts`       | Subscription plan definitions         |
| `mock-files.ts`       | Spreadsheet file records + versions   |
| `mock-workflows.ts`   | Workflows and workflow runs           |
| `mock-usage.ts`       | Usage summary and daily data          |
| `mock-notifications.ts`| User notifications                  |
| `mock-billing.ts`     | Subscription and invoice data         |
| `mock-devices.ts`     | Authorised device records             |
| `mock-team.ts`        | Team member records                   |
| `mock-templates.ts`   | Workflow templates                    |
| `mock-admin.ts`       | Admin stats, releases, system status  |
| `mock-marketing.ts`   | Features, solutions, resources        |
| `mock-desktop.ts`     | Desktop tasks and workbooks           |

---

## How to replace mock services with a real API

All data access goes through `src/services/`:

1. **`src/services/auth.ts`** — Replace `login()` and `register()` with `fetch()` calls to your auth endpoint. The `AuthSession` interface matches what you'd return from a JWT-based auth service.

2. **`src/services/dashboard.ts`** — Each function (`getFiles()`, `getWorkflows()`, etc.) is a standalone async function. Replace the mock delay + data with a real `fetch('/api/...')` call. The return types are already defined in `src/types/index.ts`.

3. **Session storage** — The mock writes to `localStorage`. Replace with HTTP-only cookies or your preferred session mechanism in `src/services/auth.ts`.

4. **Types** — `src/types/index.ts` contains all shared TypeScript interfaces. These are designed to match a REST or GraphQL API response shape and can be moved into a shared monorepo package later.

---

## Environment variables

```bash
# .env.example
# No variables are required to run the frontend demo.
# Add these when connecting a real backend:

NEXT_PUBLIC_API_URL=https://api.xelora.app
NEXT_PUBLIC_APP_ENV=development
```

---

## Technology stack

| Technology         | Version   | Purpose                          |
|--------------------|-----------|----------------------------------|
| Next.js            | 16        | App Router, SSR, routing         |
| React              | 19        | UI framework                     |
| TypeScript         | 5         | Strict typing throughout         |
| Tailwind CSS       | 4         | Utility-first styling            |
| Radix UI           | Latest    | Accessible component primitives  |
| Zustand            | 5         | Global auth + UI state           |
| React Hook Form    | 7         | Form state management            |
| Zod                | 4         | Schema validation                |
| Recharts           | 3         | Usage charts                     |
| Lucide React       | Latest    | Icon system                      |
| Sonner             | 2         | Toast notifications              |

---

## Notes

- The Xelora Desktop page (`/desktop`) is a **web simulation** of what the native desktop application would look like. It is not a real Electron or Tauri app.
- The download button on `/download` links to `/api/download/windows` which returns a mock response. No real installer is served.
- All billing actions (upgrade, cancel, buy usage) show success toasts but make no real charges.
- Admin routes are protected by checking `user.isAdmin === true` from the session. Use `admin@xelora.app` / `Admin123!` to access them.
