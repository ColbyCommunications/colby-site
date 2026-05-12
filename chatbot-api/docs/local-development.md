# Local development

The chatbot API is **not** part of the repo's Lando setup. Lando
(`../.lando.yml`) only provisions the WordPress side — PHP, Nginx, the
`main` MySQL schema, and the `platform` CLI passthrough. The chatbot API
runs as a plain Python process against either:

1. A **Platform.sh tunnel** that exposes the cloud `chatbot_dashboard`
   MySQL (most common), or
2. A **local MySQL** instance you point at with `CONFIG_DB_URL`.

You do **not** need Docker, Lando, or `lando start` to develop the
chatbot API.

## Prerequisites

- Python 3.11 (matches the Platform.sh container).
- The Platform.sh CLI, if you plan to tunnel into a cloud DB. The
  repo-root Lando config installs this inside its `appserver` container,
  but for chatbot-api work it is more convenient to install it on the
  host: `curl -fsSL https://raw.githubusercontent.com/platformsh/cli/main/installer.sh | bash`.

## Setup

```bash
cd chatbot-api
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## `.env` template

Create `chatbot-api/.env` (gitignored) with at minimum:

```ini
# Database — pick one:
# (a) Tunnel mode: leave CONFIG_DB_URL unset, PLATFORM_RELATIONSHIPS will
#     be exported by `platform tunnel:open`.
# (b) Local MySQL:
# CONFIG_DB_URL=mysql://root:root@127.0.0.1:3306/chatbot_dashboard

# External services
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
ALGOLIA_APP_ID=...
ALGOLIA_API_KEY=...
ALGOLIA_INDEX_NAME=prod_colbyedu_aggregated
QDRANT_URL=https://...qdrant.io
QDRANT_API_KEY=...

# Admin auth — disable Okta locally
ADMIN_OKTA_ENABLED=false
ADMIN_SESSION_SECRET=any-random-string

# Optional
CORS_ORIGINS=*
AGENT_ID=colby-rag
AGENT_NAME=Colby RAG Assistant
```

`load_dotenv()` runs at the top of `rag_app.py`, so this file is picked
up automatically.

## Running with a Platform.sh tunnel

```bash
platform tunnel:open --project <project-id> --environment master
# This sets PLATFORM_RELATIONSHIPS for the current shell, exposing the
# chatbot MySQL via a local port. config_db.py parses it automatically.

python api.py
# → http://127.0.0.1:7777   (AgentOS-chosen port)
```

When you're done:

```bash
platform tunnel:close --all
```

## Running with a local MySQL

```bash
# Start MySQL locally however you prefer (brew services start mysql,
# docker run mysql, etc.), then:
mysql -uroot -proot -e "CREATE DATABASE chatbot_dashboard;"

# In .env:
CONFIG_DB_URL=mysql://root:root@127.0.0.1:3306/chatbot_dashboard

python api.py
```

`init_config_schema()` will create all the tables on first boot. The
dashboard will be empty until you add models and agents via the admin UI
or by SQL.

## What runs without a DB

If neither `CONFIG_DB_URL` nor `PLATFORM_RELATIONSHIPS` is set, the app
still boots — every config DAO returns `None` and the runtime agent uses
hard-coded fallback prompts prefixed with `[RUNTIME_RAG_DEV]`. This is
useful for quick "does my code at least import and serve `/ask`?" checks
but is not a real local dev experience.

## Hitting the API

```bash
# Sync
curl -s -X POST http://127.0.0.1:7777/ask \
  -H 'content-type: application/json' \
  -d '{"message":"What are the library hours?"}' | jq .

# Streaming (SSE)
curl -N "http://127.0.0.1:7777/ask/stream?message=What%20are%20the%20library%20hours"

# Admin (when ADMIN_OKTA_ENABLED=false)
open http://127.0.0.1:7777/admin/dashboard
```

In local dev `app.root_path` is still set to `/chatbot-api`, which only
affects URL **generation** (e.g. `request.url_for(...)`). The routes
themselves are served at their unprefixed paths (`/ask`, `/admin/...`),
so the URLs above don't need the prefix.

## Cron scripts

```bash
# Rebuild Qdrant locally — destructive, hits prod Qdrant unless you
# point QDRANT_URL/QDRANT_API_KEY at a non-prod cluster.
python update_vector_db.py

# Send the analytics email (requires SMTP_* env vars).
python daily_analytics_email.py
```

See [docs/crons.md](./crons.md).

## Why not Lando for this app?

- The chatbot is a Python service, not PHP/WordPress; running it through
  Lando's `appserver` would mean a second container image and a second
  PHP/Nginx context just for one Python process.
- Local Python + `uvicorn --reload` is faster than a Lando rebuild on
  every change.
- The `mysqldb` schema this app needs (`chatbot_dashboard`) is **not**
  created by the Lando-managed MySQL — Lando provisions the `main`
  schema for WordPress only. A tunnel is the canonical way to get a real
  copy of the chatbot data locally.

If you do want to add a Lando service for the chatbot in the future, it
would need its own `python:3.11` service, env-var passthrough, and a
separate MySQL schema or service — none of which exist today.
