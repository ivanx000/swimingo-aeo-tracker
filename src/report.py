"""Builds a Markdown summary report from today's parsed results."""
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
QUESTIONS_FILE = DATA_DIR / "questions.json"


def load_questions_by_id() -> dict[int, dict]:
    """Load buyer questions keyed by id, for joining against parsed results."""
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)
    return {q["id"]: q for q in questions}


def load_parsed_entries(dates: list[str]) -> list[dict]:
    """Load and combine all *_parsed.json files for the given dates (a capture round
    can span more than one calendar day if manual capture takes a while)."""
    entries = []
    paths = sorted(path for d in dates for path in RESULTS_DIR.glob(f"{d}_*_parsed.json"))
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            entries.extend(json.load(f))
    return entries


def _pct(count: int, total: int) -> str:
    """Format count/total as a percentage, or 'n/a' if total is zero."""
    if total == 0:
        return "n/a"
    return f"{100 * count / total:.0f}%"


def visibility_by_platform(entries: list[dict]) -> dict[str, tuple[int, int]]:
    """Return {platform: (mentioned_count, total_count)}."""
    totals: dict[str, int] = defaultdict(int)
    mentioned: dict[str, int] = defaultdict(int)
    for e in entries:
        totals[e["platform"]] += 1
        if e["swimingo_mentioned"]:
            mentioned[e["platform"]] += 1
    return {p: (mentioned[p], totals[p]) for p in totals}


def visibility_by_field(
    entries: list[dict], questions_by_id: dict[int, dict], field: str
) -> dict[str, tuple[int, int]]:
    """Return {field_value: (mentioned_count, total_count)} for a question field (type/persona)."""
    totals: dict[str, int] = defaultdict(int)
    mentioned: dict[str, int] = defaultdict(int)
    for e in entries:
        question = questions_by_id.get(e["question_id"])
        if not question:
            continue
        value = question[field]
        totals[value] += 1
        if e["swimingo_mentioned"]:
            mentioned[value] += 1
    return {v: (mentioned[v], totals[v]) for v in totals}


def competitor_leaderboard(entries: list[dict]) -> tuple[Counter, dict[str, Counter]]:
    """Return (overall mention counts, {platform: mention counts}) for competitors."""
    overall: Counter = Counter()
    per_platform: dict[str, Counter] = defaultdict(Counter)
    for e in entries:
        for comp in e["competitors_mentioned"]:
            overall[comp] += 1
            per_platform[e["platform"]][comp] += 1
    return overall, per_platform


def top_cited_domains(entries: list[dict], limit: int = 15) -> list[tuple[str, int]]:
    """Return the most frequently cited domains across all entries."""
    counts: Counter = Counter()
    for e in entries:
        for domain in e["cited_domains"]:
            counts[domain] += 1
    return counts.most_common(limit)


def find_gaps(entries: list[dict], questions_by_id: dict[int, dict]) -> list[dict]:
    """Find questions where Swimingo was not mentioned but a competitor was."""
    gaps = []
    for e in entries:
        if not e["swimingo_mentioned"] and e["competitors_mentioned"]:
            question = questions_by_id.get(e["question_id"], {})
            gaps.append(
                {
                    "question_id": e["question_id"],
                    "platform": e["platform"],
                    "question": question.get("question", "?"),
                    "competitors_mentioned": e["competitors_mentioned"],
                }
            )
    return gaps


def build_report(dates: list[str]) -> str:
    """Build the full Markdown report as a string."""
    questions_by_id = load_questions_by_id()
    entries = load_parsed_entries(dates)

    date_label = dates[0] if len(dates) == 1 else f"{dates[0]} to {dates[-1]}"
    lines = [f"# Swimingo AEO Visibility Report — {date_label}", ""]

    if not entries:
        lines.append("No parsed results found for these dates.")
        return "\n".join(lines)

    total_mentioned = sum(1 for e in entries if e["swimingo_mentioned"])
    lines.append(
        f"**Overall Swimingo visibility: {_pct(total_mentioned, len(entries))} "
        f"({total_mentioned}/{len(entries)} responses)**"
    )
    lines.append("")

    lines.append("## Visibility by platform")
    for platform, (mentioned, total) in sorted(visibility_by_platform(entries).items()):
        lines.append(f"- **{platform}**: {_pct(mentioned, total)} ({mentioned}/{total})")
    lines.append("")

    lines.append("## Visibility by question type")
    for qtype, (mentioned, total) in sorted(visibility_by_field(entries, questions_by_id, "type").items()):
        lines.append(f"- **{qtype}**: {_pct(mentioned, total)} ({mentioned}/{total})")
    lines.append("")

    lines.append("## Visibility by persona")
    for persona, (mentioned, total) in sorted(
        visibility_by_field(entries, questions_by_id, "persona").items()
    ):
        lines.append(f"- **{persona}**: {_pct(mentioned, total)} ({mentioned}/{total})")
    lines.append("")

    lines.append("## Competitor leaderboard")
    overall, per_platform = competitor_leaderboard(entries)
    if overall:
        lines.append("Overall mentions:")
        for comp, count in overall.most_common():
            lines.append(f"- {comp}: {count}")
        lines.append("")
        lines.append("By platform:")
        for platform in sorted(per_platform):
            breakdown = ", ".join(f"{comp}: {count}" for comp, count in per_platform[platform].most_common())
            lines.append(f"- **{platform}**: {breakdown}")
    else:
        lines.append("No competitor mentions found.")
    lines.append("")

    lines.append("## Top cited domains")
    domains = top_cited_domains(entries)
    if domains:
        for domain, count in domains:
            lines.append(f"- {domain}: {count}")
    else:
        lines.append("No domains found.")
    lines.append("")

    lines.append("## Gaps (Swimingo absent, competitor present)")
    gaps = find_gaps(entries, questions_by_id)
    if gaps:
        for gap in gaps:
            comps = ", ".join(gap["competitors_mentioned"])
            lines.append(
                f"- [{gap['platform']}] Q{gap['question_id']}: \"{gap['question']}\" — mentioned: {comps}"
            )
    else:
        lines.append("No gaps found — no question had a competitor mentioned without Swimingo.")
    lines.append("")

    return "\n".join(lines)


def run(dates: list[str] | None = None) -> None:
    """Generate a summary report for the given dates (default: today), save it,
    and print a short version to stdout."""
    dates = dates or [date.today().isoformat()]
    report_text = build_report(dates)

    name_part = dates[0] if len(dates) == 1 else f"{dates[0]}_to_{dates[-1]}"
    report_path = RESULTS_DIR / f"{name_part}_summary_report.md"
    RESULTS_DIR.mkdir(exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    print(report_text)
    print(f"\nFull report saved to {report_path}")


if __name__ == "__main__":
    run()
