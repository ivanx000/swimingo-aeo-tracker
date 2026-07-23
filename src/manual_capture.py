"""Interactive manual-paste capture tool for platforms that can't be automated
(ChatGPT, Perplexity, Copilot, Google AI Overviews)."""
import json
import sys
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
QUESTIONS_FILE = DATA_DIR / "questions.json"

PLATFORMS = ["chatgpt", "perplexity", "copilot", "ai_overviews"]
END_SENTINEL = "END"
SKIP_SENTINEL = "SKIP"


def load_questions() -> list[dict]:
    """Load the buyer questions from data/questions.json."""
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def output_path(today: str, platform: str) -> Path:
    """Path to today's raw results file for a given platform."""
    return RESULTS_DIR / f"{today}_{platform}_raw.json"


def load_existing_results(path: Path) -> list[dict]:
    """Load already-captured results for today, if any (enables resuming)."""
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


class InputStreamClosed(Exception):
    """Raised when stdin closes (EOF) before any input was given for a question."""


def read_multiline_paste() -> str | None:
    """Read a multi-line pasted response, terminated by a blank line or END.

    Returns None if the user types SKIP as the first line. Raises
    InputStreamClosed if stdin closes before any line is entered, so the
    caller can stop the session instead of saving empty responses.
    """
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            if not lines:
                raise InputStreamClosed
            break
        if not lines and line.strip() == SKIP_SENTINEL:
            return None
        if line.strip() == END_SENTINEL or line == "":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def select_platform() -> str:
    """Interactively prompt the user to choose which platform to capture."""
    print("Select a platform to capture:")
    for i, p in enumerate(PLATFORMS, start=1):
        print(f"  {i}. {p}")
    choice = input("Platform number or name: ").strip().lower()

    if choice in PLATFORMS:
        return choice
    try:
        return PLATFORMS[int(choice) - 1]
    except (ValueError, IndexError):
        print(f"Invalid selection: {choice}")
        sys.exit(1)


def run(platform: str) -> None:
    """Run the manual capture loop for a single platform, resuming if partly done."""
    if platform not in PLATFORMS:
        raise ValueError(f"Unknown platform '{platform}'. Choose from: {PLATFORMS}")

    questions = load_questions()
    today = date.today().isoformat()
    path = output_path(today, platform)

    results = load_existing_results(path)
    done_ids = {r["question_id"] for r in results}
    remaining = [q for q in questions if q["id"] not in done_ids]

    if not remaining:
        print(f"All {len(questions)} questions already captured for {platform} on {today}.")
        return

    print(f"\nCapturing responses for: {platform}")
    print(f"{len(done_ids)} already done, {len(remaining)} remaining.")
    print(f"Paste the full response, then a blank line (or '{END_SENTINEL}') to finish.")
    print(f"Type {SKIP_SENTINEL} to skip a question.\n")

    for i, q in enumerate(remaining, start=1):
        print(f"\n[{i}/{len(remaining)}] Q{q['id']} ({q['city']}, {q['persona']}, {q['type']}):")
        print(f"  {q['question']}")
        print("Paste response below:")
        try:
            response_text = read_multiline_paste()
        except InputStreamClosed:
            print("\nInput stream closed. Progress saved; run again to resume.")
            break

        if response_text is None:
            print("  Skipped.")
            continue

        results.append(
            {
                "question_id": q["id"],
                "platform": platform,
                "date": today,
                "raw_response": response_text,
            }
        )
        save_results(path, results)  # save after every question so progress is never lost

    print(f"\nDone. Saved {len(results)} results to {path}")


def main() -> None:
    """Standalone entry point: use a CLI arg if given, otherwise prompt for a platform."""
    if len(sys.argv) > 1 and sys.argv[1] in PLATFORMS:
        platform = sys.argv[1]
    else:
        platform = select_platform()
    run(platform)


if __name__ == "__main__":
    main()
