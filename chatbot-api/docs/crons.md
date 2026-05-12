# Scheduled jobs

Two crons are defined inline in
[`.platform.app.yaml`](../.platform.app.yaml). They run inside the same
container image as the web app, so they share the same Python env,
relationships, and secrets.

## `update_vectordb` — daily Qdrant rebuild

```yaml
update_vectordb:
  spec: '0 9 * * *'   # 4:00 AM EST / 5:00 AM EDT
  commands:
    start: 'python update_vector_db.py'
```

Script: [`update_vector_db.py`](../update_vector_db.py).

### What it does

1. **Deletes** the existing Qdrant collection `colby_knowledge`.
2. Recreates it with `text-embedding-3-small` dimensions (1536) and a
   payload index on the source label field.
3. Pulls **all** documents from Algolia (`prod_colbyedu_aggregated` by
   default).
4. Chunks each document with a fixed 300-token window and 150-token
   overlap (via `tiktoken` `cl100k_base`).
5. Embeds chunks in batches of 64 with up to 3 parallel OpenAI requests.
6. Uploads to Qdrant in batches of 512 points.

### Why a full rebuild each day?

It is simpler than incremental sync, sidesteps "deleted document"
bookkeeping, and runs in well under the cron window for the current
content volume. The vector store's `VectorGraphHealthError` check on
every `/ask` request will fire a 500 if the collection ever drops below
threshold — that's how we detect a failed cron in production.

### Required env vars

| Variable                    | Purpose |
|-----------------------------|---------|
| `ALGOLIA_APP_ID`            | Algolia application id |
| `ALGOLIA_API_KEY`           | Algolia admin/search key |
| `ALGOLIA_INDEX_NAME`        | Defaults to `prod_colbyedu_aggregated` |
| `QDRANT_URL`                | Qdrant Cloud URL |
| `QDRANT_API_KEY`            | Qdrant Cloud key |
| `OPENAI_API_KEY`            | For embeddings |

## `daily_analytics_email` — daily summary email

```yaml
daily_analytics_email:
  spec: '0 13 * * *'   # ~8:00 AM EST / 9:00 AM EDT
  commands:
    start: 'python daily_analytics_email.py'
```

Script: [`daily_analytics_email.py`](../daily_analytics_email.py).

### What it does

1. Computes the ET calendar day window (matches
   `admin_api.list_query_logs`'s "Today" filter so the email and dashboard
   agree).
2. Reads `query_logs` + `query_log_parts` to compute:
   - Total queries.
   - Counts split by status (`answered`, `blocked`, `error`).
   - Blocked-by-which-validator breakdown.
   - `passed_guardrails` and `no_answer_after_pass` for the funnel.
   - Top answered and top blocked queries (by frequency).
3. Renders an HTML email and sends it via SMTP.

### Required env vars

| Variable               | Purpose |
|------------------------|---------|
| `SMTP_HOST`            | SMTP relay |
| `SMTP_PORT`            | Usually 587 |
| `SMTP_USER` / `SMTP_PASSWORD` | Credentials |
| `ANALYTICS_EMAIL_FROM` | Envelope sender |
| `ANALYTICS_EMAIL_TO`   | Comma-separated recipient list |

## Where to look in the Platform.sh UI

Both crons appear under **Settings → Crons** for the `chatbot-api` app
in any environment. Logs are in **Logs → Crons** — search for the cron
name.

## Running them manually

```bash
# In a deployed environment:
platform ssh -A chatbot-api -- "cd /app && python update_vector_db.py"
platform ssh -A chatbot-api -- "cd /app && python daily_analytics_email.py"

# Locally (with platform tunnel:open and all env vars set):
python update_vector_db.py
python daily_analytics_email.py
```
