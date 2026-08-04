"""ChromaDB persistence for retrieval chunks. Fully local, no server, no API key."""
from pathlib import Path

import chromadb

REPO_ROOT = Path(__file__).resolve().parents[2]
CHROMA_DIR = REPO_ROOT / "chroma_db"
COLLECTION_NAME = "swimingo_retrieval"


def get_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def rebuild_collection(chunks: list, embeddings: list) -> chromadb.Collection:
    """Drop and recreate the collection from scratch.

    Embedding a few hundred chunks with a local MiniLM model takes seconds,
    so there's no benefit to incremental updates — always rebuilding avoids
    stale or duplicate entries from earlier runs.

    Uses cosine distance (not Chroma's L2 default) so query results carry a
    bounded, easily-interpreted similarity score (1 - cosine_distance)
    instead of an unbounded raw L2 distance.
    """
    client = get_client()
    if COLLECTION_NAME in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION_NAME)

    collection = client.create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
    collection.add(
        ids=[c["chunk_id"] for c in chunks],
        embeddings=embeddings,
        documents=[c["text"] for c in chunks],
        metadatas=[
            {
                "url": c["url"],
                "domain": c["domain"],
                "category": c["category"],
                "chunk_index": c["chunk_index"],
                "word_count": c["word_count"],
            }
            for c in chunks
        ],
    )
    return collection


def get_collection() -> chromadb.Collection:
    return get_client().get_collection(COLLECTION_NAME)
