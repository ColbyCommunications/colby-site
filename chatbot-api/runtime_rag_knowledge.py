from __future__ import annotations

import os
import sys
import json
import asyncio
from typing import List, Dict, Any, Optional
from typing import Set

from dotenv import load_dotenv
from algoliasearch.search.client import SearchClient
from pydantic import BaseModel, Field

# Modern Agno imports
from agno.agent import Agent
from agno.tools import tool
from agno.models.openai import OpenAIChat

# Thinking/trace tools (required to always show thinking tools)
from agno.tools.reasoning import ReasoningTools  # type: ignore


class ColbyRAGResponse(BaseModel):
    """
    Structured response model for Colby RAG Assistant.
    
    This enforces that the agent always searches the knowledge base
    and clearly indicates when it doesn't have reliable information.
    All responses must include proper citations.
    """
    answer: str = Field(
        ..., 
        description=(
            "The complete answer to the user's question with a '## Sources' section at the end. "
            "If information was found, answer naturally then add:\n\n## Sources\n1. [Title](URL)\n2. [Title](URL)\n"
            "If no reliable information found, this must be: 'I don't know - I could not find reliable information about this in the Colby College knowledge base.'"
        )
    )
    found_information: bool = Field(
        ..., 
        description="True if reliable information was found in the knowledge base, False otherwise"
    )
    sources_used: List[str] = Field(
        default_factory=list,
        description="List of source URLs that were used to answer the question. Must match URLs in the answer's Sources section. Empty if no information found."
    )
    search_performed: bool = Field(
        default=True,
        description="Always True - confirms that knowledge base was searched"
    )


def _load_stopwords() -> Set[str]:
    """Load English stopwords using NLTK, with safe fallback to a static set.

    Returns a lowercase set of stopwords.
    """
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
    """Remove stop words and very short tokens using NLTK stopwords.

    - Uses NLTK English stopwords if available; falls back to static list.
    - Keeps original casing in the returned keywords.
    - Filters tokens of length <= 2 after stripping.
    """
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

async def search_algolia_individual_keywords(keywords: List[str], max_hits: int = 3) -> List[Dict[str, Any]]:
    """Search Algolia with individual keywords, not merged together."""
    app_id = os.environ["ALGOLIA_APP_ID"]
    api_key = os.environ["ALGOLIA_API_KEY"]
    index_name = os.environ.get("ALGOLIA_INDEX_NAME", "prod_colbyedu_aggregated")

    # Filter stop words
    filtered_keywords = filter_stop_words(keywords)
    # print(f"Original keywords: {keywords}")
    # print(f"Filtered keywords (no stop words): {filtered_keywords}")
    
    if not filtered_keywords:
        return []
    
    # Create a single batched search request for all keywords
    all_results = []
    async with SearchClient(app_id, api_key) as client:
        try:
            # print(f"Searching batched keywords: {filtered_keywords}")
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
                # print(f"Data keys: {data.keys()}")
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
        # print(f"Object ID: {obj_id}")
        if obj_id and obj_id not in seen_ids:
            seen_ids.add(obj_id)
            unique_results.append(result)
    
    # print(f"Total unique results: {len(unique_results)}")
    return unique_results[:max_hits]


async def search_algolia(keywords: List[str], max_hits: int = 5) -> List[Dict[str, Any]]:
    """Search Algolia with individual keywords."""
    return await search_algolia_individual_keywords(keywords, max_hits)


def retriever(
    query: str, 
    agent: Optional[Agent] = None, 
    num_documents: int = 5, 
    **kwargs
) -> Optional[list[dict]]:
    """
    Custom retriever function to search Algolia for relevant documents.
    Embeds source URLs directly in content for LLM visibility.
    """
    try:
        raw_keywords = [word.strip() for word in query.split() if len(word.strip()) > 1]
        keywords = filter_stop_words(raw_keywords)
        
        if not keywords:
            return []
        
        import asyncio
        import concurrent.futures
        
        try:
            loop = asyncio.get_running_loop()
            def run_search():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(search_algolia(keywords[:5], num_documents))
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_search)
                search_results = future.result(timeout=30)
        except RuntimeError:
            search_results = asyncio.run(search_algolia(keywords[:5], num_documents))
        
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
                "source": _first_present(hit, ["originIndexLabel", "origin_index_label"], "Unknown"),
                "id": _first_present(hit, ["objectID", "objectId", "object_id", "permalink", "url"], ""),
            }
            formatted_results.append(doc)
        
        return formatted_results
        
    except Exception as e:
        print(f"Error during Algolia search: {str(e)}")
        return None


def build_agent() -> Any:
    """
    Build and configure the RAG agent.
    
    Configuration via environment variables:
    - OPENAI_MODEL: Model to use (default: gpt-4o)
    - AGENT_SHOW_TOOL_CALLS: Show tool calls (default: false)
    - AGENT_STREAM_INTERMEDIATE: Stream intermediate steps (default: false)
    """
    model_id = os.environ.get("OPENAI_MODEL", "gpt-4o")
    show_tool_calls = os.environ.get("AGENT_SHOW_TOOL_CALLS", "false").lower() == "true"
    stream_intermediate = os.environ.get("AGENT_STREAM_INTERMEDIATE", "false").lower() == "true"

    base_kwargs = dict(
        model=OpenAIChat(id=model_id),
        description=(
            "You are a Colby College knowledge base assistant. "
            "You can ONLY provide information from the knowledge base. "
            "If information is not in the knowledge base, say you don't know. "
            "Do not provide an answer if you cannot cite a URL for each fact in your response from the knowledge base. [1][URL] [2][URL] [3][URL]..."
            "Current academic year: 2025-2026."
        ),
        markdown=True,
        knowledge_retriever=retriever,
        search_knowledge=True,
        add_knowledge_to_context=True,
    )

    instructions = [
        "You are a Colby College knowledge base assistant.",
        "ONLY answer using information from retrieved documents.",
        "Each document has [SOURCE: Title - URL] markers - extract and cite these URLs.",
        "",
        "RESPONSE FORMAT:",
        "1. Answer the question",
        "2. End with: ## Sources\\n1. [Title](URL)\\n2. [Title](URL)",
        "",
        "If no information found: 'I don't know - I could not find reliable information about this in the Colby College knowledge base.'",
    ]

    advanced_kwargs = dict(
        instructions=instructions,
        show_tool_calls=show_tool_calls,
        stream_intermediate_steps=stream_intermediate,
    )

    try:
        agent = Agent(**{**base_kwargs, **advanced_kwargs})
    except TypeError:
        agent = Agent(**base_kwargs)
    return agent    


async def run_agent_with_message(user_message: str):
    """Wrapper function for running the agent - used by performance evaluation."""
    agent = build_agent()
    try:
        # Stream model output; reveal reasoning/tool traces when supported
        try:
            response = await agent.arun(user_message)
        except TypeError:
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
            try:
                await agent.aprint_response(user_message, stream=True, show_reasoning=True)
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
    if "rag_response" not in df.columns:
        df["rag_response"] = ""

    from tqdm import tqdm
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Processing rows"):
        user_message = str(row.get("nl_queries", "")).strip()
        if not user_message:
            df.at[idx, "rag_response"] = ""
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
        df.at[idx, "rag_response"] = text
        try:
            df.to_csv(csv_path, index=False)
        except Exception as e:
            print(f"Failed to write CSV at row {idx}: {e}")




if __name__ == "__main__":
    asyncio.run(main())
    


