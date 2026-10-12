# Security notes

## What's covered

**Authentication.** Every endpoint except `GET /` requires `X-API-Key` to
match `LOCAL_API_KEY`, checked with `secrets.compare_digest` (constant-time,
not `!=`, which leaks timing information). If `LOCAL_API_KEY` is unset, the
app **refuses to start** unless you explicitly set `ALLOW_NO_AUTH=true` - it
will not silently run wide open because a env var was forgotten.
Previously, `/knowledge/add`, `/knowledge/search`, and
`/knowledge/{user_id}/documents` had **no auth check at all** - fixed.

**Rate limiting.** A simple in-memory sliding window (`security.rate_limit`),
keyed by API key (or IP if none given), default 60 requests/60s. This is a
baseline, not a production-grade limiter - it resets on restart and doesn't
share state across multiple server processes. For real production use behind
a load balancer, put a proper rate limiter (nginx, Cloudflare, etc.) in front
of this too.

**Path traversal.** `/knowledge/add`'s `file_path` is resolved and checked
against `KNOWLEDGE_INGEST_ALLOWED_DIR` before anything reads it
(`security.validate_ingest_path`) - a request can no longer read arbitrary
files off the server's disk via `../../` or an absolute path elsewhere.

**Codegen sandbox** (`codegen/executor.py`) - unchanged from before, still:
- AST-checked import allowlist (`xlwings`, `openpyxl`, `datetime`, `math`,
  `re`, `json`, `statistics` only)
- Blocks `eval`, `exec`, `os`, `subprocess`, `__import__`, etc.
- Blocks direct `.formula`/`.formula2` assignment (forces `insert_formula`)
- Runs in a subprocess with a timeout - this is "a seatbelt, not a cage":
  it stops obviously dangerous code, it does not make arbitrary AI-written
  code execution fully safe. Don't expose `run_excel_code` to untrusted users.

**Skill library** (`skills/loader.py`). Every folder in
`skills/library/<name>/` with a `SKILL.md` and `impl.py` is loaded at
startup; a folder that fails to load is logged as an error and skipped.
`impl.py` is real, executable Python with full Excel/COM and file-system
access, so the skill folder must only be writable by trusted parties. The
desktop agent installs it under Program Files, which standard users cannot
modify. (An earlier SHA-256 manifest was removed: its hashes broke on
Windows line endings and on every unregenerated edit, and the manifest sat
in the same folder as the skills it protected, so it added no protection
against anyone able to write there.)

## What's NOT covered (be aware of these)

- **No user-level auth/authorization.** One shared `LOCAL_API_KEY` acts as
  any `user_id` - anyone with the key can read/write another user's
  preferences, knowledge base, or tasks. Fine for single-user desktop use;
  not fine multi-tenant without adding real per-user auth (JWT, sessions, etc).
- **No TLS here.** This app speaks plain HTTP. If it's ever reachable over
  a network (not just localhost), put it behind HTTPS (a reverse proxy)
  or the API key travels in cleartext.
- **`run_excel_code` (codegen) is still AI-written code with COM/file
  access**, sandboxed but not sealed. The AST allowlist blocks known-bad
  patterns; it is not a formal proof of safety. Treat it the same way you'd
  treat any "AI writes code, we run it" feature.
- **The rate limiter is in-memory and per-process** - restart clears it,
  and it doesn't coordinate across multiple workers/instances.
