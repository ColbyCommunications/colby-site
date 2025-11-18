from __future__ import annotations

import os
import sys
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from algoliasearch.search.client import SearchClient

# QDrant for vector search
from qdrant_client import AsyncQdrantClient
import openai

# Modern Agno imports
from agno.agent import Agent
from agno.tools import tool
from agno.models.openai import OpenAIChat

from agno.guardrails import PromptInjectionGuardrail
prompt_injection_guardrail = PromptInjectionGuardrail()
from config_db import load_agent_config
from input_validation_pre_hook import (
    colby_blacklist_validation,
    colby_query_validation,
    get_standard_rejection_message,
)


logger = logging.getLogger(__name__)

def _load_stopwords() -> Set[str]:
    """Load English stopwords using NLTK with fallback."""
    # Static fallback set (previous behavior)
    fallback: Set[str] = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'he', 'in', 'is', 'it',
        'its', 'of', 'on', 'that', 'the', 'to', 'was', 'were', 'will', 'with', 'the', 'this', 'but', 'they',
        'have', 'had', 'what', 'said', 'each', 'which', 'she', 'do', 'how', 'their', 'if', 'up', 'out', 'many',
        'then', 'them', 'these', 'so', 'some', 'her', 'would', 'make', 'like', 'into', 'him', 'time', 'two',
        'more', 'go', 'no', 'way', 'could', 'my', 'than', 'first', 'been', 'call', 'who', 'oil', 'sit', 'now',
        'find', 'down', 'day', 'did', 'get', 'come', 'made', 'may', 'part',
        # Extra question-style and helper words we never want as search keywords
        'who', 'whos', 'whose', 'whom',
        'what', 'whats',
        'when', 'where', 'why', 'how',
    }

    try:
        import nltk  # type: ignore
        from nltk.corpus import stopwords  # type: ignore

        try:
            words = stopwords.words('english')
        except LookupError:
            # Try to download quietly and retry once
            try:
                nltk.download('stopwords', quiet=True)
                words = stopwords.words('english')
            except Exception:
                return fallback

        add_words = [
            "colby",
            "college",
            # Question prefixes and variants that should not be treated as content keywords
            "who",
            "whos",
            "whose",
            "whom",
            "what",
            "whats",
            "when",
            "where",
            "why",
            "how",
        ]
        words.extend(add_words)
        return {w.strip().lower() for w in words if isinstance(w, str)}
    except Exception:
        return fallback

# Initialize stopwords at import time
STOP_WORDS: Set[str] = _load_stopwords()

def filter_stop_words(keywords: List[str]) -> List[str]:
    """Remove stop words and tokens with length <= 2."""
    filtered: List[str] = []
    for word in keywords:
        word_stripped = word.strip()
        if not word_stripped:
            continue
        word_lower = word_stripped.lower()
        if len(word_lower) <= 2:
            continue
        if word_lower in STOP_WORDS:
            continue
        filtered.append(word_stripped)
    return filtered


def _first_present(d: Dict[str, Any], keys: List[str], default: Any = "") -> Any:
    """Return the first non-empty value for any key in keys from dict d."""
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


# Common natural-language prefixes that should not become search keywords
QUESTION_PREFIXES: Set[str] = {
    "who",
    "whos",
    "whose",
    "whom",
    "what",
    "whats",
    "when",
    "where",
    "why",
    "how",
}


def extract_query_keywords(query: str, max_keywords: int = 3) -> List[str]:
    """
    Extract high-signal keywords from a natural language query.

    Two-level filtering:
    1) Strip common question prefixes like 'who/what/when/where/how/whos' from the start
       of the query entirely.
    2) From the remaining text, drop words shorter than 3 characters and apply the
       stop-word filter; then keep only the first `max_keywords` unique tokens.
    """

    def _normalize_token(token: str) -> str:
        # Strip surrounding punctuation and normalize to lowercase for comparison
        return token.strip(" ?!,.:;\"'()[]{}").lower()

    if not query:
        return []

    tokens: List[str] = [t for t in query.strip().split() if t]

    # Level 1: remove leading question prefixes completely
    while tokens and _normalize_token(tokens[0]) in QUESTION_PREFIXES:
        tokens.pop(0)

    if not tokens:
        return []

    # Level 2: drop very short words, then apply stop-word filter
    candidate_words: List[str] = []
    for t in tokens:
        norm = _normalize_token(t)
        if len(norm) < 3:
            continue
        candidate_words.append(norm)

    # Apply stop-word filter as a second layer of cleanup
    cleaned = filter_stop_words(candidate_words)

    # Ensure uniqueness while preserving order
    seen: Set[str] = set()
    keywords: List[str] = []
    for word in cleaned:
        w = word.lower()
        if w in seen:
            continue
        seen.add(w)
        keywords.append(w)

    return keywords[:max_keywords]


