# Admin API

Everything mounted under [`/admin/*`](../admin_api.py). All endpoints are
gated by the `require_admin` dependency, which redirects unauthenticated
requests to the Okta login flow when `ADMIN_OKTA_ENABLED=true`. See
[docs/okta-auth.md](./okta-auth.md) for the auth wiring.

## Router

```python
admin_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)
```

All routes below are relative to `/admin`, and in production they're
further prefixed by `/chatbot-api` from the Platform.sh router.

## Exempt paths

`require_admin` lets these through without an Okta session so the OIDC
flow can bootstrap:

- `/admin/` (landing — renders its own login preview)
- `/admin/login`
- `/admin/authorization-code/callback`
- `/admin/logout`
- `/admin/responses` and `/admin/dashboard` (the HTML pages render their
  own logged-out preview)
- Anything under `/admin/static/`

## Authentication routes

| Method | Path                                  | Purpose |
|--------|---------------------------------------|---------|
| GET    | `/admin/login`                        | Builds Okta authorize URL + PKCE, redirects |
| GET    | `/admin/authorization-code/callback`  | Exchanges code, stores `okta_user` in session |
| GET    | `/admin/logout`                       | Clears session, redirects to Okta logout |

See [docs/okta-auth.md](./okta-auth.md).

## Config CRUD

These power the **Dashboard → Configuration** screen.

### LLM models (`llm_models` table)

| Method | Path                          | Body / params       | Returns |
|--------|-------------------------------|---------------------|---------|
| GET    | `/admin/models`               | —                   | `List[LlmModelDTO]` |
| POST   | `/admin/models`               | `LlmModelDTO`       | `LlmModelDTO` (201) |
| PUT    | `/admin/models/{model_id}`    | `LlmModelDTO`       | `LlmModelDTO` |
| DELETE | `/admin/models/{model_id}`    | —                   | 204 |
| POST   | `/admin/validate-model`       | `{model_id}`        | `ValidateModelResponse` — calls OpenAI to confirm the id is callable |

### Agents (`llm_agents` + `agent_instructions`)

| Method | Path                          | Returns |
|--------|-------------------------------|---------|
| GET    | `/admin/agents`               | `List[AgentDTO]` (with ordered instructions) |
| GET    | `/admin/agents/{agent_key}`   | `AgentDTO` |
| POST   | `/admin/agents`               | `AgentDTO` (201) |
| PUT    | `/admin/agents/{agent_key}`   | `AgentDTO` — replaces instructions atomically |
| DELETE | `/admin/agents/{agent_key}`   | 204 |

The recognized `agent_key` values are `runtime_rag`, `validation_primary`,
and `validation_blacklist`.

### App messages (`app_messages` table)

Currently used for `standard_rejection_message`.

| Method | Path                                  | Returns |
|--------|---------------------------------------|---------|
| GET    | `/admin/messages`                     | `List[AppMessageDTO]` |
| GET    | `/admin/messages/{message_key}`       | `AppMessageDTO` |
| PUT    | `/admin/messages/{message_key}`       | `AppMessageDTO` |

## Query logs

These power the **Dashboard → Responses** screen.

| Method | Path                                              | Returns |
|--------|---------------------------------------------------|---------|
| GET    | `/admin/query-logs`                               | `List[QueryLogDTO]` (filters: `status`, `start_date`, `end_date`, `q`, `limit`) |
| GET    | `/admin/query-logs/{log_id}`                      | `QueryLogDTO` with all per-stage parts |
| GET    | `/admin/query-logs/export/csv`                    | CSV download (same filters as list) |
| POST   | `/admin/query-logs/{log_id}/blacklist`            | Promote to a blacklist training example |
| DELETE | `/admin/query-logs/{log_id}/blacklist`            | Remove from blacklist examples |
| POST   | `/admin/query-logs/{log_id}/whitelist`            | Promote to a whitelist training example |
| DELETE | `/admin/query-logs/{log_id}/whitelist`            | Remove from whitelist examples |

The schema (and what each per-stage `result_json` contains) is documented
in [docs/query-logging.md](./query-logging.md).

## Metrics

| Method | Path                          | Returns |
|--------|-------------------------------|---------|
| GET    | `/admin/metrics/weekly`       | `WeeklyMetricsDTO` — 7-day rolling counts (ET) split by status & blocker |

## Training examples (`query_examples` table)

Used by both validators as few-shot examples.

| Method | Path                          | Returns |
|--------|-------------------------------|---------|
| GET    | `/admin/training-examples`    | `TrainingExamplesDTO` (whitelist + blacklist lists) |
| PUT    | `/admin/training-examples`    | Replace the lists wholesale |

## Static assets + dashboard HTML

Served directly out of `admin_ui/`:

| Path                              | Source                               |
|-----------------------------------|--------------------------------------|
| `/admin/static/dashboard.css`     | `admin_ui/dashboard.css`             |
| `/admin/static/dashboard.js`      | `admin_ui/dashboard.js`              |
| `/admin/static/responses.js`      | `admin_ui/responses.js`              |
| `/admin/static/home.js`           | `admin_ui/home.js`                   |
| `/admin/` (HTML)                  | `admin_ui/home.html`                 |
| `/admin/dashboard` (HTML)         | `admin_ui/index.html`                |
| `/admin/responses` (HTML)         | `admin_ui/responses.html`            |

See [docs/admin-ui.md](./admin-ui.md).

## DTOs

All Pydantic models (`LlmModelDTO`, `AgentDTO`, `AgentInstructionDTO`,
`AppMessageDTO`, `QueryLogDTO`, `QueryLogPartDTO`, `WeeklyMetricsDTO`,
`TrainingExamplesDTO`, …) live at the top of
[`admin_api.py`](../admin_api.py). They map 1-to-1 to the MySQL tables in
[docs/config-db.md](./config-db.md).
