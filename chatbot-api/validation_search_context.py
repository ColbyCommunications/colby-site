import asyncio
import json
from typing import Any, Dict, List, Tuple


def _build_event_loop_runner():
    """
    Create a helper that can run async callables from a sync context,
    even when there's already a running event loop (e.g. inside FastAPI).
    """
    import concurrent.futures

    def run(coro):
        try:
            # If there's an active event loop (arun/async context), run in a worker thread.
            asyncio.get_running_loop()

            def _run_in_new_loop():
                new_loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(new_loop)
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_run_in_new_loop)
                return future.result(timeout=30)
        except RuntimeError:
            # No running event loop – safe to use asyncio.run
            return asyncio.run(coro)

    return run


def build_search_context_for_query(user_query: str) -> Dict[str, Any]:
    """
    Build a compact, structured summary of keyword and RAG/vector search
    results for the given user query.

    This is designed specifically for input validation – it should be:
    - Lightweight (limited number of results, truncated snippets)
    - Resilient (never raise if search infra is unavailable)
    - JSON-serializable
    """
    from runtime_rag_knowledge import (  # imported lazily to avoid circular import at module load
        extract_query_keywords,
        search_algolia,
        search_qdrant_vector,
        _first_present,
    )

    run_sync = _build_event_loop_runner()

    async def _gather() -> Tuple[Dict[str, Any], Dict[str, Any]]:
        # ----- Keyword / Algolia search -----
        keyword_context: Dict[str, Any] = {
            "keywords_used": [],
            "num_results": 0,
            "results": [],
            "error": None,
        }

        # Reuse the same keyword-extraction logic as the main runtime agent.
        try:
            keywords = extract_query_keywords(user_query, max_keywords=3)
        except Exception:
            keywords = []

        keyword_context["keywords_used"] = keywords

        try:
            if keywords:
                algolia_hits = await search_algolia(keywords, max_hits=3)
            else:
                algolia_hits = []
        except Exception as e:  # noqa: BLE001
            algolia_hits = []
            keyword_context["error"] = f"algolia_error: {str(e)}"

        # Compact, high-signal view of Algolia results
        for hit in algolia_hits[:3]:
            title = _first_present(hit, ["post_title", "title"], "Untitled")
            url = _first_present(hit, ["permalink", "url"], "")
            content = hit.get("content") or hit.get("body") or hit.get("excerpt") or ""
            keyword_context["results"].append(
                {
                    "title": title,
                    "url": url,
                    "source": hit.get("originIndexLabel") or hit.get("origin_index_label") or "Algolia",
                    "content": content,
                    "search_keyword": hit.get("_search_keyword"),
                }
            )

        keyword_context["num_results"] = len(keyword_context["results"])

        # ----- Vector / Qdrant search -----
        vector_context: Dict[str, Any] = {
            "num_results": 0,
            "results": [],
            "error": None,
        }

        try:
            vector_hits = await search_qdrant_vector(user_query, max_hits=5)
        except Exception as e:  # noqa: BLE001
            vector_hits = []
            vector_context["error"] = f"vector_error: {str(e)}"

        for hit in vector_hits[:5]:
            title = _first_present(hit, ["post_title", "title"], "Colby College Resource")
            url = _first_present(hit, ["permalink", "url"], "")
            content = hit.get("content") or hit.get("body") or hit.get("excerpt") or ""
            vector_context["results"].append(
                {
                    "title": title,
                    "url": url,
                    "source": hit.get("originIndexLabel") or hit.get("origin_index_label") or "Vector Search",
                    "content": content,
                    "score": hit.get("_score"),
                    "search_type": hit.get("_search_type", "vector"),
                }
            )

        vector_context["num_results"] = len(vector_context["results"])

        return keyword_context, vector_context

    try:
        keyword_ctx, vector_ctx = run_sync(_gather())
    except Exception as e:  # noqa: BLE001
        # On any unexpected failure, fall back to a minimal payload rather than breaking validation.
        return {
            "user_query": user_query,
            "error": f"search_context_error: {str(e)}",
        }

    return {
        "user_query": user_query,
        "keyword_search": keyword_ctx,
        "vector_search": vector_ctx,
    }


def build_validation_payload(user_query: str) -> str:
    """
    Build a JSON string that the validation model can consume.

    The payload contains:
    - user_query: original text
    - keyword_search: compact Algolia-based view
    - vector_search: compact Qdrant-based view
    """
    context = build_search_context_for_query(user_query)
    payload = {
        "task": "decide_if_legitimate_colby_college_query",
        "user_query": user_query,
        "search_context": context,
    }
    # Return as JSON string so we can embed in a natural language prompt.
    return json.dumps(payload, ensure_ascii=False)


