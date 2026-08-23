"""CLI entry point for the NAP consistency checker (Task 5.1).

Fetches each profile page listed in src/nap/profiles.py, diffs its published
name/phone/website against the canonical values in src/nap/constants.py, and
prints + saves a report. Re-run this any time to catch drift (per Task 5.1,
re-run in Week 8).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from nap import checker


def main() -> None:
    checker.run()


if __name__ == "__main__":
    main()
