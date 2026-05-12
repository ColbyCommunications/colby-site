# Configuration database

The chatbot API uses a MySQL database to store **everything the admin
dashboard can edit at runtime**: model catalog, agent prompts, app
messages, query logs, and training examples. The runtime reads from this
DB on every request (`build_agent()` in
[`runtime_rag_knowledge.py`](../runtime_rag_knowledge.py)), so an edit in
the dashboard is live the moment it's saved — no redeploy.

Module: [`config_db.py`](../config_db.py).

## Connection

`get_db_connection()` resolves credentials in this order:

1. **`CONFIG_DB_URL`** — e.g. `mysql://user:pass@host:3306/dbname`. Useful
   for local dev pointing at a tunnel or a local MySQL.
2. **`PLATFORM_RELATIONSHIPS`** / **`UPSUN_RELATIONSHIPS`** — base64-encoded
   JSON injected by Platform.sh. Looks up the `configdb` relationship.

If neither is set, `get_db_connection()` returns `None` and every config
DAO silently falls back to the in-code defaults. The runtime agent will
log `[RUNTIME_RAG][DEV]` lines and prefix prompts with `[RUNTIME_RAG_DEV]`
so it's obvious in the dashboard which run used the fallback.

`.platform.app.yaml` wires the relationship:

```yaml
relationships:
  configdb: "mysqldb:chatbot"
```

That `mysqldb:chatbot` endpoint is defined in
[`../.platform/services.yaml`](../../.platform/services.yaml) — it owns
the `chatbot_dashboard` schema and is **separate** from the `mysql`
endpoint used by WordPress.

## Schema

`init_config_schema()` runs on app boot and is fully idempotent. It
creates / verifies the following tables:

### `llm_models`
The catalog of OpenAI models that can be selected for any agent.
`is_active` controls whether it appears in the dashboard dropdown;
`is_default` is informational.

### `llm_agents`
One row per logical agent (`runtime_rag`, `validation_primary`,
`validation_blacklist`). Stores the chosen `model_id` and a
`description_template` (which can contain `{current_date}` and
`{standard_rejection_message}` placeholders).

### `agent_instructions`
Ordered (by `position`) list of instruction strings per agent. Cascades on
delete via `fk_agent_instructions_agent`.

### `app_messages`
Key/value table for things the runtime needs to surface verbatim. Today,
only `standard_rejection_message` is read.

### `query_logs`
One row per user request. Statuses: `pending`, `answered`, `blocked`,
`error`. `blocked_by` records which validator stage rejected the message
(set by `mark_blocked_by` from
[`query_logging.py`](../query_logging.py)).

### `query_log_parts`
Per-stage detail rows linked back to `query_logs.id`. Each row captures
the `stage` (e.g. `validation_primary`, `validation_blacklist`,
`runtime_rag`), the actual `model_id` and `agent_name` used, a boolean
`using_db_config` flag, whether the stage blocked the query, and an
opaque JSON `result_json` payload (for the runtime stage, this contains
the final answer text).

### `query_examples`
Whitelist / blacklist training examples. `kind` ∈ {`whitelist`,
`blacklist`}. Promoted into this table from the responses dashboard;
consumed by the validator agents as few-shot examples. `init_config_schema`
includes an **idempotent backfill** that migrates legacy
`BLACKLISTED_QUERY_EXAMPLE:` / `WHITELISTED_QUERY_EXAMPLE:` entries
previously stored as `agent_instructions` rows.

## DAOs (selected)

- `load_agent_config(agent_key)` → `AgentConfig` (name, model_id,
  description_template, ordered instructions).
- `get_app_message(message_key)` → str | None.
- `get_query_examples(kind)` → list of training example strings.
- `get_openai_metadata_or_none()` → dict of Platform.sh env metadata to
  attach to OpenAI API calls (useful for per-environment cost tracking).

## Local development

For tests and ad-hoc local runs, point at the cloud DB through a tunnel:

```bash
# from chatbot-api/
platform tunnel:open --project <project-id> --environment <branch>
# Tunnel exports PLATFORM_RELATIONSHIPS; config_db will pick it up.
```

Or point at a local MySQL by setting `CONFIG_DB_URL` in your `.env`. See
[docs/local-development.md](./local-development.md).
