"""Per-site parsers. Each takes the fetched HTML (+ the page URL and a requests
Session for any follow-up fetches) and returns a ParsedNAP.

Confirmed via manual investigation (2026-08-22) that neither site requires JS
rendering: Intently's "not activated" message and Yellow Pages' phone/name
fields are both present in the raw HTML on first load, so requests +
BeautifulSoup is sufficient (no Playwright needed here).
"""
import re
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .http import fetch_html

INACTIVE_MARKERS = (
    "not fully activated",
    "cannot be shown publicly",
)


@dataclass
class ParsedNAP:
    name: str | None = None
    phone: str | None = None
    website: str | None = None
    inactive: bool = False
    inactive_reason: str | None = None
    source_url: str | None = None


def parse_intently(html: str, url: str, session: requests.Session) -> ParsedNAP:
    soup = BeautifulSoup(html, "lxml")
    body_text = soup.get_text(" ", strip=True).lower()

    if any(marker in body_text for marker in INACTIVE_MARKERS):
        return ParsedNAP(
            inactive=True,
            inactive_reason=(
                "Profile page reports the service provider's account as not "
                "fully activated — no name/phone/site content is published."
            ),
            source_url=url,
        )

    # Best-effort generic extraction in case the profile becomes active later.
    # The structure of an active Intently profile hasn't been observed yet, so
    # this falls back to loose text/attribute matching rather than specific
    # selectors.
    title_tag = soup.find("title")
    name = title_tag.get_text(strip=True) if title_tag and title_tag.get_text(strip=True) else None

    phone = None
    phone_match = re.search(r"(\+?1?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})", soup.get_text(" ", strip=True))
    if phone_match:
        phone = phone_match.group(1)

    website = None
    link = soup.find("a", href=re.compile(r"swimingo\.com", re.I))
    if link:
        website = link["href"]
    else:
        website_match = re.search(r"(https?://[^\s\"'<>]*swimingo\.com[^\s\"'<>]*)", html, re.I)
        if website_match:
            website = website_match.group(1)

    return ParsedNAP(name=name, phone=phone, website=website, source_url=url)


def _extract_yp_website(soup: BeautifulSoup) -> str | None:
    website_link = soup.select_one(".mlr__item--website a[href]")
    if website_link and website_link.get("href"):
        return website_link["href"]
    return None


def _extract_yp_phone_from_detail(soup: BeautifulSoup) -> str | None:
    for script in soup.find_all("script", type="application/ld+json"):
        match = re.search(r'"telephone"\s*:\s*"([^"]+)"', script.get_text())
        if match:
            return match.group(1)
    submenu_phone = soup.select_one(".mlr__submenu .mlr__sub-text")
    if submenu_phone:
        return submenu_phone.get_text(strip=True)
    return None


def parse_yellowpages(html: str, url: str, session: requests.Session) -> ParsedNAP:
    soup = BeautifulSoup(html, "lxml")

    # Pick the first result card whose name matches "Swimingo" (defensive
    # against the search ever returning more than one listing).
    name = None
    detail_url = None
    for name_tag in soup.select("a.jsListingName"):
        text = name_tag.get_text(strip=True)
        if "swimingo" in text.lower():
            name = text
            detail_url = name_tag.get("href")
            break

    card = None
    if detail_url:
        card = soup.select_one(f'a.jsListingName[href="{detail_url}"]')
        card = card.find_parent("div", class_="listing__content__wrap--flexed") if card else None

    phone = None
    phone_tag = (card or soup).select_one("a.jsMlrMenu[data-phone]")
    if phone_tag:
        phone = phone_tag.get("data-phone")

    website = _extract_yp_website(card or soup)

    if detail_url:
        detail_url = urljoin(url, detail_url.split("?")[0])

    # Yellow Pages' search-results card doesn't carry a website field for this
    # listing; fall back to the full business detail page, which is where a
    # site (if on file) or a more complete phone entry would live.
    if (website is None or phone is None) and detail_url:
        try:
            detail_html = fetch_html(detail_url, session)
            detail_soup = BeautifulSoup(detail_html, "lxml")
            if website is None:
                website = _extract_yp_website(detail_soup)
            if phone is None:
                phone = _extract_yp_phone_from_detail(detail_soup)
        except requests.RequestException:
            pass  # Fall through with whatever was found on the search page.

    return ParsedNAP(name=name, phone=phone, website=website, source_url=detail_url or url)
