"""CLI entry point for the Swimingo AEO tracker."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import gemini_runner
import manual_capture
import parser as result_parser
import report


def main() -> None:
    """Parse CLI args and dispatch to the matching subcommand."""
    arg_parser = argparse.ArgumentParser(
        prog="swimingo-aeo-tracker",
        description="Track Swimingo's visibility across AI answer engines.",
    )
    subparsers = arg_parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("run-gemini", help="Ask Gemini every buyer question and save raw responses.")

    capture_parser = subparsers.add_parser("capture", help="Manually capture responses for one platform.")
    capture_parser.add_argument("platform", choices=manual_capture.PLATFORMS)
    capture_parser.add_argument(
        "--method",
        choices=manual_capture.CAPTURE_METHODS,
        default="editor",
        help="How to capture each response (default: editor).",
    )

    dates_help = (
        "Comma-separated dates (YYYY-MM-DD) to include, for a capture round that "
        "spanned more than one day. Default: today only."
    )
    parse_parser = subparsers.add_parser("parse", help="Parse raw result files.")
    parse_parser.add_argument("--dates", help=dates_help)

    report_parser = subparsers.add_parser("report", help="Generate a summary report.")
    report_parser.add_argument("--dates", help=dates_help)

    subparsers.add_parser("run-all", help="Run Gemini, then parse, then report (skips manual capture).")

    args = arg_parser.parse_args()

    if args.command == "run-gemini":
        gemini_runner.run()
    elif args.command == "capture":
        manual_capture.run(args.platform, args.method)
    elif args.command == "parse":
        dates = args.dates.split(",") if args.dates else None
        if dates:
            result_parser.parse_dates(dates)
        else:
            result_parser.parse_today()
    elif args.command == "report":
        dates = args.dates.split(",") if args.dates else None
        report.run(dates)
    elif args.command == "run-all":
        gemini_runner.run()
        result_parser.parse_today()
        report.run()


if __name__ == "__main__":
    main()
