# Colby Chatbot API

A FastAPI-based Retrieval-Augmented Generation (RAG) service that powers the
chat assistant on **colby.edu**. It exposes a small public API for asking
questions (`/ask`, `/ask/stream`) and a much larger, Okta-protected admin
dashboard (`/admin/*`) for configuring models, prompts, validators, and
viewing query logs — all without a redeploy.

> **TL;DR** — The app runs as its own Platform.sh container (`chatbot-api`)
> mounted at `https://www.colby.edu/chatbot-api/`. It is **not** a Lando
> service. Lando only manages the WordPress side of the repo; the chatbot
> API is developed and run locally with plain Python + Uvicorn.

---

## Where to look

The codebase is intentionally flat (one module per concern). For deep dives,
see the per-component docs under [`docs/`](./docs):

| Component                               | Files                                                | Doc |
|-----------------------------------------|------------------------------------------------------|-----|
| End-to-end architecture & request flow  | `api.py`, `rag_app.py`                               | [docs/architecture.md](./docs/architecture.md) |
| Public RAG endpoints (`/ask`, `/ask/stream`, `/health`, `/info`) | `rag_app.py`                       | [docs/architecture.md#public-endpoints](./docs/architecture.md#public-endpoints) |
| Runtime agent + Algolia + Qdrant search | `runtime_rag_knowledge.py`                           | [docs/runtime-rag.md](./docs/runtime-rag.md) |
| Input validation pre-hook + guardrails  | `input_validation_pre_hook.py`, `validation_search_context.py` | [docs/input-validation.md](./docs/input-validation.md) |
| Admin API (config CRUD, logs, metrics)  | `admin_api.py`                                       | [docs/admin-api.md](./docs/admin-api.md) |
| Admin dashboard UI (static HTML/JS/CSS) | `admin_ui/`                                          | [docs/admin-ui.md](./docs/admin-ui.md) |
| Configuration database (MySQL)          | `config_db.py`                                       | [docs/config-db.md](./docs/config-db.md) |
| Query logging & per-stage metadata      | `query_logging.py`                                   | [docs/query-logging.md](./docs/query-logging.md) |
| Okta-backed admin authentication        | `okta_auth.py`, session middleware in `rag_app.py`   | [docs/okta-auth.md](./docs/okta-auth.md) |
| Scheduled jobs (vector rebuild, email)  | `update_vector_db.py`, `daily_analytics_email.py`    | [docs/crons.md](./docs/crons.md) |
| Platform.sh deployment & routing        | `.platform.app.yaml`, `../.platform/routes.yaml`     | [docs/deployment.md](./docs/deployment.md) |
| Local development (no Docker required)  | `requirements.txt`, `.env`                           | [docs/local-development.md](./docs/local-development.md) |

---

## High-level architecture

```
                  ┌────────────────────────────────────────────────────┐
                  │  Platform.sh router (.platform/routes.yaml)        │
                  │  https://www.colby.edu/chatbot-api → chatbot-api   │
                  └─────────────────────┬──────────────────────────────┘
                                        │
                  ┌─────────────────────▼──────────────────────────────┐
                  │  chatbot-api container (Python 3.11, Uvicorn)      │
                  │                                                    │
                  │   api.py  ──► rag_app.app  (FastAPI / AgentOS)     │
                  │                ├── /ask, /ask/stream, /health,     │
                  │                │   /info     (public RAG)          │
                  │                ├── /admin/*  (Okta + dashboard)    │
                  │                └── SessionMiddleware (Okta)        │
                  │                                                    │
                  │   runtime_rag_knowledge.build_agent()              │
                  │     ├── Algolia keyword search                     │
                  │     ├── Qdrant vector search                       │
                  │     └── Agno Agent + OpenAI model                  │
                  │                                                    │
                  │   input_validation_pre_hook                        │
                  │     ├── colby_query_validation (LLM)               │
                  │     └── colby_blacklist_validation (LLM)           │
                  └──────────┬──────────────────────┬──────────────────┘
                             │                      │
                  ┌──────────▼──────────┐   ┌───────▼──────────────┐
                  │ MySQL (mysqldb)     │   │ External services    │
                  │   chatbot endpoint  │   │  • Algolia           │
                  │   schema:           │   │  • Qdrant Cloud      │
                  │   chatbot_dashboard │   │  • OpenAI            │
                  │                     │   │  • Okta (admin)      │
                  │ llm_models          │   │  • SMTP (cron email) │
                  │ llm_agents          │   └──────────────────────┘
                  │ agent_instructions  │
                  │ app_messages        │
                  │ query_logs          │
                  │ query_log_parts     │
                  │ query_examples      │
                  └─────────────────────┘
```

See [docs/architecture.md](./docs/architecture.md) for the full request
lifecycle (validation → retrieval → answer → logging).

---

## The two surfaces, in one paragraph each

**Public RAG (`/chatbot-api/ask*`).** A user question hits FastAPI, runs
through the Agno input-validation pre-hooks (which themselves call Algolia
+ Qdrant to gather context), then the runtime agent — also built on Agno —
performs keyword + vector retrieval and streams an answer back via SSE or
returns it in one shot. Every step is recorded in `query_logs` /
`query_log_parts` so it shows up in the dashboard. Implementation lives in
[`rag_app.py`](./rag_app.py) and [`runtime_rag_knowledge.py`](./runtime_rag_knowledge.py).
See [docs/runtime-rag.md](./docs/runtime-rag.md).

**Admin dashboard (`/chatbot-api/admin/*`).** A Colby staff member signs in
with Okta, then the dashboard lets them change LLM models, edit agent
instructions, manage whitelist/blacklist training examples, browse the full
query log (with CSV export), and watch weekly metrics — all by reading and
writing the same MySQL `configdb` that the runtime reads on every request.
That means a prompt change at 10:00 is live by 10:00:01, no deploy needed.
Routes live in [`admin_api.py`](./admin_api.py); the static UI is
[`admin_ui/`](./admin_ui/). See [docs/admin-api.md](./docs/admin-api.md) and
[docs/admin-ui.md](./docs/admin-ui.md).

---

## Where this fits in the wider colby-site repo

The chatbot is one application in a multi-app Platform.sh project. The
**WordPress app** at the repo root and the **chatbot-api app** in this
directory share the same MySQL service but use separate endpoints / schemas
(see [`.platform/services.yaml`](../.platform/services.yaml)):

- `mysqldb:mysql` endpoint → schema `main`  →  used by WordPress
- `mysqldb:chatbot` endpoint → schema `chatbot_dashboard` → used by this app

### Lando

Lando (`.lando.yml` at the repo root) only spins up the **WordPress** side
locally — PHP, Nginx, the `main` MySQL schema, and the `platform` CLI
passthrough. The chatbot API does **not** have a Lando service definition
and is **not** served by `lando start`. To run the chatbot API locally,
follow [docs/local-development.md](./docs/local-development.md) — it runs
directly with `uvicorn` against either a local MySQL DB or, more commonly,
a remote Platform.sh `chatbot_dashboard` schema reached via `platform
tunnel:open`.

### Platform.sh

- App definition: [`.platform.app.yaml`](./.platform.app.yaml) (this dir)
- Routing: [`../.platform/routes.yaml`](../.platform/routes.yaml) — see the
  `########## CHATBOT API ##########` section.
- Services: [`../.platform/services.yaml`](../.platform/services.yaml)
- Crons: defined inline in this app's `.platform.app.yaml`
  (`update_vectordb`, `daily_analytics_email`)

See [docs/deployment.md](./docs/deployment.md) for the full deployment
story including environment-variable wiring.

---

## Quick start (local dev)

```bash
# from chatbot-api/
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Open a Platform.sh tunnel so the local app can reach the chatbot MySQL,
# Algolia, Qdrant, etc. (env vars are exported to .env automatically by
# the platform CLI when you do `platform tunnel:open`).
platform tunnel:open

# Run the combined app (RAG + admin).
python api.py
# → http://127.0.0.1:7777 (or whatever AgentOS picks)
```

Full instructions, including which env vars are required vs. optional and
how to point at a **local** MySQL instead of a tunnel, are in
[docs/local-development.md](./docs/local-development.md).

---

## Endpoints at a glance

| Method | Path                          | Auth         | Purpose |
|--------|-------------------------------|--------------|---------|
| GET    | `/chatbot-api/`               | none         | Login splash (renders the Okta sign-in card) |
| POST   | `/chatbot-api/ask`            | none         | Synchronous question → full answer JSON |
| GET    | `/chatbot-api/ask/stream`     | none         | SSE stream (query params) |
| POST   | `/chatbot-api/ask/stream`     | none         | SSE stream (JSON body) |
| GET    | `/chatbot-api/health`         | none         | Liveness check |
| GET    | `/chatbot-api/info`           | none         | Agent + endpoint map |
| GET    | `/chatbot-api/admin/`         | Okta session | Dashboard home |
| GET    | `/chatbot-api/admin/dashboard`| Okta session | Config dashboard (models, agents, messages) |
| GET    | `/chatbot-api/admin/responses`| Okta session | Query log explorer |
| GET    | `/chatbot-api/admin/login`    | none         | Okta authorize redirect |
| GET    | `/chatbot-api/admin/authorization-code/callback` | none | Okta OIDC callback |
| GET    | `/chatbot-api/admin/logout`   | none         | Clears session, redirects to Okta logout |
| —      | `/chatbot-api/admin/<resource>` | Okta session | CRUD JSON endpoints — see [docs/admin-api.md](./docs/admin-api.md) |

---

## Repo-level pointers (everything that is NOT under this directory)

- [`../README.md`](../README.md) — top-level WordPress + Platform.sh setup,
  the Lando workflow, and Composer notes.
- [`../.lando.yml`](../.lando.yml) — WordPress-only Lando recipe.
- [`../.platform/routes.yaml`](../.platform/routes.yaml) — global Platform.sh
  routing (search for `CHATBOT API`).
- [`../.platform/services.yaml`](../.platform/services.yaml) — shared MySQL
  service definition.

---

## Component map (file → doc)

| File                              | One-line role                                          | Doc |
|-----------------------------------|--------------------------------------------------------|-----|
| `api.py`                          | App composition entrypoint (RAG + admin)               | [docs/architecture.md](./docs/architecture.md) |
| `rag_app.py`                      | Public FastAPI routes, CORS, session middleware        | [docs/architecture.md](./docs/architecture.md) |
| `runtime_rag_knowledge.py`        | RAG agent factory, Algolia + Qdrant search tools       | [docs/runtime-rag.md](./docs/runtime-rag.md) |
| `input_validation_pre_hook.py`    | Pre-run validators (`colby_query_validation`, blacklist) | [docs/input-validation.md](./docs/input-validation.md) |
| `validation_search_context.py`    | Packs search context into validator prompts            | [docs/input-validation.md](./docs/input-validation.md) |
| `admin_api.py`                    | All `/admin/*` routes (config, logs, metrics, training) | [docs/admin-api.md](./docs/admin-api.md) |
| `admin_ui/*.html`, `*.js`, `*.css` | Vanilla static dashboard, served via `/admin/static/*` | [docs/admin-ui.md](./docs/admin-ui.md) |
| `config_db.py`                    | MySQL schema bootstrap + config DAOs                   | [docs/config-db.md](./docs/config-db.md) |
| `query_logging.py`                | ContextVar-based per-request logging into MySQL        | [docs/query-logging.md](./docs/query-logging.md) |
| `okta_auth.py`                    | Okta OIDC config + session keys                        | [docs/okta-auth.md](./docs/okta-auth.md) |
| `update_vector_db.py`             | Daily cron — rebuilds Qdrant from Algolia              | [docs/crons.md](./docs/crons.md) |
| `daily_analytics_email.py`        | Daily cron — emails activity report                    | [docs/crons.md](./docs/crons.md) |
| `requirements.txt`                | Pinned runtime dependencies                            | [docs/local-development.md](./docs/local-development.md) |
| `.platform.app.yaml`              | Container, web, mounts, relationships, crons           | [docs/deployment.md](./docs/deployment.md) |