async def keyword_search(query: str, num_results: int = 5) -> str:
    """
    This tool only accepts exact keyword matching.
    
    This tool is only useful for specific name and exact phrases.

    Search the Colby College knowledge base using keyword matching.
    
    Args:
        query: The search query with keywords to find (e.g., "financial aid deadlines")
        num_results: Number of results to return (default: 5, max: 10)
    
    Returns:
        Formatted search results with titles, URLs, and content snippets
    """
    # Limit num_results we will actually surface
    num_results = min(num_results, 3)

    # Extract high-signal keywords from the natural language query.
    # This handles question prefixes (who/what/when/where/how/whos) and
    # very short or stop-word tokens in two stages.
    keywords = extract_query_keywords(query, max_keywords=3)
    
    if not keywords:
        return "No valid keywords found in query. Please provide meaningful search terms."
    
    # Run keyword search (now directly awaitable)
    search_results = await search_algolia(keywords, num_results)
    
    if not search_results:
        return "No results found for the given keywords. Try different or broader search terms."
    
    # Format results for the agent
    formatted_output = f"Found {len(search_results)} keyword search results:\n\n"
    
    for i, hit in enumerate(search_results, 1):
        title = _first_present(hit, ["post_title", "title"], "Untitled")
        url = _first_present(hit, ["permalink", "url"], "No URL")
        content = hit.get("content") or hit.get("body") or hit.get("excerpt", "")

        formatted_output += f"{i}. **{title}**\n"
        formatted_output += f"   URL: {url}\n"
        formatted_output += f"   Content: {content}\n\n"
    
    return formatted_output

async def search_algolia(keywords: List[str], max_hits: int = 5) -> List[Dict[str, Any]]:
    """Search Algolia with individual keywords using batched search.

    Requirements:
    - Use only the first 3 cleaned keywords.
    - Aim for at least one result per keyword (subject to index coverage).
    - Respect the overall `max_hits` cap.
    """
    app_id = os.environ["ALGOLIA_APP_ID"]
    api_key = os.environ["ALGOLIA_API_KEY"]
    index_name = os.environ.get("ALGOLIA_INDEX_NAME", "prod_colbyedu_aggregated")

    # Second-level cleanup on provided keywords
    filtered_keywords = filter_stop_words(keywords)

    if not filtered_keywords:
        return []

    # Cap to the first 3 keywords and ensure we never exceed max_hits
    max_keywords = min(len(filtered_keywords), max_hits, 3)
    filtered_keywords = filtered_keywords[:max_keywords]

    if not filtered_keywords:
        return []

    # Create a single batched search request for all keywords, requesting
    # just enough hits to guarantee at least one candidate per keyword.
    per_keyword_limit = 1
    final_results: List[Dict[str, Any]] = []

    async with SearchClient(app_id, api_key) as client:
        try:
            resp = await client.search({
                "requests": [
                    {
                        "indexName": index_name,
                        "query": keyword,
                        "hitsPerPage": per_keyword_limit,
                        "attributesToRetrieve": [
                            "objectID",
                            "post_title",
                            "content",
                            "excerpt",
                            "permalink",
                            "originIndexLabel",
                            "title",
                            "body",
                            "url"
                        ],
                    }
                    for keyword in filtered_keywords
                ]
            })

            try:
                data = resp.model_dump()
            except AttributeError:
                data = resp.dict()

            results = data.get("results", [])

            # Align each result set with its originating keyword and
            # take at most one hit per keyword.
            for keyword, result in zip(filtered_keywords, results):
                hits = result.get("hits", [])
                if not hits:
                    continue
                hit = hits[0]
                hit["_search_keyword"] = keyword
                final_results.append(hit)
        except Exception as e:
            print(f"Error during batched search: {e}")

    # At this point we have at most one result per keyword, already respecting `max_hits`.
    return final_results[:max_hits]


