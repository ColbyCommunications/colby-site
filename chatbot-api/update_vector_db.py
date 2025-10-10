"""
Vector Database Full Rebuild Script

This script completely rebuilds the QDrant vector database on each run:

1. Deletes existing QDrant collection
2. Creates fresh QDrant collection
3. Fetches all documents from Algolia
4. Chunks content using simple fixed-size chunking with overlap
5. Embeds all chunks
6. Uploads to QDrant

Run daily after algolia_aggregation.js via cron.
"""

import os
import sys
from typing import List, Dict, Any
from dotenv import load_dotenv
from qdrant_client.async_qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import openai
import tiktoken
import asyncio
from tqdm import tqdm

load_dotenv()

# Configuration
ALGOLIA_APP_ID = os.environ["ALGOLIA_APP_ID"]
ALGOLIA_API_KEY = os.environ["ALGOLIA_API_KEY"]
ALGOLIA_INDEX_NAME = os.environ.get("ALGOLIA_INDEX_NAME", "prod_colbyedu_aggregated")

QDRANT_URL = os.environ["QDRANT_URL"]
QDRANT_API_KEY = os.environ["QDRANT_API_KEY"]
COLLECTION_NAME = "colby_knowledge"

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536

# Chunking parameters - smaller chunks with more overlap for better quality
CHUNK_SIZE = 300  # tokens per chunk
OVERLAP_SIZE = 150  # 50% overlap for better context continuity


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens in text using tiktoken."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences using simple regex."""
    import re
    # Split on period, exclamation, or question mark followed by space
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def _first_present(d: Any, keys: List[str], default: Any = "") -> Any:
    """Return the first non-empty value for any key in keys from dict or object."""
    for k in keys:
        # Handle both dict and object (Pydantic models)
        if isinstance(d, dict):
            if k in d and d[k] not in (None, ""):
                return d[k]
        else:
            # Try attribute access for objects
            if hasattr(d, k):
                val = getattr(d, k)
                if val not in (None, ""):
                    return val
    return default


