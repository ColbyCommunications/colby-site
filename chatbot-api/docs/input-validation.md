# Input validation

Two LLM-backed validators and one structural guardrail run **before** the
runtime agent ever gets the user's message. All of them are registered as
Agno pre-hooks inside
[`runtime_rag_knowledge.build_agent`](../runtime_rag_knowledge.py).

| Pre-hook                             | Agent key              | Purpose |
|--------------------------------------|------------------------|---------|
| `PromptInjectionGuardrail()` (Agno)  | —                      | Static guard against common prompt-injection patterns |
| `colby_query_validation`             | `validation_primary`   | Is this a legitimate Colby College question? |
| `colby_blacklist_validation`         | `validation_blacklist` | Does this match any blacklisted training example? |

A failure raises `agno.exceptions.InputCheckError`, which the
`/ask` handlers catch and convert into a normal 200 response containing
the **standard rejection message**.

## File map

- [`input_validation_pre_hook.py`](../input_validation_pre_hook.py) —
  pre-hook factories and the `get_standard_rejection_message()` resolver.
- [`validation_search_context.py`](../validation_search_context.py) —
  builds the JSON payload (Algolia + Qdrant snippets) the primary
  validator reads when deciding "is this a Colby question?".

## Standard rejection message

`get_standard_rejection_message()` reads `app_messages.standard_rejection_message`
from the config DB at every call. If the DB is unavailable, it returns:

> This question falls outside of my knowledge of Colby College information.
> Please re-ask your question within a Colby context.

Validators format their description templates with `{standard_rejection_message}`
so changing the value in the dashboard updates every validator prompt on
the next request.

## `colby_query_validation` (primary)

- **Model + prompts:** loaded from `llm_agents` row `validation_primary`,
  with `{current_date}` / `{standard_rejection_message}` substitution.
- **Few-shot examples:** loaded from `query_examples` (`whitelist` and
  `blacklist` rows) and embedded in the description.
- **Search context:** for every user message, `build_validation_payload`
  runs `extract_query_keywords` + Algolia + Qdrant searches in a worker
  thread (works inside FastAPI's running event loop) and passes the
  compact JSON result to the validator. The validator can therefore see
  whether *retrieval would even find anything* before approving the
  query — which catches "Who is Taylor Swift?" type questions that
  *look* Colby-shaped but have no supporting content.

If the validator marks `is_legitimate_colby_query=false`, it raises
`InputCheckError` and `mark_blocked_by("validation_primary")` is recorded.

## `colby_blacklist_validation`

- **Model + prompts:** loaded from `llm_agents` row `validation_blacklist`.
- **Few-shot examples:** blacklist examples from `query_examples`.
- Does not run Algolia/Qdrant — this is a cheap pattern matcher whose
  whole job is to block obvious repeats of previously bad queries
  (e.g. coordinated abuse).

## Why two validators?

They are independently tunable. The primary validator is the "smart"
context-aware judge; the blacklist validator is a fast escape hatch the
admins can promote any flagged query into without writing prompt edits.
Each runs as its own log part so the dashboard shows exactly which one
fired.

## Flow

```
                user message
                     │
                     ▼
        PromptInjectionGuardrail (Agno)
                     │
                     ▼
        colby_blacklist_validation
                     │  (passes)
                     ▼
        colby_query_validation
                     │  (passes)
                     ▼
                runtime agent
```

A rejection from any of these → `InputCheckError` → 200 OK with the
standard rejection message. The query log is finalized as
`status="blocked"` with the blocking stage in `blocked_by`.

## Where the whitelist comes in

The whitelist is *not* a bypass for the validators — the validators always
run. Whitelisted examples are fed as positive few-shot data so the primary
validator learns to recognize the *class* of questions admins have
explicitly approved. Promotion happens via the admin API
(`POST /admin/query-logs/{log_id}/whitelist`); see
[docs/admin-api.md](./admin-api.md).
