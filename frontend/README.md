# Xelora — Web App (Next.js)

The Xelora website, dashboard and admin area. Browser requests go to
Next.js API routes in `src/app/api/`, which call the FastAPI backend
server-side with `BACKEND_API_KEY`; the key never reaches the browser.

## Run locally

```bash
npm install
cp .env.example .env.local     # set BACKEND_URL and BACKEND_API_KEY
npm run dev                    # http://localhost:3000
```

`BACKEND_API_KEY` must equal `LOCAL_API_KEY` in `backend/.env`.

## Build

```bash
npx tsc --noEmit
npm run build && npm start
```

## Layout

```
src/
├── app/          routes (marketing, auth, dashboard, admin, desktop) + api/ proxies
├── components/   UI, layout, dashboard and desktop components
├── lib/          session, backend client, desktop detection, release lookup
├── services/     data-access functions used by pages
├── stores/       Zustand stores
├── types/        shared TypeScript types
└── data/         mock data still used where the backend has no endpoint yet
```

Which areas still use `src/data/` mocks is listed in
`docs/reports/INTEGRATION.md` → "Known gaps".

## Deploy

Vercel, with **Root Directory = `frontend`**. See `docs/DEPLOYMENT.md`.
