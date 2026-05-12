# Architecture

How the chatbot API is wired together, from `api.py` down to the database
and the external services it depends on.

## App composition

[`api.py`](../api.py) is intentionally tiny:

```python
from admin_api import admin_router
from rag_app import app, agent_os

app.include_router(admin_router)

if __name__ == "__main__":
    agent_os.serve(app="api:app", reload=True)
```

It mounts two things on the same FastAPI app:

1. **`rag_app.app`** — the public RAG endpoints (`/ask`, `/ask/stream`,
   `/health`, `/info`) plus a root-splash middleware that returns the Okta
   login card for `GET /chatbot-api/`.
2. **`admin_api.admin_router`** — every `/admin/*` route (config CRUD,
   query logs, metrics, training examples, dashboard HTML, static assets).

In Platform.sh, the production start command is

```yaml
start: "uvicorn api:app --host 0.0.0.0 --port $PORT --workers 2"
```

so `api:app` is what serves both halves.

## Public endpoints

Defined in [`rag_app.py`](../rag_app.py).

| Route                 | Handler                          | Notes |
|-----------------------|----------------------------------|-------|
| `POST /ask`           | `ask`                            | Sync. Returns `AskResponse{content, agent_id}`. |
| `GET  /ask/stream`    | `ask_stream_get`                 | SSE. `?message=...&sources=Libraries,Admissions` |
| `POST /ask/stream`    | `ask_stream_post`                | SSE. JSON body matches `AskRequest`. |
| `GET  /health`        | `health_check`                   | Process-level liveness only. |
| `GET  /info`          | `info`                           | Reports the live model id by building a fresh agent. |
| `GET  /` (middleware) | `root_splash_middleware`         | Renders the Okta sign-in card. |

All four `/ask*` handlers follow the same lifecycle (see below). The
docstrings on each route in `rag_app.py` describe their exact request and
response shapes.

## Per-request lifecycle

```
POST /chatbot-api/ask  {"message": "...", "sources": [...]}

 1. start_request_log(message)             → row in query_logs (status='pending')
 2. create_assistant()                     → Agno Agent rebuilt from config DB
 3. build_agent_query_with_context(...)    → enriches user message with retrieval hints
 4. assistant.arun(...)                    → runs Agno pre-hooks then the model
     ├── colby_query_validation             (validation_primary agent)
     │     uses validation_search_context to embed Algolia + Qdrant snippets
     │     → may raise InputCheckError → standard rejection message returned
     ├── colby_blacklist_validation         (validation_blacklist agent)
     │     → may raise InputCheckError
     └── runtime_rag agent                  (built by runtime_rag_knowledge.build_agent)
           tools: keyword_search (Algolia), vector_search (Qdrant)
 5. add_log_part(stage='runtime_rag', ...) → row in query_log_parts
 6. finalize_request_log(status='answered' | 'blocked' | 'error', ...)
 7. clear_request_log_context()             → resets ContextVars

→ 200 OK   {"content": "...", "agent_id": "colby-rag"}
```

The streaming variants are the same with one twist: the first chunk is
awaited *before* the HTTP 200 is sent. That way LLM connection failures
become a normal 500 instead of a half-open `text/event-stream`. See
[`rag_app._get_first_valid_chunk`](../rag_app.py).

## Why a fresh agent every request?

`create_assistant()` rebuilds the Agno `Agent` from the config DB on every
call. That makes the admin dashboard truly live — change a prompt, change a
model, change the rejection message, and the next request picks it up
without restarting the worker. The trade-off is a small per-request cost
for re-reading the config DB. See [docs/config-db.md](./config-db.md).

## Middleware stack (top → bottom)

Added inside `rag_app.py`:

1. **`root_splash_middleware`** — short-circuits `GET /` to render the
   login HTML.
2. **`SessionMiddleware`** — Starlette session cookie for Okta. Secret comes
   from `ADMIN_SESSION_SECRET` (or `APP_SESSION_SECRET`); cookie name is
   `ADMIN_SESSION_COOKIE_NAME` (default `colby_admin_session`).
3. **`CORSMiddleware`** — origins are comma-separated from `CORS_ORIGINS`
   env (default `*`).

`app.root_path = "/chatbot-api"` is set on `app` so FastAPI generates URLs
with the Platform.sh prefix even though the worker itself binds to `/`.

## External dependencies

| What             | Used for                                  | Configured via |
|------------------|-------------------------------------------|----------------|
| OpenAI           | Embeddings + chat completions             | `OPENAI_API_KEY`, `OPENAI_MODEL` |
| Algolia          | Keyword search over Colby content         | `ALGOLIA_APP_ID`, `ALGOLIA_API_KEY`, `ALGOLIA_INDEX_NAME` |
| Qdrant Cloud     | Vector / semantic search                  | `QDRANT_URL`, `QDRANT_API_KEY` |
| Okta             | Admin dashboard SSO                       | `OKTA_*` (see [docs/okta-auth.md](./okta-auth.md)) |
| MySQL (Platform) | Config + query logs                       | `PLATFORM_RELATIONSHIPS` (`configdb`) or `CONFIG_DB_URL` |
| SMTP             | `daily_analytics_email.py`                | `SMTP_*` env vars |

## Routing in production

Platform.sh routes both apex and `www` of every environment's default
domain to this container:

```yaml
"https://www.{default}/chatbot-api":
    type: upstream
    upstream: "chatbot-api:http"
    cache:
        enabled: false

"https://{default}/chatbot-api":
    type: upstream
    upstream: "chatbot-api:http"
    cache:
        enabled: false
```

(from [`../../.platform/routes.yaml`](../../.platform/routes.yaml))

The strip-prefix dance is handled inside the app: `app.root_path =
"/chatbot-api"` plus the `_get_request_path` helper in
[`admin_api.py`](../admin_api.py) normalize paths so the same code works
locally (where there is no prefix) and in production.