async def search_qdrant_vector(query: str, max_hits: int = 10) -> List[Dict[str, Any]]:
    """
    This tool uses semantic/vector similarity search to find relevant information.
    
    This tool is useful for conceptual queries, general questions, and natural language search.
    Use this when you need to find information based on meaning rather than exact keywords.

    Search the Colby College knowledge base using AI-powered semantic search.
    
    Args:
        query: Natural language query to search for (e.g., "What are the dining options on campus?")
        max_hits: Maximum number of results to return (default: 10)
    
    Returns:
        List of relevant documents with titles, URLs, content, and similarity scores
    """
    # Get Qdrant configuration from environment
    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY")
    collection_name = os.environ.get("QDRANT_COLLECTION_NAME", "colby_knowledge")
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    embedding_model = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
    
    if not all([qdrant_url, qdrant_api_key, openai_api_key]):
        print("⚠️ Qdrant or OpenAI credentials missing, skipping vector search")
        return []
    
    # print(f"🔢 Vector Search: Generating embedding with {embedding_model}...")
    
    openai_client = None
    qdrant_client = None
    
    try:
        # Generate query embedding using context manager
        async with openai.AsyncOpenAI(api_key=openai_api_key) as openai_client:
            response = await openai_client.embeddings.create(
                model=embedding_model,
                input=query
            )
            query_vector = response.data[0].embedding
        
        # Search Qdrant using query points API
        qdrant_client = AsyncQdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
            timeout=30
        )
        
        try:
            # Perform vector search using query points
            # print(f"🔍 Vector Search: Querying Qdrant collection '{collection_name}' (limit={max_hits})...")
            search_result = await qdrant_client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=max_hits,
                with_payload=True,
            )
            
            # print(f"✅ Vector Search: Found {len(search_result.points)} results")
            
            # Format results to match Algolia structure
            formatted_results = []
            for point in search_result.points:
                payload = point.payload
                url = payload.get("url", "")
                
                # Calculate URL depth penalty: decrease score by 0.1 for each '/'
                # This prioritizes URLs closer to the main domain
                url_depth_penalty = url.count('/') * 0.1
                adjusted_score = point.score - url_depth_penalty
                
                # Score boosting URLs:
                score_boosting_urls = {
                    "life.colby.edu": 0.3,
                    "afa.colby.edu": 0.3,
                    "news.colby.edu": -0.3,
                    "alumni.colby.edu": 0.1,
                }

                # If the above strings are in the URL, add the score boost
                url_match_boost_score = 0
                for key, value in score_boosting_urls.items():
                    if key in url:
                        adjusted_score += value
                        url_match_boost_score += value

                # If a URL does not have colby.edu:
                if "colby.edu" not in url:
                    adjusted_score -= 1.0

                formatted_results.append({
                    "objectID": payload.get("objectID", ""),
                    "post_title": payload.get("title", ""),
                    "title": payload.get("title", ""),
                    "content": payload.get("content", ""),
                    "permalink": url,
                    "url": url,
                    "originIndexLabel": payload.get("source", "Vector Search"),
                    "_score": adjusted_score,
                    "_original_score": point.score,
                    "_url_depth_penalty": url_depth_penalty,
                    "_url_match_boost_score": url_match_boost_score,
                    "_search_type": "vector",
                    "chunk_index": payload.get("chunk_index", 0),
                    "total_chunks": payload.get("total_chunks", 1),
                })
            
            # Sort results by adjusted score (highest first) to prioritize main domain pages
            formatted_results.sort(key=lambda x: x["_score"], reverse=True)

            # Debug: Dump formatted vector search results to a JSON file
            # import json
            # with open("formatted_results.json", "w") as f:
            #     json.dump(formatted_results, f, indent=4)

            return formatted_results
        finally:
            # Ensure Qdrant client is properly closed
            if qdrant_client:
                try:
                    await qdrant_client.close()
                except Exception:
                    pass  # Ignore errors during cleanup
        
    except Exception as e:
        print(f"Error during Qdrant vector search: {str(e)}")
        return []


