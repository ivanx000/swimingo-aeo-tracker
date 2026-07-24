"""Manual capture tool for platforms that can't be automated (ChatGPT,
Perplexity, Copilot, Google AI Overviews).

Two capture methods avoid the terminal's paste-length issues with very long
single blocks of text (e.g. a long AI Overview response):
  - "editor" (default): each question opens in the user's text editor; the
    saved file content becomes the response.
  - "clipboard": the user copies the response, presses Enter, and the tool
    reads it straight from the OS clipboard via pyperclip."""
import json
import os
import platform
import shlex
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import pyperclip

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
QUESTIONS_FILE = DATA_DIR / "questions.json"

PLATFORMS = ["chatgpt", "perplexity", "copilot", "ai_overviews"]
CAPTURE_METHODS = ["editor", "clipboard"]
SKIP_SENTINEL = "SKIP"
RESPONSE_MARKER = "===== WRITE YOUR RESPONSE BELOW THIS LINE ====="


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


def get_editor_command(path: Path) -> list[str]:
    """Build the command to open `path` for editing, blocking until it's closed.

    Honors $EDITOR if set. Otherwise falls back to notepad on Windows,
    TextEdit on macOS, and nano elsewhere.
    """
    editor = os.environ.get("EDITOR")
    if editor:
        return shlex.split(editor) + [str(path)]

    system = platform.system()
    if system == "Windows":
        return ["notepad", str(path)]
    if system == "Darwin":
        # -n opens a fresh TextEdit instance so -W only waits on that
        # instance, not on every other TextEdit window already open.
        return ["open", "-n", "-W", "-a", "TextEdit", str(path)]
    return ["nano", str(path)]


def capture_via_editor(question: dict) -> str | None:
    """Open a temp file for one question in the user's editor and return the saved response.

    Returns None if the saved body is empty or just SKIP.
    """
    header = (
        f"Q{question['id']} ({question['city']}, {question['persona']}, {question['type']}):\n"
        f"{question['question']}\n"
        "\n"
        "Paste the platform's full response below the marker line, then save\n"
        f"and close this file. Leave the body empty, or type {SKIP_SENTINEL}, to skip.\n"
        "\n"
        f"{RESPONSE_MARKER}\n"
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", prefix=f"aeo_q{question['id']}_", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(header)
        tmp_path = Path(tmp.name)

    try:
        command = get_editor_command(tmp_path)
        try:
            subprocess.run(command)
        except FileNotFoundError:
            raise RuntimeError(
                f"Could not launch editor command {command!r}. "
                "Set the EDITOR environment variable to a command that works on your system."
            )
        content = tmp_path.read_text(encoding="utf-8")
    finally:
        tmp_path.unlink(missing_ok=True)

    if RESPONSE_MARKER in content:
        content = content.split(RESPONSE_MARKER, 1)[1]
    response_text = content.strip()

    if not response_text or response_text == SKIP_SENTINEL:
        return None
    return response_text


def capture_via_clipboard(question: dict) -> str | None:
    """Wait for the user to copy the platform's response, then read it from the clipboard.

    Returns None if the user types SKIP instead of pressing Enter, or if
    the clipboard is empty.
    """
    prompt = (
        f"Copy the response (select it and Cmd/Ctrl+C), then press Enter here "
        f"(or type {SKIP_SENTINEL} to skip): "
    )
    choice = input(prompt).strip()
    if choice == SKIP_SENTINEL:
        return None

    try:
        response_text = pyperclip.paste().strip()
    except pyperclip.PyperclipException as e:
        raise RuntimeError(
            "Could not read the clipboard. On Linux, install xclip or xsel "
            f"and try again. ({e})"
        )

    if not response_text:
        return None
    return response_text


def capture_response(method: str, question: dict) -> str | None:
    """Dispatch to the chosen capture method for a single question."""
    if method == "clipboard":
        return capture_via_clipboard(question)
    return capture_via_editor(question)


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


def run(platform: str, method: str = "editor") -> None:
    """Run the manual capture loop for a single platform, resuming if partly done."""
    if platform not in PLATFORMS:
        raise ValueError(f"Unknown platform '{platform}'. Choose from: {PLATFORMS}")
    if method not in CAPTURE_METHODS:
        raise ValueError(f"Unknown capture method '{method}'. Choose from: {CAPTURE_METHODS}")

    questions = load_questions()
    today = date.today().isoformat()
    path = output_path(today, platform)

    results = load_existing_results(path)
    done_ids = {r["question_id"] for r in results}
    remaining = [q for q in questions if q["id"] not in done_ids]

    if not remaining:
        print(f"All {len(questions)} questions already captured for {platform} on {today}.")
        return

    print(f"\nCapturing responses for: {platform} (method: {method})")
    print(f"{len(done_ids)} already done, {len(remaining)} remaining.")
    if method == "clipboard":
        print("For each question, copy the response to your clipboard, then press Enter.\n")
    else:
        print("Each question opens in your editor. Paste the response, save, and close to continue.\n")

    try:
        for i, q in enumerate(remaining, start=1):
            print(f"[{i}/{len(remaining)}] Q{q['id']} ({q['city']}, {q['persona']}, {q['type']}): {q['question']}")
            response_text = capture_response(method, q)

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
            print("  Saved.")
    except KeyboardInterrupt:
        print("\nInterrupted. Progress saved; run again to resume.")

    print(f"\nDone. Saved {len(results)} results to {path}")


def main() -> None:
    """Standalone entry point: use CLI args if given, otherwise prompt for a platform.

    Usage: python manual_capture.py [platform] [method]
    """
    if len(sys.argv) > 1 and sys.argv[1] in PLATFORMS:
        platform = sys.argv[1]
    else:
        platform = select_platform()
    method = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] in CAPTURE_METHODS else "editor"
    run(platform, method)


if __name__ == "__main__":
    main()
