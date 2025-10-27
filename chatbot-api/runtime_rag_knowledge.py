from __future__ import annotations

import os
import sys
import asyncio
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
from input_validation_pre_hook import colby_query_validation

def _load_stopwords() -> Set[str]:
    """Load English stopwords using NLTK with fallback."""
    # Static fallback set (previous behavior)
    fallback: Set[str] = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'he', 'in', 'is', 'it',
        'its', 'of', 'on', 'that', 'the', 'to', 'was', 'were', 'will', 'with', 'the', 'this', 'but', 'they',
        'have', 'had', 'what', 'said', 'each', 'which', 'she', 'do', 'how', 'their', 'if', 'up', 'out', 'many',
        'then', 'them', 'these', 'so', 'some', 'her', 'would', 'make', 'like', 'into', 'him', 'time', 'two',
        'more', 'go', 'no', 'way', 'could', 'my', 'than', 'first', 'been', 'call', 'who', 'oil', 'sit', 'now',
        'find', 'down', 'day', 'did', 'get', 'come', 'made', 'may', 'part'
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

        add_words = ["colby", "college"]
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
    # Limit num_results
    num_results = min(num_results, 3)
    
    # Extract and filter keywords
    raw_keywords = [word.strip() for word in query.split() if len(word.strip()) > 1]
    keywords = filter_stop_words(raw_keywords)
    
    if not keywords:
        return "No valid keywords found in query. Please provide meaningful search terms."
    
    # Run keyword search (now directly awaitable)
    search_results = await search_algolia(keywords[:5], num_results)
    
    if not search_results:
        return "No results found for the given keywords. Try different or broader search terms."
    
    # Format results for the agent
    formatted_output = f"Found {len(search_results)} keyword search results:\n\n"
    
    for i, hit in enumerate(search_results, 1):
        title = _first_present(hit, ["post_title", "title"], "Untitled")
        url = _first_present(hit, ["permalink", "url"], "No URL")
        content = hit.get("content") or hit.get("body") or hit.get("excerpt", "")
        
        # Truncate content to avoid overwhelming the agent
        content_preview = content[:500] + "..." if len(content) > 500 else content
        
        formatted_output += f"{i}. **{title}**\n"
        formatted_output += f"   URL: {url}\n"
        formatted_output += f"   Content: {content_preview}\n\n"
    
    return formatted_output

