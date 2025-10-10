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
import gc
from typing import List, Dict, Any, Iterable
from dotenv import load_dotenv
from qdrant_client.async_qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import openai
import tiktoken
import asyncio
from tqdm import tqdm

load_dotenv()

ALGOLIA_APP_ID = os.environ["ALGOLIA_APP_ID"]
ALGOLIA_API_KEY = os.environ["ALGOLIA_API_KEY"]
ALGOLIA_INDEX_NAME = os.environ.get("ALGOLIA_INDEX_NAME", "prod_colbyedu_aggregated")

QDRANT_URL = os.environ["QDRANT_URL"]
QDRANT_API_KEY = os.environ["QDRANT_API_KEY"]
COLLECTION_NAME = "colby_knowledge"

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536

CHUNK_SIZE = 300
OVERLAP_SIZE = 150

DOC_BATCH_SIZE = 300
EMBED_BATCH_SIZE = 64
UPLOAD_BATCH_SIZE = 512
PARALLEL_EMBED_REQS = 3

ENC = tiktoken.get_encoding("cl100k_base")


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
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def _first_present(d: Any, keys: List[str], default: Any = "") -> Any:
    """Return the first non-empty value for any key in keys from dict or object."""
    for k in keys:
        if isinstance(d, dict):
            if k in d and d[k] not in (None, ""):
                return d[k]
        else:
            if hasattr(d, k):
                val = getattr(d, k)
                if val not in (None, ""):
                    return val
    return default


def semantic_chunk_text(text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """CPU-friendly chunker: encode sentences once; keep running token count."""
    import re
    if not text or not text.strip():
        return []

    title = metadata.get("title", "")
    source = metadata.get("source", "")
    context_header = f"Document: {title}\nSource: {source}\n\n"

    header_tokens = len(ENC.encode(context_header))
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    if not sentences:
        return []

    encoded = [(s, len(ENC.encode(s))) for s in sentences]
    max_tokens = CHUNK_SIZE or 400

    chunks, cur_parts = [], [context_header]
    cur_tokens = header_tokens

    for s, s_tokens in encoded:
        # +1 for space when appending after first sentence
        add_cost = s_tokens + (1 if len(cur_parts) > 1 else 0)
        if cur_tokens + add_cost > max_tokens and len(cur_parts) > 1:
            chunk_text = " ".join(cur_parts)
            chunks.append({
                "content": chunk_text,
                "display_content": chunk_text.replace(context_header, "").strip(),
                "tokens": cur_tokens,
                "chunk_index": len(chunks),
                **metadata
            })
            cur_parts = [context_header, s]
            cur_tokens = header_tokens + s_tokens
        else:
            if len(cur_parts) > 1:
                cur_parts.append(s)
                cur_tokens += 1 + s_tokens
            else:
                cur_parts.append(s)
                cur_tokens += s_tokens

    if len(cur_parts) > 1:
        chunk_text = " ".join(cur_parts)
        chunks.append({
            "content": chunk_text,
            "display_content": chunk_text.replace(context_header, "").strip(),
            "tokens": cur_tokens,
            "chunk_index": len(chunks),
            **metadata
        })

    total = len(chunks)
    for c in chunks:
        c["total_chunks"] = total
    return chunks


def prepare_one_doc(hit: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Per-doc preparation so we don't accumulate everything at once."""
    def _first_present(d: Any, keys: List[str], default: Any = "") -> Any:
        for k in keys:
            if isinstance(d, dict):
                if k in d and d[k] not in (None, ""):
                    return d[k]
            else:
                if hasattr(d, k):
                    val = getattr(d, k)
                    if val not in (None, ""):
                        return val
        return default

    object_id = _first_present(hit, ["object_id", "objectID", "objectId"], "unknown")
    title = _first_present(hit, ["cleaned_title", "post_title", "title"], "Colby College Resource")
    content = _first_present(hit, ["content", "body", "excerpt"], "")
    url = _first_present(hit, ["permalink", "url"], "")
    source = _first_present(hit, ["originIndexLabel", "origin_index_label"], "Unknown")

    if not url:
        url = f"internal://{object_id}"
    if not content:
        content = title if title != "Colby College Resource" else f"Document {object_id}"

    metadata = {"objectID": object_id, "title": title, "url": url, "source": source}
    return semantic_chunk_text(content, metadata)


async def fetch_all_algolia_docs() -> List[Dict[str, Any]]:
    """Fetch all documents from Algolia aggregated index (async with aggregator)."""
    print(f"Fetching documents from Algolia index: {ALGOLIA_INDEX_NAME}")
    
    all_hits = []
    pbar = tqdm(desc="Fetching from Algolia", unit=" docs")
    
    def aggregator(response):
        """Aggregates hits from each browse response batch."""
        all_hits.extend(response.hits)
        pbar.update(len(response.hits))
    
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


class EmbedLimiter:
    """Bound concurrency so CPU & rate limits stay tame."""
    def __init__(self, client, semaphore):
        self.client = client
        self.sem = semaphore

    async def embed_batch(self, inputs: List[str]):
        async with self.sem:
            resp = await self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=inputs
            )
            return [d.embedding for d in resp.data]


async def recreate_qdrant_collection(client: AsyncQdrantClient):
    """Delete and recreate QDrant collection from scratch."""
    print(f"Recreating QDrant collection: {COLLECTION_NAME}")
    
    try:
        await client.delete_collection(collection_name=COLLECTION_NAME)
        print("🗑️  Deleted existing collection")
    except Exception:
        print("ℹ️  No existing collection to delete")
    
    await client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=EMBEDDING_DIMS,
            distance=Distance.COSINE
        )
    )
    print("✅ Collection created successfully")


