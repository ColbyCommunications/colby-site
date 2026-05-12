# Deployment (Platform.sh)

The chatbot API is one of two applications in the colby-site
multi-app Platform.sh project. It deploys as its own container with its
own scaling, crons, and disk — only the `mysqldb` service is shared with
the WordPress app at the repo root.

## Application definition

[`.platform.app.yaml`](../.platform.app.yaml) (this directory):

| Field             | Value                                                           |
|-------------------|-----------------------------------------------------------------|
| `name`            | `chatbot-api`                                                   |
| `type`            | `python:3.11`                                                   |
| `size`            | `M`                                                             |
| Build hook        | `pip install --upgrade pip && pip install -r requirements.txt`  |
| Web start         | `uvicorn api:app --host 0.0.0.0 --port $PORT --workers 2`       |
| Disk              | `512` MB                                                        |
| Mount             | `tmp` → local writable directory                                |
| Relationship      | `configdb: "mysqldb:chatbot"`                                   |
| Base memory       | `128` MB (`memory_ratio: 256`)                                  |
| Crons             | `update_vectordb`, `daily_analytics_email` (see [docs/crons.md](./crons.md)) |
| Default env vars  | `PYTHONUNBUFFERED=1`, `CORS_ORIGINS=*`                          |

## Routing

[`../.platform/routes.yaml`](../../.platform/routes.yaml) routes both
`apex` and `www` of every environment to this container:

```yaml
########## CHATBOT API ##########
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

`cache: enabled: false` is important — every `/ask` response is unique and
the SSE stream cannot be cached. The downstream FastAPI app sets
`app.root_path = "/chatbot-api"` so generated URLs include the prefix and
the auth normalization in
[`admin_api._get_request_path`](../admin_api.py) strips it for internal
checks.

## Database

`mysqldb` is defined in
[`../.platform/services.yaml`](../../.platform/services.yaml) with **two
endpoints**:

```yaml
mysqldb:
  type: mysql:10.2
  configuration:
    schemas:
      - main                  # WordPress
      - chatbot_dashboard     # This app
    endpoints:
      mysql:
        default_schema: main
        privileges:
          main: admin
      chatbot:
        default_schema: chatbot_dashboard
        privileges:
          chatbot_dashboard: admin
```

This chatbot app binds only to the `chatbot` endpoint via the `configdb`
relationship, so it cannot accidentally read or write the WordPress
schema.

## Secrets (set via the Platform.sh portal)

These are required and **not** stored in the repo:

```
OPENAI_API_KEY
ALGOLIA_APP_ID
ALGOLIA_API_KEY
QDRANT_URL
QDRANT_API_KEY
OKTA_DOMAIN
OKTA_CLIENT_ID
OKTA_CLIENT_SECRET
OKTA_REDIRECT_URI
ADMIN_SESSION_SECRET
SMTP_HOST  SMTP_PORT  SMTP_USER  SMTP_PASSWORD
ANALYTICS_EMAIL_FROM  ANALYTICS_EMAIL_TO
```

Optional / tunable (defaults shown):

```
AGENT_ID                   = colby-rag
AGENT_NAME                 = Colby RAG Assistant
AGENT_OS_ID                = runtime-rag-os
OPENAI_MODEL               = (DB-driven; falls back to gpt-4.1-mini)
ALGOLIA_INDEX_NAME         = prod_colbyedu_aggregated
ADMIN_OKTA_ENABLED         = false (defaults open in non-prod)
ADMIN_SESSION_COOKIE_NAME  = colby_admin_session
ADMIN_SESSION_SAME_SITE    = lax
ADMIN_SESSION_HTTPS_ONLY   = false
CORS_ORIGINS               = *
REQUEST_TIMEOUT            = 300
```

## How environments map

Each Platform.sh environment (`master`, `dev`, `chatbot`, feature
branches) gets its own copy of:

- The `chatbot-api` container.
- The `mysqldb` service (and therefore its own `chatbot_dashboard`
  schema). This means dashboard edits in `dev` don't leak into `master`.
- Routes scoped to `{default}` (each environment's auto-generated
  hostname).

## Deploy flow

1. Push to the branch tracked by the Platform.sh environment.
2. Platform.sh runs the build hook (`pip install -r requirements.txt`).
3. Platform.sh restarts the container with the new image.
4. On boot, `rag_app.py` runs `init_config_schema()`, which is
   idempotent and self-migrating (see [docs/config-db.md](./config-db.md)).
5. Crons (`update_vectordb`, `daily_analytics_email`) are scheduled per
   the spec in `.platform.app.yaml`.

There is no separate "release" step — the next request after the deploy
sees a fresh `Agent` built from the current config DB.