async def search_algolia(keywords: List[str], max_hits: int = 5) -> List[Dict[str, Any]]:
    """Search Algolia with individual keywords using batched search."""
    app_id = os.environ["ALGOLIA_APP_ID"]
    api_key = os.environ["ALGOLIA_API_KEY"]
    index_name = os.environ.get("ALGOLIA_INDEX_NAME", "prod_colbyedu_aggregated")

    # Filter stop words
    filtered_keywords = filter_stop_words(keywords)
    
    if not filtered_keywords:
        return []
    
    # Create a single batched search request for all keywords
    all_results = []
    async with SearchClient(app_id, api_key) as client:
        try:
            resp = await client.search({
                "requests": [
                    {
                        "indexName": index_name,
                        "query": keyword,
                        "hitsPerPage": 5,
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
            # Align each result set with its originating keyword
            for keyword, result in zip(filtered_keywords, results):
                hits = result.get("hits", [])
                for hit in hits:
                    hit["_search_keyword"] = keyword
                all_results.extend(hits)
        except Exception as e:
            print(f"Error during batched search: {e}")
    
    # Remove duplicates based on objectID while preserving order
    seen_ids = set()
    unique_results = []
    for result in all_results:
        obj_id = (
            result.get("objectID")
            or result.get("objectId")
            or result.get("object_id")
            or result.get("permalink")
            or result.get("url")
        )
        if obj_id and obj_id not in seen_ids:
            seen_ids.add(obj_id)
            unique_results.append(result)
    
    return unique_results[:max_hits]


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


def build_agent() -> Any:
    """Build and configure the RAG agent with environment-based settings."""
    model_id = os.environ.get("OPENAI_MODEL")
    from agno.tools.reasoning import ReasoningTools

    # Get current date/time in EST timezone
    est_tz = ZoneInfo("America/New_York")
    current_time = datetime.now(est_tz)
    formatted_date = current_time.strftime("%I:%M%p, %b %d, %Y").lower().replace(" 0", " ")
    # Result format: "1:13am, Oct 21, 2025"

    base_kwargs = dict(
        model=OpenAIChat(id=model_id),
        description=(
            "You are a Colby College knowledge base assistant. "
            f"Today's date is {formatted_date} (EST). You must use this date to answer questions about deadlines, events, and other time-sensitive information."
            "You must call keyword_search and search_qdrant_vector parallelly in multiple threads to craft a complete answer."        
            "You can ONLY provide information from the knowledge base. "
            "If information is not in the knowledge base, say the standard rejection message."
            "Standard rejection message: 'This question falls outside of my knowledge of Colby College information. Please re-ask your question within a Colby context.'"
            "Do not provide an answer if you cannot cite a URL for each fact in your response from the knowledge base."   
            "Every query must call all available tools to craft a complete answer."        
        ),
        markdown=True,
        knowledge_retriever=retriever,
        search_knowledge=True,
        add_knowledge_to_context=True,
        tools=[
            keyword_search, 
            search_qdrant_vector, 
            ReasoningTools()],
        pre_hooks=[prompt_injection_guardrail, colby_query_validation],

    )

    instructions = [
        "ONLY answer using information from retrieved documents.",
        "CRITICAL: NEVER display raw URLs. ALL links MUST use markdown format: [descriptive text](URL)",
        "The descriptive text should be meaningful - use page titles, section names, or relevant keywords.",
        "When citing specific facts or quotes, create Text Fragment links to highlight the exact text on the source page.",
        "Text Fragment link format: Add '#:~:text=' followed by the URL-encoded text snippet to the end of URLs.",
        "CRITICAL TEXT FRAGMENT RULES:",
        "  1. Keep fragments SHORT (2-6 words maximum) - long fragments break markdown links",
        "  2. AVOID text containing parentheses ( ) - they break markdown syntax. Encode as %28 and %29.",
        "  3. Use simple, unique phrases that don't need special characters",
        "  4. Prefer section headings or short key phrases over long sentences",
        "Avoid using phone numbers, email addresses, or other text that's likely a hyperlink on the page.",
        "Instead, use the SURROUNDING CONTEXT TEXT to create the fragment.",
        "URL-encode the fragment: spaces=%20, colons=%3A, commas=%2C, parentheses=%28%29, etc.",
        "Examples of GOOD link formatting:",
        "  - [financial aid deadlines](https://example.com/page#:~:text=application%20deadline)",
        "  - [campus safety contacts](https://example.com/page#:~:text=Non-emergency%20phone)",
        "  - [appointment scheduling](https://example.com/page#:~:text=schedule%20an%20appointment)",
        "Examples of BAD formatting:",
        "  - Fragment too long: #:~:text=To%20schedule%20call%20at%20207-859-4490%20or%20visit%20our%20office (WAY too long)",
        "  - Contains parentheses: #:~:text=Room%20205%20(Building) (breaks markdown - must encode as %28 %29)",
        "  - Naked URL: https://example.com/page#:~:text=... (NEVER do this)",
        "When in doubt, use a SHORT 2-4 word phrase or just link without text fragment: [title](https://example.com/page)",
        "Standard rejection message: 'This question falls outside of my knowledge of Colby College information. Please re-ask your question within a Colby context.'"
    ]

    advanced_kwargs = dict(
        instructions=instructions,
    )

    try:
        agent = Agent(**{**base_kwargs, **advanced_kwargs})
    except TypeError:
        agent = Agent(**base_kwargs)
    return agent    


async def run_agent_with_message(user_message: str):
    """Run agent with a message - used for performance evaluation."""
    agent = build_agent()
    try:
        response = await agent.arun(user_message)
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
