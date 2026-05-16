"""
server.py
THE NEW ENTRYPOINT. Run this instead of main.py:

    uvicorn server:app --reload

main.py is NOT modified anywhere in this addon - this file imports its
`app` object and attaches the new /auth and /billing routers plus a
plan-enforcement middleware on top of it. main.py continues to work
exactly as it did before (uvicorn main:app still runs the agent API
alone, with no auth/billing/plan-limit layer) - server.py is a strict
superset.

Why middleware instead of editing the /task route in main.py:
Adding per-user plan limits to POST /task without touching main.py
means we can't add a FastAPI `Depends(...)` to that route directly
(that *would* require editing main.py). Starlette/FastAPI middleware
can inspect and short-circuit a request before it reaches the route
handler, so that's where the check lives instead - functionally
equivalent, zero changes to main.py.
"""
from fastapi.responses import JSONResponse

# Import main's app FIRST.
from main import app  # noqa: E402

# Import the new models so their tables are registered on Base.metadata
# before database.init_db() (called inside main.py's startup event)
# runs Base.metadata.create_all() - this is what makes auth_users,
# subscriptions, usage_records, invoices get created automatically
# alongside the existing users/tasks/action_logs/etc tables.
import auth_billing_models  # noqa: F401,E402
import workspace_models  # noqa: F401,E402 - registers files/team/devices/notifications/workflows tables

from auth import router as auth_router, decode_token  # noqa: E402
from oauth import router as oauth_router  # noqa: E402
from billing import router as billing_router  # noqa: E402
from files import router as files_router  # noqa: E402
from devices import router as devices_router  # noqa: E402
from team import router as team_router  # noqa: E402
from notifications import router as notifications_router  # noqa: E402
from workflows import router as workflows_router  # noqa: E402
from admin import router as admin_router  # noqa: E402
from plan_guard import check_and_increment_task_usage, PlanLimitExceeded  # noqa: E402
from database import SessionLocal  # noqa: E402
from seed_templates import seed_default_templates  # noqa: E402
import config  # noqa: E402

app.include_router(auth_router)
app.include_router(oauth_router)
app.include_router(billing_router)
app.include_router(files_router)
app.include_router(devices_router)
app.include_router(team_router)
app.include_router(notifications_router)
app.include_router(workflows_router)
app.include_router(admin_router)


@app.on_event("startup")
def _seed_on_startup():
    if SessionLocal is None:
        return
    db = SessionLocal()
    try:
        seed_default_templates(db)
    finally:
        db.close()


@app.middleware("http")
async def enforce_plan_limits(request, call_next):
    """Only touches POST /task. Every other route (including all of
    main.py's other endpoints and the new /auth, /billing routes)
    passes straight through untouched."""
    if request.method == "POST" and request.url.path == "/task":
        if SessionLocal is None:
            # No DATABASE_URL configured - main.py itself already runs
            # without persistence in that mode, so there's nothing to
            # enforce a plan against. Let main.py's existing behavior
            # (works, just doesn't save) stand.
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"error": "Missing Authorization: Bearer <token>. Log in first."},
            )

        try:
            user_id = decode_token(auth_header.removeprefix("Bearer ").strip())
        except Exception:
            return JSONResponse(status_code=401, content={"error": "Invalid or expired session token."})

        db = SessionLocal()
        try:
            check_and_increment_task_usage(db, user_id)
        except PlanLimitExceeded as e:
            return JSONResponse(status_code=e.status_code, content={"error": e.message})
        finally:
            db.close()

    return await call_next(request)


if config.ALLOW_NO_AUTH and not config.LOCAL_API_KEY:
    print("server.py: reminder - ALLOW_NO_AUTH=true means the agent endpoints in "
          "main.py have no X-API-Key protection. /auth and /billing are still "
          "protected by their own JWT check regardless of this setting.")
