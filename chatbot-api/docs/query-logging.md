# Query logging

Per-request logging into MySQL, used by the **Responses** dashboard and
the daily analytics email.

Module: [`query_logging.py`](../query_logging.py).

## What gets recorded

Every `/ask*` request creates one row in `query_logs` and zero-or-more
rows in `query_log_parts`:

```
query_logs (1) ────────► query_log_parts (N)
  id                       id
  created_at               query_log_id (FK)
  user_message             created_at
  final_answer             stage          ← 'validation_primary', 'validation_blacklist', 'runtime_rag', ...
  status                   model_id       ← the *actual* model that ran for this stage
  blocked_by               agent_name
  error_message            using_db_config
                           blocked
                           result_json    ← stage-specific blob (see below)
```

Statuses:
- `pending` — set on `start_request_log`.
- `answered` — set on `finalize_request_log` for a successful answer.
- `blocked` — validator rejection.
- `error` — uncaught exception in the agent path.

## API

- `start_request_log(user_message)` → inserts a `pending` row, stores the
  new id in a `ContextVar`.
- `add_log_part(stage, model_id, agent_name, using_db_config, result,
  blocked)` → inserts a `query_log_parts` row tied to the current request.
- `mark_blocked_by(stage)` → records *which* stage rejected the query.
  Read by `finalize_request_log` and persisted to `query_logs.blocked_by`.
- `finalize_request_log(status, final_answer, error_message)` → updates
  the parent row. Picks up `blocked_by` from the ContextVar.
- `clear_request_log_context()` → resets both ContextVars (always called
  in a `finally` block).

## Why ContextVar?

FastAPI handles requests on a single thread but with multiple concurrent
asyncio tasks. ContextVar gives per-request isolation: the validator
pre-hooks can call `mark_blocked_by` and `add_log_part` without having to
thread the parent log id through the agent's call signatures.

## When the DB is down

Every helper guards `get_db_connection() is None` and silently no-ops.
That keeps a transient `configdb` outage from breaking user-facing
`/ask` traffic — answers still flow, only the logs miss the failure
window. The downside is silent: there is no separate error trail. The
expected signal is dashboard rows simply disappearing for the affected
window.

## What `result_json` contains, by stage

| Stage                    | `result_json` keys                                  |
|--------------------------|-----------------------------------------------------|
| `validation_primary`     | Validator decision dict (reasoning, is_legitimate)  |
| `validation_blacklist`   | Same shape, blacklist-only                          |
| `runtime_rag`            | `{"content": "<full assistant answer>"}`            |

These shapes are also surfaced through `QueryLogPartDTO` in
[`admin_api.py`](../admin_api.py).

## Consumers

- **Admin dashboard** — `/admin/query-logs*` routes
  (see [docs/admin-api.md](./admin-api.md)).
- **Daily analytics email** — see [docs/crons.md](./crons.md).
- **Metrics** — `GET /admin/metrics/weekly` aggregates these tables.
