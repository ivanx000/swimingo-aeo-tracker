"""Splits scraped pages into fixed-size, overlapping word chunks."""
import glob
import json
from pathlib import Path

from retrieval.scraper import SCRAPED_DIR, THIN_CONTENT_WORD_THRESHOLD, normalize_domain, slug_for_url

CHUNK_SIZE_WORDS = 400
OVERLAP_WORDS = 50


def load_scraped_records() -> list:
    """Load cached scrape records, skipping ones too thin to be real page content.

    Below THIN_CONTENT_WORD_THRESHOLD covers both hard failures (e.g.
    superprof.ca's CAPTCHA wall, 0 words) and soft failures where the fetch
    "succeeded" but the page itself wasn't real content (e.g. a stale
    sitemap URL that 404s with a short "page not found" message, still
    scraped successfully as HTML). Neither should feed the embedding.
    """
    records = []
    skipped = []
    for path in glob.glob(str(SCRAPED_DIR / "**" / "*.json"), recursive=True):
        record = json.loads(Path(path).read_text())
        if record.get("word_count", 0) >= THIN_CONTENT_WORD_THRESHOLD:
            records.append(record)
        else:
            skipped.append(record["url"])

    if skipped:
        print(f"Skipping {len(skipped)} thin/failed scrape(s): {skipped}")

    return records


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_WORDS, overlap: int = OVERLAP_WORDS) -> list:
    words = text.split()
    if not words:
        return []

    step = chunk_size - overlap
    pieces = []
    for start in range(0, len(words), step):
        piece_words = words[start:start + chunk_size]
        pieces.append(" ".join(piece_words))
        if start + chunk_size >= len(words):
            break
    return pieces


def build_chunks(records: list) -> list:
    chunks = []
    for record in records:
        domain = normalize_domain(record["domain"])
        pieces = chunk_text(record["text"])
        for i, piece in enumerate(pieces):
            chunks.append({
                "chunk_id": f"{record['category']}__{domain}__{slug_for_url(record['url'])}__{i}",
                "url": record["url"],
                "domain": domain,
                "category": record["category"],
                "chunk_index": i,
                "word_count": len(piece.split()),
                "text": piece,
            })
    return chunks
