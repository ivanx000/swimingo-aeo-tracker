"""Extracts Swimingo/competitor mentions and cited domains from raw AI responses."""
import json
import re
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
COMPETITORS_FILE = DATA_DIR / "competitors.json"

SWIMINGO_DOMAIN = "swimingo.com"
URL_PATTERN = re.compile(r"https?://[^\s)\]}>\"']+|www\.[^\s)\]}>\"']+")


def load_competitors() -> list[dict]:
    """Load known competitors from data/competitors.json."""
    with open(COMPETITORS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _extract_domain(url: str) -> str:
    """Strip protocol, 'www.', path, and trailing punctuation from a URL."""
    domain = re.sub(r"^https?://", "", url)
    domain = re.sub(r"^www\.", "", domain)
    domain = domain.split("/")[0]
    domain = domain.rstrip(".,;:)")
    return domain.lower()


def check_swimingo_mentioned(text: str) -> bool:
    """Case-insensitive search for 'Swimingo' anywhere in the text."""
    return bool(re.search(r"swimingo", text, re.IGNORECASE))


def find_competitors_mentioned(text: str, competitors: list[dict]) -> list[str]:
    """Return names of competitors whose name appears (case-insensitive) in the text."""
    mentioned = []
    for comp in competitors:
        if re.search(re.escape(comp["name"]), text, re.IGNORECASE):
            mentioned.append(comp["name"])
    return mentioned


def find_cited_domains(text: str, competitors: list[dict]) -> list[str]:
    """Find domains cited via URL, plus any known domains mentioned as plain text."""
    domains = set()

    for match in URL_PATTERN.findall(text):
        domains.add(_extract_domain(match))

    known_domains = [SWIMINGO_DOMAIN]
    for comp in competitors:
        known_domains.extend(comp["domains"])

    for known in known_domains:
        if re.search(re.escape(known), text, re.IGNORECASE):
            domains.add(known.lower())

    return sorted(domains)


def parse_entry(entry: dict, competitors: list[dict]) -> dict:
    """Return a copy of a raw result entry with parsed fields added."""
    text = entry.get("raw_response", "")
    parsed = dict(entry)
    parsed["swimingo_mentioned"] = check_swimingo_mentioned(text)
    parsed["competitors_mentioned"] = find_competitors_mentioned(text, competitors)
    parsed["cited_domains"] = find_cited_domains(text, competitors)
    return parsed


def parse_file(raw_path: Path) -> Path:
    """Parse a single raw results file and save the parsed version alongside it."""
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_entries = json.load(f)

    competitors = load_competitors()
    parsed_entries = [parse_entry(entry, competitors) for entry in raw_entries]

    parsed_path = Path(str(raw_path).replace("_raw.json", "_parsed.json"))
    with open(parsed_path, "w", encoding="utf-8") as f:
        json.dump(parsed_entries, f, indent=2, ensure_ascii=False)

    return parsed_path


def parse_dates(dates: list[str]) -> list[Path]:
    """Parse every *_raw.json file for the given dates (a capture round can span more
    than one calendar day if manual capture takes a while)."""
    raw_files = sorted(
        path for d in dates for path in RESULTS_DIR.glob(f"{d}_*_raw.json")
    )

    if not raw_files:
        print(f"No raw result files found for {', '.join(dates)}.")
        return []

    parsed_paths = []
    for raw_path in raw_files:
        parsed_path = parse_file(raw_path)
        print(f"Parsed {raw_path.name} -> {parsed_path.name}")
        parsed_paths.append(parsed_path)

    return parsed_paths


def parse_today() -> list[Path]:
    """Parse every *_raw.json file for today's date."""
    return parse_dates([date.today().isoformat()])


if __name__ == "__main__":
    parse_today()
