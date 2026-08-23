"""Registry of profile pages to check. Add a new site by appending one Profile
here — no other code changes needed. Leave `url` as None for a site that
isn't live yet; it'll show up in the report as a clearly marked placeholder."""
from dataclasses import dataclass
from typing import Callable, Optional

from . import parsers

Parser = Callable[[str, str, object], parsers.ParsedNAP]


@dataclass
class Profile:
    key: str
    label: str
    url: Optional[str]
    parser: Optional[Parser] = None
    placeholder_note: Optional[str] = None


PROFILES: list[Profile] = [
    Profile(
        key="intently",
        label="Intently.co",
        url="https://intently.co/profiles/36925043",
        parser=parsers.parse_intently,
    ),
    Profile(
        key="yellowpages",
        label="Yellow Pages / 411.ca",
        url="https://www.yellowpages.ca/search/si/1/Swimingo/Canada",
        parser=parsers.parse_yellowpages,
    ),
    Profile(
        key="superprof",
        label="Superprof.ca",
        url=None,
        placeholder_note="URL not yet available — profile exists per Aakif but hasn't been captured yet.",
    ),
    Profile(
        key="chatterblock",
        label="ChatterBlock",
        url=None,
        placeholder_note="URL not yet available — listing submitted and under review, not live yet.",
    ),
]
