"""Runs every buyer question through the Gemini API and saves the raw responses."""
import json
import os
import re
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
QUESTIONS_FILE = DATA_DIR / "questions.json"

# "gemini-flash-latest" is Google's rolling alias for the current stable free-tier
# Flash model, so this keeps working as Google retires/renames dated model versions.
MODEL_NAME = "gemini-flash-latest"

# Free tier caps this model at 5 requests/minute; spacing calls by 13s (>60/5)
# keeps every call under that cap instead of bursting through all 42 questions
# and hitting 429s on nearly every one after the first few.
MIN_INTERVAL_SECONDS = 13.0
DEFAULT_RETRY_DELAY_SECONDS = 15.0
MAX_RATE_LIMIT_RETRIES = 6


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


def parse_retry_delay(error: errors.ClientError) -> float:
    """Extract the server-suggested retry delay (seconds) from a 429 error.

    Falls back to DEFAULT_RETRY_DELAY_SECONDS if the response doesn't include
    a RetryInfo detail (Google's standard quota-exceeded error shape).
    """
    details = getattr(error, "details", None) or {}
    error_details = details.get("error", {}).get("details", [])
    for detail in error_details:
        if str(detail.get("@type", "")).endswith("RetryInfo"):
            match = re.match(r"([\d.]+)", str(detail.get("retryDelay", "")))
            if match:
                return float(match.group(1))
    return DEFAULT_RETRY_DELAY_SECONDS


def ask_gemini(client: genai.Client, question_text: str) -> str:
    """Ask Gemini one question, retrying on 429 instead of giving up on it."""
    for attempt in range(1, MAX_RATE_LIMIT_RETRIES + 1):
        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=question_text)
            return response.text or ""
        except errors.ClientError as e:
            if e.code != 429:
                raise
            delay = parse_retry_delay(e)
            print(f"  Rate limited (attempt {attempt}/{MAX_RATE_LIMIT_RETRIES}); "
                  f"waiting {delay:.0f}s before retrying...")
            time.sleep(delay)

    raise RuntimeError(f"Still rate-limited after {MAX_RATE_LIMIT_RETRIES} retries")


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
            raw_text = ask_gemini(client, q["question"])
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
        time.sleep(MIN_INTERVAL_SECONDS)

    print(f"Done. Saved {len(results)} results to {path}")


if __name__ == "__main__":
    run()
