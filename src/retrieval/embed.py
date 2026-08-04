"""Orchestrates Step 3: chunk scraped pages, embed them, store in ChromaDB."""
from retrieval import chunker, embedder, store


def run() -> dict:
    records = chunker.load_scraped_records()
    chunks = chunker.build_chunks(records)
    print(f"{len(records)} scraped pages -> {len(chunks)} chunks "
          f"({chunker.CHUNK_SIZE_WORDS}-word, {chunker.OVERLAP_WORDS}-word overlap)")

    print(f"Embedding with {embedder.EMBEDDING_MODEL_NAME}...")
    embeddings = embedder.embed_texts([c["text"] for c in chunks])

    store.rebuild_collection(chunks, embeddings)
    print(f"Stored {len(chunks)} chunks in ChromaDB at {store.CHROMA_DIR}")

    return {"pages": len(records), "chunks": len(chunks)}


if __name__ == "__main__":
    run()
