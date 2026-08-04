"""CLI entry point for the retrieval simulator (Task 3.1).

Separate from main.py by design — main.py and the rest of the Week 1
harness (src/gemini_runner.py, manual_capture.py, parser.py, report.py)
stay untouched.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from retrieval import embed, scoreboard, scraper


def main() -> None:
    arg_parser = argparse.ArgumentParser(
        prog="retrieval",
        description="Local RAG retrieval simulator for Swimingo vs. competitor content.",
    )
    subparsers = arg_parser.add_subparsers(dest="command", required=True)

    scrape_parser = subparsers.add_parser(
        "scrape", help="Scrape Swimingo + competitor pages and cache them locally."
    )
    scrape_parser.add_argument(
        "--force", action="store_true", help="Re-scrape pages even if a cached copy exists."
    )

    subparsers.add_parser(
        "embed", help="Chunk scraped pages, embed them, and store in ChromaDB."
    )

    subparsers.add_parser(
        "score", help="Query all 42 buyer questions and produce the retrieval scoreboard."
    )

    args = arg_parser.parse_args()

    if args.command == "scrape":
        scraper.run(force=args.force)
    elif args.command == "embed":
        embed.run()
    elif args.command == "score":
        scoreboard.run()


if __name__ == "__main__":
    main()
