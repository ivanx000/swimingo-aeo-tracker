"""Scrapes Swimingo's own pages plus competitor pages for the retrieval simulator.

Swimingo URLs are discovered from swimingo.com/sitemap.xml at run time (no
hardcoded list, so new cities/posts are picked up automatically). Competitor
URLs come from data/competitor_urls.json.
"""
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError, Page, sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
SCRAPED_DIR = REPO_ROOT / "scraped_content"

SWIMINGO_SITEMAP_URL = "https://swimingo.com/sitemap.xml"
COMPETITOR_URLS_FILE = DATA_DIR / "competitor_urls.json"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
REQUEST_TIMEOUT = 15
PAGE_LOAD_TIMEOUT_MS = 20_000
RENDER_WAIT_MS = 2_000  # let client-side rendered pages (e.g. Swimingo's blog) hydrate
DELAY_BETWEEN_REQUESTS = 1.0
THIN_CONTENT_WORD_THRESHOLD = 100


def fetch_swimingo_urls() -> dict:
    """Fetch and parse swimingo.com/sitemap.xml, split into city pages and blog posts."""
    resp = requests.get(SWIMINGO_SITEMAP_URL, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    root = ElementTree.fromstring(resp.content)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    all_urls = [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]

    city_pages = [u for u in all_urls if "/swim-lessons/" in urlparse(u).path]
    blog_posts = [u for u in all_urls if re.search(r"/blog/\d+$", urlparse(u).path)]

    return {"city_pages": sorted(city_pages), "blog_posts": sorted(blog_posts)}


def load_competitor_urls() -> list:
    """Homepage + any per-city page URLs discovered from each competitor's own sitemap.

    city_pages entries were captured into data/competitor_urls.json by a one-off
    investigation (see the file's "note" field), not re-discovered on every run —
    re-crawling 13 external sitemaps on every scrape would be needless load on
    those sites for URLs that don't change often.
    """
    with open(COMPETITOR_URLS_FILE) as f:
        data = json.load(f)

    urls = []
    for c in data["competitors"]:
        urls.append(c["url"])
        urls.extend(c.get("city_pages", {}).values())
    return sorted(set(urls))


def slug_for_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    slug = path.replace("/", "__") if path else "home"
    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", slug)
    return slug


def normalize_domain(domain: str) -> str:
    """Strip a leading www. so the same site isn't split into two domains.

    Some competitor URLs (from their own sitemaps) include www., others
    don't, for the same underlying site — e.g. aquastarcanada.com and
    www.aquastarcanada.com. Without this, aggregate counts by domain
    (e.g. "who beats us most") would silently undercount that competitor.
    """
    return domain[4:] if domain.startswith("www.") else domain


DEDUPE_MAX_BLOCK_LEN = 80
DEDUPE_LOOKBACK = 3


def _dedupe_adjacent_blocks(blocks: list) -> list:
    """Collapse a block into a nearby one when one is a prefix of (or equal to) the other.

    Catches two patterns seen in the scraped pages: an "eyebrow" label
    immediately followed by a heading that repeats it (e.g. a
    <p>"Private Swim Lessons"</p> right before an
    <h1>"Private Swim Lessons in Toronto"</h1>), and a blog title that
    repeats itself around a byline/read-time line (title, "June 7, 2025 -
    5 min read", title again as the H1). Both are separate DOM elements
    that read as a stutter once flattened to plain text, which would
    double-count those words in the embedding. Looks back a few blocks
    (not just the immediately preceding one) so the byline-in-between case
    is still caught, and stays bounded to short strings so it doesn't
    touch ordinary body sentences that coincidentally share a prefix.
    """
    result = []
    for block in blocks:
        if len(block) <= DEDUPE_MAX_BLOCK_LEN:
            block_l = block.lower()
            match_idx = None
            for i in range(max(0, len(result) - DEDUPE_LOOKBACK), len(result)):
                prev = result[i]
                if len(prev) > DEDUPE_MAX_BLOCK_LEN:
                    continue
                prev_l = prev.lower()
                if block_l == prev_l or block_l.startswith(prev_l + " ") or prev_l.startswith(block_l + " "):
                    match_idx = i
                    break
            if match_idx is not None:
                if len(block) > len(result[match_idx]):
                    result[match_idx] = block  # keep the longer/more complete version
                continue
        result.append(block)
    return result


def extract_main_text(html: str) -> str:
    """Strip chrome/noise and return the remaining body text, deduped.

    Tried preferring <main>/<article> first, but on Swimingo's own site
    <article> tags wrap individual FAQ accordion items rather than the
    page body, and Tailwind utility classes like "place-content-inherit"
    false-positive against a "content" id/class regex. Stripping noise
    and taking the rest of <body> is more reliable across differently
    structured sites than guessing at a single "main content" container.
    """
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg"]):
        tag.decompose()

    root = soup.body or soup
    blocks = _dedupe_adjacent_blocks(list(root.stripped_strings))
    text = " ".join(blocks)
    return re.sub(r"\s+", " ", text).strip()


def fetch_rendered_html(page: Page, url: str) -> str | None:
    """Load a URL in headless Chromium and return the post-render HTML.

    Some Swimingo pages (blog posts) are pure client-side rendered — plain
    requests only sees a "Loading..." shell. Rendering with a real browser
    fixes that, and as a side effect presents a normal browser fingerprint
    that plain requests didn't for a couple of competitor sites behind bot
    protection.
    """
    try:
        page.goto(url, timeout=PAGE_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")
        page.wait_for_timeout(RENDER_WAIT_MS)
        return page.content()
    except PlaywrightError as exc:
        print(f"  FAILED  {url}  ({exc.message.splitlines()[0]})")
        return None


def cache_paths(category: str, url: str) -> tuple[Path, Path]:
    domain = urlparse(url).netloc
    subdir = SCRAPED_DIR / category / domain
    slug = slug_for_url(url)
    return subdir / f"{slug}.html", subdir / f"{slug}.json"


def scrape_and_cache(page: Page, url: str, category: str, force: bool = False) -> dict:
    """Scrape one URL, cache raw HTML + cleaned text/metadata, return the record.

    `category` is "swimingo" or "competitors" and becomes both the cache
    subfolder and the source tag stored in the metadata.
    """
    html_path, json_path = cache_paths(category, url)

    if json_path.exists() and not force:
        with open(json_path) as f:
            return json.load(f)

    html = fetch_rendered_html(page, url)
    if html is None:
        return {"url": url, "domain": urlparse(url).netloc, "category": category, "error": "fetch_failed"}

    text = extract_main_text(html)
    word_count = len(text.split())

    record = {
        "url": url,
        "domain": urlparse(url).netloc,
        "category": category,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "word_count": word_count,
        "text": text,
    }

    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    json_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    if word_count < THIN_CONTENT_WORD_THRESHOLD:
        print(f"  WARNING thin content ({word_count} words) at {url} — page may be JS-rendered")

    return record


def run(force: bool = False) -> dict:
    swimingo_urls = fetch_swimingo_urls()
    competitor_urls = load_competitor_urls()

    print(f"Swimingo: {len(swimingo_urls['city_pages'])} city pages, {len(swimingo_urls['blog_posts'])} blog posts")
    print(f"Competitors: {len(competitor_urls)} URLs")

    records = []
    thin = []
    failed = []

    jobs = (
        [(u, "swimingo") for u in swimingo_urls["city_pages"] + swimingo_urls["blog_posts"]]
        + [(u, "competitors") for u in competitor_urls]
    )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            user_agent=REQUEST_HEADERS["User-Agent"], extra_http_headers=REQUEST_HEADERS
        )
        page = context.new_page()

        for i, (url, category) in enumerate(jobs):
            was_cached = cache_paths(category, url)[1].exists() and not force
            print(f"[{i + 1}/{len(jobs)}] {url}{' (cached)' if was_cached else ''}")

            try:
                record = scrape_and_cache(page, url, category, force=force)
            except Exception as exc:
                print(f"  FAILED  {url}  (unexpected: {exc})")
                record = {"url": url, "domain": urlparse(url).netloc, "category": category, "error": "unexpected_exception"}
            records.append(record)

            if record.get("error"):
                failed.append(url)
            elif record.get("word_count", 0) < THIN_CONTENT_WORD_THRESHOLD:
                thin.append(url)

            if not was_cached:
                time.sleep(DELAY_BETWEEN_REQUESTS)

        browser.close()

    summary = {
        "total": len(records),
        "succeeded": len(records) - len(failed),
        "failed": failed,
        "thin_content": thin,
    }
    print(f"\nDone: {summary['succeeded']}/{summary['total']} succeeded, "
          f"{len(failed)} failed, {len(thin)} flagged as thin content")
    return summary


if __name__ == "__main__":
    run()