def retriever(
    query: str, 
    agent: Optional[Agent] = None, 
    num_documents: int = 10, 
    **kwargs
) -> Optional[list[dict]]:
    """
    Custom retriever function to search the vector database for relevant documents.
    
    Performs semantic vector search using embeddings. For exact keyword matching,
    the agent can use the keyword_search tool instead.
    
    Note: This is a synchronous wrapper around the async search_qdrant_vector function
    because the Agno Agent framework expects a synchronous knowledge_retriever.
    """
    try:
        if num_documents is None:
            num_documents = 10
        
        # Run async search in sync context
        try:
            # Check if we're already in an event loop
            loop = asyncio.get_running_loop()
            # We're in an async context, need to run in a thread with a new loop
            import concurrent.futures
            
            def run_in_new_loop():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(search_qdrant_vector(query, num_documents))
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_new_loop)
                search_results = future.result(timeout=30)
        except RuntimeError:
            # No event loop running, safe to use asyncio.run
            search_results = asyncio.run(search_qdrant_vector(query, num_documents))
        
        if not search_results:
            print("⚠️  No vector results found")
            return []
        
        for i, doc in enumerate(search_results[:5], 1):
            title = doc.get("title", doc.get("post_title", "Untitled"))[:60]
            url = doc.get("url", doc.get("permalink", "No URL"))[:70]
            score = doc.get("_score", 0)
        
        # Format results for the agent
        formatted_results = []
        for hit in search_results[:num_documents]:
            content = hit.get("content") or hit.get("body") or hit.get("excerpt", "")
            title = _first_present(hit, ["post_title", "title"], "Colby College Resource")
            url = _first_present(hit, ["permalink", "url"], "")
            
            # Embed URL at start and end for maximum LLM visibility
            if url:
                content_with_source = f"[SOURCE: {title} - {url}]\n\n{content}\n\n[SOURCE: {title} - {url}]"
            else:
                content_with_source = content
            
            doc = {
                "content": content_with_source,
                "title": title,
                "url": url,
                "source": _first_present(hit, ["originIndexLabel", "origin_index_label"], "Vector Search"),
                "id": _first_present(hit, ["objectID", "objectId", "object_id", "permalink", "url"], ""),
            }
            formatted_results.append(doc)
        
        return formatted_results
        
    except Exception as e:
        print(f"Error during vector search: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def build_agent_query_with_context(user_message: str) -> str:
    """
    Build the final input string for the runtime RAG agent by attaching the
    same search context (keyword + vector) that we compute for validation.

    This keeps the validator and runtime agent grounded in the exact same
    Algolia and Qdrant results for a given query.
    """
    try:
        # Lazy import to avoid circular dependency at module import time
        from validation_search_context import build_search_context_for_query

        context = build_search_context_for_query(user_message)

        # Helpful log so we can see how much context is being passed into the
        # runtime agent in both local dev and production.
        keyword_results = len(
            (context.get("keyword_search") or {}).get("results", [])
        )
        vector_results = len(
            (context.get("vector_search") or {}).get("results", [])
        )
        logger.info(
            "[RUNTIME_RAG][CONTEXT] Built search context for query (keyword_results=%d, "
            "vector_results=%d).",
            keyword_results,
            vector_results,
        )
    except Exception as e:  # noqa: BLE001
        context = {
            "user_query": user_message,
            "error": f"search_context_error: {str(e)}",
        }
        logger.warning(
            "[RUNTIME_RAG][CONTEXT][DEV] Failed to build search context for query: %s",
            e,
        )

    context_json = json.dumps(context, ensure_ascii=False)

    return (
        "You are a Colby College knowledge base assistant. "
        "You are given both the user's question and a precomputed SEARCH_CONTEXT_JSON "
        "containing keyword and vector search hits from the official Colby knowledge base. "
        "ONLY answer using information that can be grounded in this search context. "
        "If the context does not contain relevant Colby information, respond with the "
        "standard rejection message.\n\n"
        f"SEARCH_CONTEXT_JSON:\n{context_json}\n\n"
        "USER_QUESTION:\n"
        f"{user_message}"
    )


def _default_runtime_description(formatted_date: str, rejection_message: str) -> str:
    """
    Built-in description for the main runtime RAG agent.

    `formatted_date` should be an EST time string like "1:13am, Oct 21, 2025".
    """

    return (
        "You are a Colby College knowledge base assistant. "
        f"Today's date is {formatted_date} (EST). You must use this date to answer questions about deadlines, events, and other time-sensitive information."
        "You can ONLY provide information from the knowledge base. "
        "If information is not in the knowledge base, say the standard rejection message."
        f"Standard rejection message: '{rejection_message}'"
        "Do not provide an answer if you cannot cite a URL for each fact in your response from the knowledge base."
    )


def _default_runtime_instructions() -> list[str]:
    """
    Built-in instructions for the runtime RAG agent.

    These are templates that may contain the following placeholders:
      {current_date}               - human-readable EST date string
      {standard_rejection_message} - current standard rejection message
    """

    return [
        "ONLY answer using information from retrieved documents.",
        "CRITICAL: NEVER display raw URLs. ALL links MUST use markdown format: [descriptive text](URL)",
        "The descriptive text should be meaningful - use page titles, section names, or relevant keywords.",
        "When citing specific facts or quotes, create Text Fragment links to highlight the exact text on the source page.",
        "Text Fragment link format: Add '#:~:text=' followed by the URL-encoded text snippet to the end of URLs.",
        "CRITICAL TEXT FRAGMENT RULES:",
        "  1. Keep fragments SHORT (2-6 words maximum) - long fragments break markdown links",
        "  2. ONLY use CONTINUOUS text - NO line breaks, bullets, numbered lists, or multi-line text",
        "  3. If text spans multiple lines or is part of a list, use ONLY the first line or a heading instead",
        "  4. URL-encode ALL special characters in the fragment text:",
        "     - Spaces: %20",
        "     - Hyphens: %2D (CRITICAL - unencoded hyphens break text fragments!)",
        "     - Colons: %3A",
        "     - Commas: %2C",
        "     - Parentheses: %28 and %29",
        "  5. Use simple, unique phrases from the retrieved content",
        "  6. Prefer section headings or short key phrases over long sentences",
        "Avoid using phone numbers, email addresses, or other text that's likely a hyperlink on the page.",
        "Avoid text from bulleted lists, numbered lists, or multi-paragraph content.",
        "Instead, use the SURROUNDING CONTEXT TEXT (like headings or introductory sentences) to create the fragment.",
        "Examples of GOOD link formatting:",
        "  - [dining halls](https://example.com/page#:~:text=on%2Dcampus%20dining%20halls) (hyphen encoded as %2D)",
        "  - [financial aid deadlines](https://example.com/page#:~:text=application%20deadline)",
        "  - [campus safety contacts](https://example.com/page#:~:text=Non%2Demergency%20phone) (hyphen encoded)",
        "Examples of BAD formatting:",
        "  - Hyphen not encoded: #:~:text=on-campus (WRONG - must be on%2Dcampus)",
        "  - Fragment too long: #:~:text=To%20schedule%20call%20at%20207%2D859%2D4490 (WAY too long)",
        "  - Multi-line text: #:~:text=first%20line%0Asecond%20line (contains line break - will FAIL)",
        "  - Bulleted list item: #:~:text=•%20First%20item (list formatting - will FAIL)",
        "  - Naked URL: https://example.com/page#:~:text=... (NEVER do this)",
        "When in doubt, use a SHORT 2-4 word phrase or just link without text fragment: [title](https://example.com/page)",
        "Standard rejection message: '{standard_rejection_message}'",
    ]


def build_agent() -> Any:
    """Build and configure the RAG agent with environment- and DB-based settings."""

    # Get current date/time in EST timezone
    est_tz = ZoneInfo("America/New_York")
    current_time = datetime.now(est_tz)
    formatted_date = current_time.strftime("%I:%M%p, %b %d, %Y").lower().replace(" 0", " ")
    # Result format: "1:13am, Oct 21, 2025"

    rejection_message = get_standard_rejection_message()

    # Defaults from environment / code.
    default_model_id = os.environ.get("OPENAI_MODEL")
    description = _default_runtime_description(formatted_date, rejection_message)
    instructions = _default_runtime_instructions()
    model_id = default_model_id
    name = "Colby RAG Assistant"
    using_db_config = False

    # Optionally override from the config DB.
    try:
        agent_cfg = load_agent_config("runtime_rag")
    except Exception:
        agent_cfg = None

    if agent_cfg:
        using_db_config = True
        if agent_cfg.model_id:
            model_id = agent_cfg.model_id
        if agent_cfg.description_template:
            try:
                description = agent_cfg.description_template.format(
                    current_date=formatted_date,
                    standard_rejection_message=rejection_message,
                )
            except Exception:
                # If formatting fails for any reason, fall back to default description.
                description = _default_runtime_description(
                    formatted_date,
                    rejection_message,
                )
        if agent_cfg.instructions:
            instructions = agent_cfg.instructions
        if agent_cfg.name:
            name = agent_cfg.name

    # Log which source of truth we're using for the runtime agent.
    if using_db_config:
        logger.info(
            "[RUNTIME_RAG][DB] Using config DB settings for agent 'runtime_rag' "
            "(model_id=%r, name=%r).",
            model_id,
            name,
        )
    else:
        logger.warning(
            "[RUNTIME_RAG][DEV] Configuration DB unavailable or missing agent "
            "'runtime_rag'; using built-in fallback prompts and model_id=%r.",
            model_id,
        )

    # If we did NOT successfully load configuration from the DB, mark prompts as DEV
    # so it's also visible inside the prompt text itself.
    if not using_db_config:
        description = (
            "[RUNTIME_RAG_DEV] Using built-in fallback description because the "
            "configuration database is unavailable or missing the 'runtime_rag' agent. "
            + description
        )
        instructions = [
            "DEV_MODE_RUNTIME_RAG_DEV: Using local fallback instructions because the "
            "configuration database is unavailable or missing the 'runtime_rag' agent.",
            *instructions,
        ]
        logger.info(
            "[DEV] runtime_rag using built-in fallback config: model_id=%s, "
            "instructions=%d, name=%s",
            model_id,
            len(instructions or []),
            name,
        )
    else:
        logger.info(
            "[DB] runtime_rag loaded from config DB: model_id=%s, "
            "instructions=%d, name=%s, description_template=%s",
            model_id,
            len(instructions or []),
            name,
            bool(agent_cfg and agent_cfg.description_template),
        )

    # Final safety fallback for model_id.
    if not model_id:
        model_id = "gpt-4.1-mini"

    # Format instructions with templates, allowing both the built-in defaults and
    # DB-provided instructions to use placeholders.
    placeholders = {
        "current_date": formatted_date,
        "standard_rejection_message": rejection_message,
    }
    formatted_instructions: list[str] = []
    for line in instructions or []:
        try:
            formatted_instructions.append(str(line).format(**placeholders))
        except Exception:
            # On any formatting issue, fall back to the raw line.
            formatted_instructions.append(str(line))

    base_kwargs = dict(
        model=OpenAIChat(id=model_id),
        description=description,
        markdown=True,
        pre_hooks=[prompt_injection_guardrail, colby_blacklist_validation, colby_query_validation],
        name=name,
    )

    advanced_kwargs = dict(
        instructions=formatted_instructions,
    )

    try:
        agent = Agent(**{**base_kwargs, **advanced_kwargs})
    except TypeError:
        # Older versions of agno.Agent may not accept `name` or `instructions` as kwargs.
        agent = Agent(**{k: v for k, v in base_kwargs.items() if k != "name"})

    # Attach lightweight metadata so the API layer can log which configuration
    # source and model powered this runtime agent.
    try:
        agent._colby_agent_config = {  # type: ignore[attr-defined]
            "agent_key": "runtime_rag",
            "model_id": model_id,
            "using_db_config": using_db_config,
            "name": name,
        }
    except Exception:
        # Never let logging metadata break agent construction.
        pass

    return agent


async def run_agent_with_message(user_message: str):
    """Run agent with a message - used for performance evaluation."""
    agent = build_agent()
    try:
        enhanced_input = build_agent_query_with_context(user_message)
        response = await agent.arun(enhanced_input)
        return response
    except Exception as e:
        print(f"Agent execution error: {e}")
        raise


async def main():
    load_dotenv()
    csv_path = os.environ.get("CSV_PATH", ".csv")
    import pandas as pd

    if not csv_path or not os.path.exists(csv_path):
        # Fallback to interactive mode if CSV not found
        user_message = input("Enter your question or command: ").strip()
        if not user_message:
            print("No input provided.")
            sys.exit(1)
        agent = build_agent()
        try:
            await agent.aprint_response(user_message, stream=True)
        except TypeError:
            await agent.aprint_response(user_message, stream=True)
        except Exception as e:
            print(f"Agent execution error: {e}")
            sys.exit(1)
        return

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Failed to read CSV: {e}")
        sys.exit(1)

    if "nl_queries" not in df.columns:
        print("CSV is missing required 'nl_queries' column.")
        sys.exit(1)

    agent = build_agent()

    # Ensure output column exists
    if "vector_results" not in df.columns:
        df["vector_results"] = ""

    from tqdm import tqdm
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Processing rows"):
        user_message = str(row.get("nl_queries", "")).strip()
        if not user_message:
            df.at[idx, "vector_results"] = ""
            try:
                df.to_csv(csv_path, index=False)
            except Exception as e:
                print(f"Failed to write CSV at row {idx}: {e}")
            continue
        try:
            resp = await agent.arun(user_message)
            if resp is None:
                text = ""
            elif hasattr(resp, "content"):
                text = str(resp.content)
            else:
                text = str(resp)
        except Exception as e:
            text = f"ERROR: {e}"

        # Save result for this row and write CSV immediately
        df.at[idx, "vector_results"] = text
        try:
            df.to_csv(csv_path, index=False)
        except Exception as e:
            print(f"Failed to write CSV at row {idx}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
