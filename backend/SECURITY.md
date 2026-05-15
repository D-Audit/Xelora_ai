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

**Skill library integrity** (`skills/loader.py`) - new. Every skill in
`skills/library/<name>/` is only loaded if it's listed in
`skills/library/_manifest.json` with a matching SHA-256 hash of both
`SKILL.md` and `impl.py`. A skill folder that exists on disk but isn't in
the manifest, or whose files don't match their pinned hash, is refused and
logged loudly at startup - not silently skipped, not silently loaded. This
matters because `impl.py` is real, executable Python with full Excel/COM
and file-system access - a skill folder is a code-execution surface, and
this stops a dropped-in or tampered folder from running just by existing.

**Run `tools/generate_skill_manifest.py` after every legitimate skill
add/edit** - it re-hashes everything and rewrites the manifest. If you skip
this, the loader will correctly refuse to load whatever you changed (this
is the intended behavior, not a bug).

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
