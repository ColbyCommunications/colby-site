# Runtime RAG agent

All code under [`runtime_rag_knowledge.py`](../runtime_rag_knowledge.py).
This is what actually answers user questions — the validator pre-hooks
(see [docs/input-validation.md](./input-validation.md)) run *before* this
agent, but the answer text comes from here.

## Agent factory

`build_agent()` returns a fresh Agno `Agent` configured with:

- **Model:** `OpenAIChat(id=<model_id>, verbosity="low")`. `model_id`
  resolution order is:
  1. `llm_agents.model_id` row for `agent_key='runtime_rag'` from the
     config DB (preferred — live-editable in the dashboard).
  2. `OPENAI_MODEL` env var (fallback).
  3. Hard-coded `gpt-4.1-mini` as a final safety net.
- **Description + instructions:** loaded from `llm_agents` /
  `agent_instructions` for `runtime_rag`. If the DB is unavailable, the
  built-in fallback in `_default_runtime_description()` /
  `_default_runtime_instructions()` is used and the prompts are prefixed
  with `[RUNTIME_RAG_DEV]` / `DEV_MODE_RUNTIME_RAG_DEV:` so it's obvious in
  the dashboard logs which run used the fallback.
- **Pre-hooks:**
  `colby_query_validation`, `colby_blacklist_validation`, and Agno's
  `PromptInjectionGuardrail`. See [docs/input-validation.md](./input-validation.md).
- **Tools:** `keyword_search` (Algolia) and `vector_search` (Qdrant).
- **Platform metadata:** if `get_openai_metadata_or_none()` returns a dict,
  it's attached to the OpenAI client so requests are tagged per
  Platform.sh environment (useful for OpenAI dashboards).

Template placeholders `{current_date}` and `{standard_rejection_message}`
are substituted into both the description and each instruction line
before the agent is constructed.

## Search tools

### `keyword_search(query, num_results=5)` → Algolia

1. `extract_query_keywords` strips leading question prefixes
   (who/what/when/where/why/how/whos), drops short tokens and stop-words,
   and keeps the first **three** unique keywords.
2. `search_algolia(keywords, max_hits, sources?)` issues a *batched*
   Algolia query — one search request per keyword in a single round-trip —
   and returns at most one hit per keyword. This guarantees keyword
   coverage without flooding the agent with near-duplicates.
3. Source filtering: when `sources=["Libraries", "Admissions"]`, an
   Algolia filter `originIndexLabel:"Libraries" OR originIndexLabel:"Admissions"`
   is applied.
4. Results are formatted into a numbered list with title / URL / content
   that the agent receives as the tool output.

### `search_qdrant_vector(query, max_hits=10, sources?)` → Qdrant

- Embeds the raw query with `text-embedding-3-small` (1536 dims).
- Searches the `colby_knowledge` collection.
- Raises `VectorGraphHealthError` if the collection contains insufficient
  points — this is treated as a critical failure (cron didn't run), and
  bubbles up to a 500 instead of silently degrading to keyword-only.
- The synchronous wrapper used by validator agents handles the "event loop
  already running" case (`_build_event_loop_runner` in
  [`validation_search_context.py`](../validation_search_context.py)).

### `build_agent_query_with_context(message, sources?)`

Wrapper used by `rag_app.ask*` to inject retrieval context (and source
filters) into the message *before* it ever reaches the agent. The output is
plain text the model can read; it is **not** a tool call.

## Vector DB rebuild

The Qdrant collection is rebuilt from scratch every day by the
`update_vectordb` cron (see [docs/crons.md](./crons.md)). The collection
name is `colby_knowledge`; chunking is fixed-size 300 tokens with 150 token
overlap, embedded in batches of 64.

## Stopwords

`_load_stopwords()` prefers NLTK's English stopword list and silently
falls back to a small built-in set if NLTK isn't available. A handful of
project-specific words (`colby`, `college`, all question prefixes) are
always added so they never become Algolia keywords.

## Errors that propagate up

| Error                       | Where it comes from                  | What the API does |
|-----------------------------|--------------------------------------|-------------------|
| `InputCheckError`           | Validator pre-hooks                  | Returns the standard rejection message as a normal 200 |
| `VectorGraphHealthError`    | `search_qdrant_vector` health check  | 500 (`/ask`) or stream-error event (`/ask/stream`) |
| Any other `Exception`       | Agent execution                      | 500 + `query_logs.status='error'` row |