async def process_and_upload_batch(
    qc: AsyncQdrantClient,
    openai_client: openai.AsyncOpenAI,
    docs: List[Dict[str, Any]],
    start_point_id: int
) -> int:
    """Chunk -> embed (in small batches) -> upload (in small batches) -> free RAM."""
    # 1) Chunk just these docs
    chunks: List[Dict[str, Any]] = []
    for hit in docs:
        chunks.extend(prepare_one_doc(hit))

    if not chunks:
        return start_point_id

    # 2) Embed in small batches with bounded concurrency
    limiter = EmbedLimiter(openai_client, asyncio.Semaphore(PARALLEL_EMBED_REQS))
    texts = [c["content"] for c in chunks]
    embeddings: List[List[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i:i + EMBED_BATCH_SIZE]
        embeddings.extend(await limiter.embed_batch(batch))
        await asyncio.sleep(0)  # let event loop breathe

    # 3) Build points on the fly and upload in slices
    points: List[PointStruct] = []
    pid = start_point_id
    for chunk, vec in zip(chunks, embeddings):
        points.append(PointStruct(
            id=pid,
            vector=vec,
            payload={
                "content": chunk.get("display_content", chunk["content"]),
                "content_with_context": chunk["content"],
                "title": chunk["title"],
                "name": chunk["title"],
                "url": chunk["url"],
                "source": chunk["source"],
                "objectID": chunk["objectID"],
                "chunk_index": chunk["chunk_index"],
                "total_chunks": chunk["total_chunks"],
                "tokens": chunk.get("tokens", 0),
            }
        ))
        pid += 1
        if len(points) >= UPLOAD_BATCH_SIZE:
            await qc.upsert(collection_name=COLLECTION_NAME, points=points, wait=False)
            points.clear()
            gc.collect()
            await asyncio.sleep(0)

    if points:
        await qc.upsert(collection_name=COLLECTION_NAME, points=points, wait=False)
        points.clear()
        gc.collect()

    # 4) drop big locals before returning
    del chunks, texts, embeddings
    gc.collect()
    return pid


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
        object_id = _first_present(hit, ["object_id", "objectID", "objectId"], f"doc_{idx}")
        title = _first_present(hit, ["cleaned_title", "post_title", "title"], "Colby College Resource")
        content = _first_present(hit, ["content", "body", "excerpt"], "")
        url = _first_present(hit, ["permalink", "url"], "")
        source = _first_present(hit, ["originIndexLabel", "origin_index_label"], "Unknown")
        
        if not url:
            docs_with_generated_url += 1
            url = f"internal://{object_id}"
        
        if not content:
            docs_with_fallback_content += 1
            content = title if title != "Colby College Resource" else f"Document {object_id}"
        
        metadata = {
            "objectID": object_id,
            "title": title,
            "url": url,
            "source": source,
        }
        
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
    """Generate embeddings for texts in batches with rate limit handling."""
    client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    all_embeddings = []
    
    for i in tqdm(range(0, len(texts), batch_size), desc="Generating embeddings"):
        batch = texts[i:i + batch_size]
        
        max_retries = 5
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                response = await client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=batch
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                await asyncio.sleep(0.5)
                break
                
            except openai.RateLimitError as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
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
    
    texts = [chunk["content"] for chunk in chunks]
    embeddings = await generate_embeddings_batch(texts)
    
    print("Preparing points for upload...")
    points = []
    for idx, (chunk, embedding) in enumerate(tqdm(zip(chunks, embeddings), total=len(chunks), desc="Creating points")):
        point = PointStruct(
            id=idx,
            vector=embedding,
            payload={
                "content": chunk.get("display_content", chunk["content"]),
                "content_with_context": chunk["content"],
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
    
    batch_size = 100
    parallel_workers = 4
    
    print(f"Uploading {len(points)} points to QDrant (batch_size={batch_size}, parallel={parallel_workers})...")
    
    client.upload_points(
        collection_name=COLLECTION_NAME,
        points=points,
        batch_size=batch_size,
        parallel=parallel_workers,
        max_retries=3
    )
    
    print(f"✅ Successfully uploaded {len(points)} vectors to QDrant")


async def main():
    print("=" * 60)
    print("🚀 Vector Database Full Rebuild (memory-safe)")
    print("=" * 60)

    algolia_docs = await fetch_all_algolia_docs()
    if not algolia_docs:
        print("❌ No documents from Algolia")
        sys.exit(1)

    print(f"\n🔌 Connecting to QDrant at: {QDRANT_URL}")
    qdrant_client = AsyncQdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        prefer_grpc=True,
        timeout=300
    )
    await recreate_qdrant_collection(qdrant_client)

    openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)

    next_point_id = 0
    total_docs = len(algolia_docs)
    for i in range(0, total_docs, DOC_BATCH_SIZE):
        batch_docs = algolia_docs[i:i + DOC_BATCH_SIZE]
        print(f"📦 Processing docs {i+1}-{min(i+DOC_BATCH_SIZE, total_docs)} / {total_docs}")
        next_point_id = await process_and_upload_batch(
            qdrant_client, openai_client, batch_docs, start_point_id=next_point_id
        )

    collection_info = await qdrant_client.get_collection(collection_name=COLLECTION_NAME)
    print("\n" + "=" * 60)
    print("✅ Rebuild Complete (streaming)")
    print("=" * 60)
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Total vectors: {collection_info.points_count}")
    print(f"Chunk size: {CHUNK_SIZE}  |  Dims: {EMBEDDING_DIMS}  |  Distance: Cosine")
    print("=" * 60)

    await qdrant_client.close()


if __name__ == "__main__":
    asyncio.run(main())

