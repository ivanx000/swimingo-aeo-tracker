"""Local sentence-transformers embedding wrapper. No API key, no network at query time."""
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

_model = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def embed_texts(texts: list) -> list:
    embeddings = get_model().encode(texts, show_progress_bar=True, batch_size=32)
    return embeddings.tolist()
