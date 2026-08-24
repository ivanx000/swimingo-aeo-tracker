"""Diffs two capture runs (e.g. Week 1 baseline vs. a later week) per-question and
per-platform: visibility deltas, newly-appearing/lost Swimingo mentions, and
citation source changes."""
import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
PARSED_DIR = RESULTS_DIR / "parsed"
REPORTS_DIR = RESULTS_DIR / "reports"
QUESTIONS_FILE = DATA_DIR / "questions.json"

SWIMINGO_DOMAIN = "swimingo.com"

METHODOLOGY_LIMITATIONS = """\
- **Location (primary suspected confound):** the two runs were captured from
  different physical locations — Toronto for Week 1, Bancroft for Week 6.
  This could plausibly affect any platform that uses IP-based geolocation for
  local-intent queries, not just Google AI Overviews — search-grounded
  platforms may weight "what's near the searcher" even when a city is named
  explicitly in the question text. Platform-level visibility deltas below
  should NOT be read as clean causal evidence of Week 2-5 content/technical
  changes without this caveat in mind.
- **Account history (minor, not a confound between these two runs):**
  Perplexity and Copilot both used brand-new accounts with no prior
  interaction history in both Week 1 and Week 6, so account-history-based
  personalization drift is not a meaningful difference between the two runs
  — both started from the same blank-slate state. Different email addresses
  were used each time, and Perplexity's self-reported age field may have
  differed between runs (uncertain in Week 1, "23" in Week 6); these are
  documented for completeness but their likely impact is small.
- **What's less affected:** question-type-level findings (e.g. cost-question
  visibility) aren't tied to a single platform's personalization/location
  behavior, so they can be read with more confidence than platform-level
  deltas — though the same caveat still applies in general.
- **Forward-looking note for Week 8:** control for location and account
  consistency this time (same location, same or comparably-aged accounts)
  to get a cleaner final comparison.
"""


def load_questions_by_id() -> dict[int, dict]:
    """Load buyer questions keyed by id, for joining against parsed results."""
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)
    return {q["id"]: q for q in questions}


def load_parsed_entries(dates: list[str]) -> list[dict]:
    """Load and combine all *_parsed.json files for the given dates (a capture round
    can span more than one calendar day if manual capture takes a while)."""
    entries = []
    paths = sorted(path for d in dates for path in PARSED_DIR.glob(f"{d}_*_parsed.json"))
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            entries.extend(json.load(f))
    return entries


def index_by_platform_question(entries: list[dict]) -> dict[tuple[str, int], dict]:
    """Return {(platform, question_id): entry} for quick lookup during diffing."""
    return {(e["platform"], e["question_id"]): e for e in entries}


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


def diff_visibility(
    baseline_entries: list[dict], current_entries: list[dict]
) -> list[dict]:
    """Return per-platform visibility for both runs plus the delta, sorted by platform."""
    baseline_vis = visibility_by_platform(baseline_entries)
    current_vis = visibility_by_platform(current_entries)
    platforms = sorted(set(baseline_vis) | set(current_vis))

    rows = []
    for platform in platforms:
        b_mentioned, b_total = baseline_vis.get(platform, (0, 0))
        c_mentioned, c_total = current_vis.get(platform, (0, 0))
        rows.append(
            {
                "platform": platform,
                "baseline_mentioned": b_mentioned,
                "baseline_total": b_total,
                "current_mentioned": c_mentioned,
                "current_total": c_total,
                "delta": c_mentioned - b_mentioned,
            }
        )
    return rows


def diff_mentions(
    baseline_index: dict[tuple[str, int], dict],
    current_index: dict[tuple[str, int], dict],
    questions_by_id: dict[int, dict],
) -> tuple[list[dict], list[dict]]:
    """Return (newly_appearing, newly_lost) Swimingo mentions: questions where
    swimingo_mentioned flipped False->True (appearing) or True->False (lost)
    between baseline and current, keyed by (platform, question_id)."""
    newly_appearing = []
    newly_lost = []

    keys = sorted(set(baseline_index) | set(current_index))
    for platform, question_id in keys:
        baseline_entry = baseline_index.get((platform, question_id))
        current_entry = current_index.get((platform, question_id))
        if baseline_entry is None or current_entry is None:
            continue

        was_mentioned = baseline_entry["swimingo_mentioned"]
        is_mentioned = current_entry["swimingo_mentioned"]
        if was_mentioned == is_mentioned:
            continue

        question = questions_by_id.get(question_id, {})
        row = {
            "platform": platform,
            "question_id": question_id,
            "question": question.get("question", "?"),
        }
        if is_mentioned:
            newly_appearing.append(row)
        else:
            newly_lost.append(row)

    return newly_appearing, newly_lost


