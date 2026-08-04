"""Step 4: query all buyer questions against the retrieval collection and score results."""
import json
from datetime import date
from pathlib import Path

from retrieval import embedder, store

REPO_ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_FILE = REPO_ROOT / "data" / "questions.json"
RESULTS_DIR = REPO_ROOT / "results" / "retrieval"

TOP_N = 5
WINNING_RANK_CUTOFF = 2  # Swimingo passage ranked #1 or #2 -> "winning"


def load_questions() -> list:
    return json.loads(QUESTIONS_FILE.read_text())


def classify(swimingo_rank) -> str:
    if swimingo_rank is None:
        return "losing"
    if swimingo_rank <= WINNING_RANK_CUTOFF:
        return "winning"
    return "close"


def score_question(question: dict, query_embedding: list, collection) -> dict:
    res = collection.query(query_embeddings=[query_embedding], n_results=TOP_N)

    results = []
    swimingo_rank = None
    for rank, (doc, meta, dist) in enumerate(
        zip(res["documents"][0], res["metadatas"][0], res["distances"][0]), start=1
    ):
        results.append({
            "rank": rank,
            "category": meta["category"],
            "domain": meta["domain"],
            "url": meta["url"],
            "similarity": round(1 - dist, 4),
            "text_preview": doc[:200],
        })
        if meta["category"] == "swimingo" and swimingo_rank is None:
            swimingo_rank = rank

    if swimingo_rank is None:
        beaten_by = sorted({r["domain"] for r in results})
    else:
        beaten_by = sorted({r["domain"] for r in results if r["rank"] < swimingo_rank})

    return {
        "question_id": question["id"],
        "city": question["city"],
        "persona": question["persona"],
        "type": question["type"],
        "question": question["question"],
        "swimingo_rank": swimingo_rank,
        "classification": classify(swimingo_rank),
        "beaten_by": beaten_by,
        "top_results": results,
    }


def run() -> dict:
    questions = load_questions()
    collection = store.get_collection()

    print(f"Embedding {len(questions)} buyer questions...")
    query_embeddings = embedder.embed_texts([q["question"] for q in questions])

    scoreboard = [
        score_question(q, emb, collection) for q, emb in zip(questions, query_embeddings)
    ]

    summary = {
        "total_questions": len(scoreboard),
        "winning": sum(1 for r in scoreboard if r["classification"] == "winning"),
        "close": sum(1 for r in scoreboard if r["classification"] == "close"),
        "losing": sum(1 for r in scoreboard if r["classification"] == "losing"),
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    scoreboard_path = RESULTS_DIR / f"retrieval_scoreboard_{date.today().isoformat()}.json"
    scoreboard_path.write_text(json.dumps({"summary": summary, "questions": scoreboard}, indent=2))

    print(f"Scored {summary['total_questions']} questions: "
          f"{summary['winning']} winning, {summary['close']} close, {summary['losing']} losing")
    print(f"Saved to {scoreboard_path}")

    return {"summary": summary, "path": str(scoreboard_path)}


if __name__ == "__main__":
    run()