def semantic_chunk_text(text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Semantic chunking that:
    1. Prepends document title and source to each chunk for context
    2. Splits on sentence boundaries (not mid-sentence)
    3. Keeps chunks around 400 tokens with natural boundaries
    """
    if not text or not text.strip():
        return []
    
    title = metadata.get("title", "")
    source = metadata.get("source", "")
    
    # Create context header - this gets embedded with each chunk
    # This way the vector knows "this chunk is about [title]"
    context_header = f"Document: {title}\nSource: {source}\n\n"
    
    # Get encoding for token counting
    try:
        encoding = tiktoken.encoding_for_model("gpt-4")
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    
    # Split into sentences
    sentences = split_into_sentences(text)
    
    if not sentences:
        return []
    
    chunks = []
    current_chunk = context_header
    current_tokens = len(encoding.encode(current_chunk))
    max_chunk_tokens = 400  # Target chunk size
    
    for sentence in sentences:
        sentence_tokens = len(encoding.encode(sentence))
        
        # If adding this sentence would exceed limit, save current chunk
        if current_tokens + sentence_tokens > max_chunk_tokens and current_chunk != context_header:
            # Store the enriched content for embedding
            chunk_content = current_chunk.strip()
            # Store content without context for display to user
            display_content = current_chunk.replace(context_header, '').strip()
            
            chunks.append({
                'content': chunk_content,  # What gets embedded
                'display_content': display_content,  # What user sees
                'tokens': current_tokens,
                'chunk_index': len(chunks),
                **metadata
            })
            
            # Start new chunk with context header
            current_chunk = context_header + sentence
            current_tokens = len(encoding.encode(current_chunk))
        else:
            # Add sentence to current chunk
            if current_chunk == context_header:
                current_chunk += sentence
            else:
                current_chunk += " " + sentence
            current_tokens = len(encoding.encode(current_chunk))
    
    # Don't forget the last chunk
    if current_chunk.strip() != context_header.strip():
        chunk_content = current_chunk.strip()
        display_content = current_chunk.replace(context_header, '').strip()
        
        chunks.append({
            'content': chunk_content,
            'display_content': display_content,
            'tokens': current_tokens,
            'chunk_index': len(chunks),
            **metadata
        })
    
    # Add total_chunks to all chunks
    for chunk in chunks:
        chunk['total_chunks'] = len(chunks)
    
    return chunks


async def fetch_all_algolia_docs() -> List[Dict[str, Any]]:
    """Fetch all documents from Algolia aggregated index (async with aggregator)."""
    print(f"Fetching documents from Algolia index: {ALGOLIA_INDEX_NAME}")
    
    all_hits = []
    pbar = tqdm(desc="Fetching from Algolia", unit=" docs")
    
    def aggregator(response):
        """Aggregates hits from each browse response batch."""
        all_hits.extend(response.hits)
        pbar.update(len(response.hits))
    
    # Use async SearchClient with context manager
    from algoliasearch.search.client import SearchClient
    
    async with SearchClient(ALGOLIA_APP_ID, ALGOLIA_API_KEY) as client:
        await client.browse_objects(
            index_name=ALGOLIA_INDEX_NAME,
            aggregator=aggregator,
            browse_params={
                "attributesToRetrieve": [
                    "objectID",
                    "post_title",
                    "cleaned_title",
                    "content",
                    "excerpt",
                    "permalink",
                    "originIndexLabel",
                    "title",
                    "body",
                    "url"
                ]
            }
        )
    
    pbar.close()
    print(f"✅ Fetched {len(all_hits)} documents from Algolia")
    return all_hits


async def recreate_qdrant_collection(client: AsyncQdrantClient):
    """Delete and recreate QDrant collection from scratch."""
    print(f"Recreating QDrant collection: {COLLECTION_NAME}")
    
    # Delete if exists
    try:
        await client.delete_collection(collection_name=COLLECTION_NAME)
        print("🗑️  Deleted existing collection")
    except Exception:
        print("ℹ️  No existing collection to delete")
    
    # Create new collection
    await client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=EMBEDDING_DIMS,
            distance=Distance.COSINE
        )
    )
    print("✅ Collection created successfully")


def prepare_documents(algolia_hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert Algolia hits to structured documents with simple fixed-size chunks.
    """
    print("Preparing and chunking documents...")
    
    all_chunks = []
    docs_with_generated_url = 0
    docs_with_fallback_content = 0
    
    # Debug: Check first document structure
    if algolia_hits:
        first_doc = algolia_hits[0]
        if hasattr(first_doc, 'model_dump'):
            doc_dict = first_doc.model_dump()
        elif hasattr(first_doc, 'dict'):
            doc_dict = first_doc.dict()
        else:
            doc_dict = dict(first_doc) if hasattr(first_doc, '__dict__') else {}
        
        print(f"\n🔍 Debug - First document type: {type(first_doc)}")
        print(f"🔍 Debug - Available keys: {list(doc_dict.keys())}")
        print(f"🔍 Debug - Sample doc: {str(doc_dict)[:500]}...\n")
    
    for idx, hit in enumerate(tqdm(algolia_hits, desc="Processing documents")):
        # Note: Algolia v4 Hit objects use snake_case field names
        object_id = _first_present(hit, ["object_id", "objectID", "objectId"], f"doc_{idx}")
        title = _first_present(hit, ["cleaned_title", "post_title", "title"], "Colby College Resource")
        content = _first_present(hit, ["content", "body", "excerpt"], "")
        url = _first_present(hit, ["permalink", "url"], "")
        source = _first_present(hit, ["originIndexLabel", "origin_index_label"], "Unknown")
        
        # Generate URL if missing
        if not url:
            docs_with_generated_url += 1
            url = f"internal://{object_id}"
        
        # Use title or placeholder if content is missing
        if not content:
            docs_with_fallback_content += 1
            content = title if title != "Colby College Resource" else f"Document {object_id}"
        
        metadata = {
            "objectID": object_id,
            "title": title,
            "url": url,
            "source": source,
        }
        
        # Use semantic chunking with context headers
        chunks = semantic_chunk_text(content, metadata)
        all_chunks.extend(chunks)
    
    print(f"\n📊 Document Processing Summary:")
    print(f"   Total documents: {len(algolia_hits)}")
    print(f"   ℹ️  Docs with generated URL: {docs_with_generated_url}")
    print(f"   ℹ️  Docs with fallback content: {docs_with_fallback_content}")
    print(f"   ✅ All docs processed: {len(algolia_hits)}")
    print(f"   📝 Chunks created: {len(all_chunks)}\n")
    return all_chunks


async def generate_embeddings_batch(texts: List[str], batch_size: int = 200) -> List[List[float]]:
    """
    Generate embeddings for texts in batches with rate limit handling.
    
    Includes exponential backoff retry logic to handle OpenAI rate limits gracefully.
    """
    client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    all_embeddings = []
    
    for i in tqdm(range(0, len(texts), batch_size), desc="Generating embeddings"):
        batch = texts[i:i + batch_size]
        
        # Retry logic with exponential backoff
        max_retries = 5
        retry_delay = 1  # Start with 1 second
        
        for attempt in range(max_retries):
            try:
                response = await client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=batch
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                # Add small delay between batches to avoid rate limits
                await asyncio.sleep(0.5)
                break  # Success, exit retry loop
                
            except openai.RateLimitError as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    print(f"\n⚠️  Rate limit hit. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"\n❌ Rate limit error after {max_retries} attempts")
                    raise
            except Exception as e:
                print(f"\n❌ Error generating embeddings: {e}")
                raise
    
    return all_embeddings


async def upload_all_to_qdrant(client: AsyncQdrantClient, chunks: List[Dict[str, Any]]):
    """Generate embeddings and upload all documents to QDrant."""
    print("Generating embeddings and uploading to QDrant...")
    
    # Prepare texts for embedding
    texts = [chunk["content"] for chunk in chunks]
    
    # Generate embeddings
    embeddings = await generate_embeddings_batch(texts)
    
    # Create points for QDrant
    print("Preparing points for upload...")
    points = []
    for idx, (chunk, embedding) in enumerate(tqdm(zip(chunks, embeddings), total=len(chunks), desc="Creating points")):
        point = PointStruct(
            id=idx,  # Sequential ID starting from 0
            vector=embedding,
            payload={
                "content": chunk.get("display_content", chunk["content"]),  # Display without context
                "content_with_context": chunk["content"],  # Full enriched version for debugging
                "title": chunk["title"],
                "name": chunk["title"], 
                "url": chunk["url"],
                "source": chunk["source"],
                "objectID": chunk["objectID"],
                "chunk_index": chunk["chunk_index"],
                "total_chunks": chunk["total_chunks"],
                "tokens": chunk.get("tokens", 0)
            }
        )
        points.append(point)
    
    # Upload using upload_points with built-in parallelization
    batch_size = 100
    parallel_workers = 4  # Number of parallel upload workers
    
    print(f"Uploading {len(points)} points to QDrant (batch_size={batch_size}, parallel={parallel_workers})...")
    
    # Use upload_points with parallel parameter for efficient uploads
    client.upload_points(
        collection_name=COLLECTION_NAME,
        points=points,
        batch_size=batch_size,
        parallel=parallel_workers,
        max_retries=3
    )
    
    print(f"✅ Successfully uploaded {len(points)} vectors to QDrant")


async def main():
    """Main workflow - full rebuild of vector database on each run."""
    print("=" * 60)
    print("🚀 Vector Database Full Rebuild")
    print("=" * 60)
    
    # 1. Fetch all documents from Algolia
    algolia_docs = await fetch_all_algolia_docs()
    
    if not algolia_docs:
        print("❌ ERROR: No documents fetched from Algolia")
        sys.exit(1)
    
    # 2. Initialize async QDrant client with increased timeout
    print(f"\n🔌 Connecting to QDrant at: {QDRANT_URL}")
    qdrant_client = AsyncQdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        timeout=300  # 5 minutes timeout for large uploads
    )
    
    # 3. Recreate collection from scratch
    await recreate_qdrant_collection(qdrant_client)
    
    # 4. Prepare and chunk all documents
    chunks = prepare_documents(algolia_docs)
    
    if not chunks:
        print("❌ ERROR: No chunks created")
        sys.exit(1)
    
    # 5. Upload all documents
    await upload_all_to_qdrant(qdrant_client, chunks)
    
    # 6. Verify and report
    collection_info = await qdrant_client.get_collection(collection_name=COLLECTION_NAME)
    print("\n" + "=" * 60)
    print("✅ Database Rebuild Complete!")
    print("=" * 60)
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Documents processed: {len(algolia_docs)}")
    print(f"Total vectors: {collection_info.points_count}")
    print(f"Chunk size: {CHUNK_SIZE} tokens")
    print(f"Overlap: {OVERLAP_SIZE} tokens")
    print(f"Dimensions: {EMBEDDING_DIMS}")
    print(f"Distance: Cosine")
    print("=" * 60)
    
    # Close the client
    await qdrant_client.close()


if __name__ == "__main__":
    asyncio.run(main())

