"""Runs every buyer question through the Gemini API and saves the raw responses."""
import json
import os
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from google import genai

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
QUESTIONS_FILE = DATA_DIR / "questions.json"

MODEL_NAME = "gemini-2.5-flash"
DELAY_SECONDS = 4  # be polite to the free-tier rate limit


def load_questions() -> list[dict]:
    """Load the buyer questions from data/questions.json."""
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def output_path(today: str) -> Path:
    """Path to today's raw Gemini results file."""
    return RESULTS_DIR / f"{today}_gemini_raw.json"


def load_existing_results(path: Path) -> list[dict]:
    """Load already-saved results for today, if any (enables resuming)."""
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_results(path: Path, results: list[dict]) -> None:
    """Write results to disk, sorted by question_id."""
    results = sorted(results, key=lambda r: r["question_id"])
    RESULTS_DIR.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def run() -> None:
    """Ask Gemini every buyer question and save the raw responses for today."""
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set. Copy .env.example to .env and fill it in.")

    client = genai.Client(api_key=api_key)
    questions = load_questions()
    today = date.today().isoformat()
    path = output_path(today)

    results = load_existing_results(path)
    done_ids = {r["question_id"] for r in results}
    remaining = [q for q in questions if q["id"] not in done_ids]

    if not remaining:
        print(f"All {len(questions)} questions already answered for {today}.")
        return

    print(f"Resuming: {len(done_ids)} already done, {len(remaining)} remaining.")

    for i, q in enumerate(remaining, start=1):
        print(f"[{i}/{len(remaining)}] Q{q['id']}: {q['question']}")
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=q["question"],
            )
            raw_text = response.text or ""
        except Exception as e:
            print(f"  Error on question {q['id']}: {e}")
            continue

        results.append(
            {
                "question_id": q["id"],
                "platform": "gemini",
                "date": today,
                "raw_response": raw_text,
            }
        )
        save_results(path, results)  # save after every call so an interruption loses nothing
        time.sleep(DELAY_SECONDS)

    print(f"Done. Saved {len(results)} results to {path}")


if __name__ == "__main__":
    run()