def diff_citations(
    baseline_index: dict[tuple[str, int], dict],
    current_index: dict[tuple[str, int], dict],
    questions_by_id: dict[int, dict],
) -> list[dict]:
    """Return, for every (platform, question) present in both runs where the set of
    cited domains changed, the domains added and dropped, flagging swimingo.com
    and competitor domains specifically."""
    changes = []
    keys = sorted(set(baseline_index) & set(current_index))
    for platform, question_id in keys:
        baseline_entry = baseline_index[(platform, question_id)]
        current_entry = current_index[(platform, question_id)]

        baseline_domains = set(baseline_entry["cited_domains"])
        current_domains = set(current_entry["cited_domains"])
        if baseline_domains == current_domains:
            continue

        added = sorted(current_domains - baseline_domains)
        dropped = sorted(baseline_domains - current_domains)
        question = questions_by_id.get(question_id, {})
        changes.append(
            {
                "platform": platform,
                "question_id": question_id,
                "question": question.get("question", "?"),
                "domains_added": added,
                "domains_dropped": dropped,
                "swimingo_newly_cited": SWIMINGO_DOMAIN in added,
                "swimingo_newly_dropped": SWIMINGO_DOMAIN in dropped,
            }
        )
    return changes


def build_diff(
    baseline_dates: list[str], current_dates: list[str]
) -> dict:
    """Build the full structured diff between a baseline run and a current run."""
    questions_by_id = load_questions_by_id()
    baseline_entries = load_parsed_entries(baseline_dates)
    current_entries = load_parsed_entries(current_dates)
    baseline_index = index_by_platform_question(baseline_entries)
    current_index = index_by_platform_question(current_entries)

    visibility = diff_visibility(baseline_entries, current_entries)
    newly_appearing, newly_lost = diff_mentions(baseline_index, current_index, questions_by_id)
    citation_changes = diff_citations(baseline_index, current_index, questions_by_id)

    return {
        "baseline_dates": baseline_dates,
        "current_dates": current_dates,
        "visibility_by_platform": visibility,
        "newly_appearing_mentions": newly_appearing,
        "newly_lost_mentions": newly_lost,
        "citation_changes": citation_changes,
        "methodology_limitations": METHODOLOGY_LIMITATIONS,
    }


def _format_delta(delta: int) -> str:
    return f"+{delta}" if delta > 0 else str(delta)


def render_markdown(diff: dict) -> str:
    """Render the structured diff as a Markdown report string."""
    baseline_label = "-".join(diff["baseline_dates"])
    current_label = "-".join(diff["current_dates"])
    lines = [f"# Swimingo AEO Diff — {baseline_label} (baseline) vs. {current_label}", ""]

    lines.append("## Methodology Limitations")
    lines.append("")
    lines.append(METHODOLOGY_LIMITATIONS)
    lines.append("")

    lines.append("## Visibility by platform (baseline -> current)")
    for row in diff["visibility_by_platform"]:
        lines.append(
            f"- **{row['platform']}**: {row['baseline_mentioned']}/{row['baseline_total']} "
            f"-> {row['current_mentioned']}/{row['current_total']}, "
            f"{_format_delta(row['delta'])}"
        )
    lines.append("")

    lines.append("## Newly-appearing Swimingo mentions (absent in baseline, present in current)")
    if diff["newly_appearing_mentions"]:
        for row in diff["newly_appearing_mentions"]:
            lines.append(f"- [{row['platform']}] Q{row['question_id']}: \"{row['question']}\"")
    else:
        lines.append("None.")
    lines.append("")

    lines.append("## Newly-lost Swimingo mentions (present in baseline, absent in current)")
    if diff["newly_lost_mentions"]:
        for row in diff["newly_lost_mentions"]:
            lines.append(f"- [{row['platform']}] Q{row['question_id']}: \"{row['question']}\"")
    else:
        lines.append("None.")
    lines.append("")

    lines.append("## Citation source changes")
    if diff["citation_changes"]:
        for row in diff["citation_changes"]:
            flags = []
            if row["swimingo_newly_cited"]:
                flags.append("swimingo.com newly cited")
            if row["swimingo_newly_dropped"]:
                flags.append("swimingo.com newly dropped")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            added = ", ".join(row["domains_added"]) or "none"
            dropped = ", ".join(row["domains_dropped"]) or "none"
            lines.append(
                f"- [{row['platform']}] Q{row['question_id']}: \"{row['question']}\"{flag_str}\n"
                f"  - added: {added}\n"
                f"  - dropped: {dropped}"
            )
    else:
        lines.append("No citation source changes found.")
    lines.append("")

    return "\n".join(lines)


def run(
    baseline_dates: list[str], current_dates: list[str], label: str | None = None
) -> None:
    """Build the diff, save both .md and .json versions to results/reports/, and
    print the Markdown report to stdout."""
    diff = build_diff(baseline_dates, current_dates)
    report_text = render_markdown(diff)

    name_part = label or f"{'-'.join(baseline_dates)}_vs_{'-'.join(current_dates)}"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    md_path = REPORTS_DIR / f"{name_part}_diff.md"
    json_path = REPORTS_DIR / f"{name_part}_diff.json"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(diff, f, indent=2, ensure_ascii=False)

    print(report_text)
    print(f"\nFull diff saved to {md_path} and {json_path}")


WEEK1_DATES = ["2026-07-23", "2026-07-24"]
WEEK6_DATES = ["2026-08-23", "2026-08-24"]


if __name__ == "__main__":
    run(WEEK1_DATES, WEEK6_DATES, label="week1_vs_week6")
