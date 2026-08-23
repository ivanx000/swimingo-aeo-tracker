"""Task 5.1: NAP (name/phone/site) consistency checker.

Fetches each profile URL in profiles.PROFILES, extracts what it can find for
name/phone/website, normalizes, and diffs against the canonical values in
constants.py. Re-run this any time (including Week 8) to catch drift.
"""
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import requests

from . import constants
from .normalize import normalize_name, normalize_phone, normalize_website
from .http import fetch_html
from .profiles import PROFILES, Profile

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results" / "nap"

FIELD_SPECS = [
    ("name", constants.CANONICAL_NAME, normalize_name),
    ("phone", constants.CANONICAL_PHONE, normalize_phone),
    ("website", constants.CANONICAL_WEBSITE, normalize_website),
]


@dataclass
class FieldResult:
    field: str
    canonical: str
    found: str | None
    status: str  # PASS, FAIL, NOT_FOUND


@dataclass
class ProfileResult:
    key: str
    label: str
    url: str | None
    status: str  # OK, INACTIVE, PLACEHOLDER, ERROR
    fields: list[FieldResult]
    note: str | None = None


def _compare_field(field_name: str, canonical_raw: str, normalize_fn, found_raw: str | None) -> FieldResult:
    if found_raw is None:
        return FieldResult(field_name, canonical_raw, None, "NOT_FOUND")
    is_match = normalize_fn(found_raw) == normalize_fn(canonical_raw)
    return FieldResult(field_name, canonical_raw, found_raw, "PASS" if is_match else "FAIL")


def check_profile(profile: Profile) -> ProfileResult:
    if profile.url is None:
        return ProfileResult(profile.key, profile.label, None, "PLACEHOLDER", [], note=profile.placeholder_note)

    session = requests.Session()
    try:
        html = fetch_html(profile.url, session)
    except requests.RequestException as exc:
        return ProfileResult(profile.key, profile.label, profile.url, "ERROR", [], note=f"Fetch failed: {exc}")

    parsed = profile.parser(html, profile.url, session)

    if parsed.inactive:
        return ProfileResult(
            profile.key, profile.label, profile.url, "INACTIVE", [], note=parsed.inactive_reason
        )

    fields = [
        _compare_field(name, canonical, normalize_fn, getattr(parsed, name))
        for name, canonical, normalize_fn in FIELD_SPECS
    ]
    return ProfileResult(profile.key, profile.label, parsed.source_url or profile.url, "OK", fields)


def check_all() -> list[ProfileResult]:
    return [check_profile(profile) for profile in PROFILES]


def format_report(results: list[ProfileResult]) -> str:
    lines = [
        "# NAP Consistency Report",
        "",
        f"Canonical: **{constants.CANONICAL_NAME}** | "
        f"**{constants.CANONICAL_PHONE}** | **{constants.CANONICAL_WEBSITE}**",
        "",
    ]

    for result in results:
        lines.append(f"## {result.label}")
        lines.append(f"URL: {result.url or '(not yet available)'}")

        if result.status == "PLACEHOLDER":
            lines.append(f"Status: **NOT YET AVAILABLE** — {result.note}")
        elif result.status == "ERROR":
            lines.append(f"Status: **ERROR** — {result.note}")
        elif result.status == "INACTIVE":
            lines.append(f"Status: **INACTIVE** — {result.note}")
        else:
            for field in result.fields:
                if field.status == "PASS":
                    lines.append(f"- {field.field}: PASS")
                elif field.status == "NOT_FOUND":
                    lines.append(f"- {field.field}: NOT_FOUND (canonical: \"{field.canonical}\")")
                else:
                    lines.append(
                        f"- {field.field}: FAIL — found \"{field.found}\", expected \"{field.canonical}\""
                    )
        lines.append("")

    return "\n".join(lines)


def run(save: bool = True) -> list[ProfileResult]:
    results = check_all()
    report_text = format_report(results)
    print(report_text)

    if save:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        report_path = RESULTS_DIR / f"{today}_nap_report.md"
        json_path = RESULTS_DIR / f"{today}_nap_report.json"
        report_path.write_text(report_text, encoding="utf-8")
        json_path.write_text(json.dumps([asdict(r) for r in results], indent=2), encoding="utf-8")
        print(f"Saved report to {report_path}")
        print(f"Saved raw results to {json_path}")

    return results
