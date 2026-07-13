"""
discovery_utils.py

URL discovery for the Visa Assistant crawling pipeline.

Given a seed URL, this module figures out which other pages on the
same site are worth crawling, using two strategies:

    1. Sitemap-based discovery (preferred, when allowed + available)
    2. BFS internal-link crawling (fallback)

Both strategies converge on the same relevance filter, defined per
country in config.COUNTRY_KEYWORDS, so garbage pages (press releases,
contact forms, org charts, etc.) never reach the LLM extraction step.
"""

import urllib.request
import urllib.error
import urllib.robotparser
from urllib.parse import urlparse, urljoin
import xml.etree.ElementTree as ET

from config import COUNTRY_KEYWORDS, MAX_PAGES, MAX_DEPTH

USER_AGENT = "VisaAssistantBot/0.1"

# XML namespace used by sitemap.org protocol
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


# ==============================
# robots.txt handling
# ==============================

def _get_robots_url(seed_url: str) -> str:
    parsed = urlparse(seed_url)
    return f"{parsed.scheme}://{parsed.netloc}/robots.txt"


def _fetch_text(url: str, timeout: int = 10) -> str | None:
    """
    Fetch raw text content from a URL using a plain HTTP GET.
    Returns None on any failure (missing file, timeout, non-200, etc.).
    """

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                return None
            return response.read().decode("utf-8", errors="ignore")

    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None


def check_robots_permission(seed_url: str) -> tuple[bool, list[str]]:
    """
    Check robots.txt for a domain.

    Returns
    -------
    (allowed, sitemap_urls)
        allowed       : whether USER_AGENT may crawl the seed path
        sitemap_urls  : any sitemap URLs declared in robots.txt
    """

    robots_url = _get_robots_url(seed_url)
    robots_text = _fetch_text(robots_url)

    # No robots.txt found -> assume crawling is allowed, no sitemaps known.
    if robots_text is None:
        print(f"No robots.txt found at {robots_url}. Assuming crawl allowed.")
        return True, []

    # Permission check via stdlib parser
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(robots_text.splitlines())
    allowed = parser.can_fetch(USER_AGENT, seed_url)

    # robotparser doesn't expose Sitemap: directives, so scan manually
    sitemap_urls = [
        line.split(":", 1)[1].strip()
        for line in robots_text.splitlines()
        if line.strip().lower().startswith("sitemap:")
    ]

    return allowed, sitemap_urls


# ==============================
# Sitemap parsing
# ==============================

def _parse_sitemap_xml(xml_text: str) -> tuple[list[str], list[str]]:
    """
    Parse a sitemap XML document.

    Returns
    -------
    (page_urls, child_sitemap_urls)
        A sitemap index has child_sitemap_urls populated.
        A regular urlset has page_urls populated.
    """

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return [], []

    tag = root.tag.lower()

    if tag.endswith("sitemapindex"):
        child_sitemaps = [
            loc.text.strip()
            for loc in root.findall(".//sm:sitemap/sm:loc", SITEMAP_NS)
            if loc.text
        ]
        return [], child_sitemaps

    if tag.endswith("urlset"):
        page_urls = [
            loc.text.strip()
            for loc in root.findall(".//sm:url/sm:loc", SITEMAP_NS)
            if loc.text
        ]
        return page_urls, []

    return [], []


def fetch_sitemap_urls(sitemap_url: str, max_depth: int = 3) -> list[str]:
    """
    Fetch a sitemap, recursing into child sitemaps if it's a sitemap index.

    max_depth guards against pathological/circular sitemap references.
    """

    if max_depth <= 0:
        return []

    xml_text = _fetch_text(sitemap_url)
    if xml_text is None:
        print(f"Could not fetch sitemap: {sitemap_url}")
        return []

    page_urls, child_sitemaps = _parse_sitemap_xml(xml_text)

    all_urls = list(page_urls)

    for child_url in child_sitemaps:
        all_urls.extend(fetch_sitemap_urls(child_url, max_depth=max_depth - 1))

    return all_urls


def discover_via_sitemap(seed_url: str, sitemap_urls: list[str]) -> list[str]:
    """
    Try declared sitemaps first; fall back to the conventional
    /sitemap.xml path if none were declared in robots.txt.
    """

    candidates = list(sitemap_urls)

    if not candidates:
        parsed = urlparse(seed_url)
        default_sitemap = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
        candidates = [default_sitemap]

    all_urls = []
    for sitemap_url in candidates:
        urls = fetch_sitemap_urls(sitemap_url)
        if urls:
            print(f"Found {len(urls)} URLs in sitemap: {sitemap_url}")
        all_urls.extend(urls)

    return all_urls


# ==============================
# BFS internal-link fallback
# ==============================

async def discover_via_bfs(
    crawler,
    seed_url: str,
    max_depth: int = MAX_DEPTH,
    max_pages: int = MAX_PAGES,
) -> list[str]:
    """
    Breadth-first crawl of internal links starting from seed_url.
    Used when no sitemap is available.

    Requires an active Crawl4AI AsyncWebCrawler instance (passed in
    from main.py) since it needs to render JS-heavy pages.
    """

    # Imported here to avoid a circular import with scraper_utils at module load time
    from utils.scraper_utils import fetch_page, extract_internal_links

    domain = urlparse(seed_url).netloc

    visited = set()
    discovered = []
    queue = [(seed_url, 0)]

    while queue and len(discovered) < max_pages:

        url, depth = queue.pop(0)

        if url in visited or depth > max_depth:
            continue

        visited.add(url)

        result = await fetch_page(crawler, url)
        if result is None:
            continue

        discovered.append(url)

        if depth == max_depth:
            continue

        for link in extract_internal_links(result):
            absolute_link = urljoin(url, link)

            # Stay on the same domain, skip already-queued/visited links
            if urlparse(absolute_link).netloc != domain:
                continue
            if absolute_link in visited:
                continue

            queue.append((absolute_link, depth + 1))

    print(f"BFS discovered {len(discovered)} pages (depth limit {max_depth}).")
    return discovered


# ==============================
# Relevance filtering
# ==============================

def is_relevant_url(url: str, country: str) -> bool:
    """
    Check whether a URL matches the known visa/immigration path
    patterns for a given country, as defined in config.COUNTRY_KEYWORDS.

    If a country has no keywords configured, everything is treated
    as relevant (fail-open, since we'd rather over-collect than miss
    pages for a country we haven't tuned yet).
    """

    keywords = COUNTRY_KEYWORDS.get(country)

    if not keywords:
        return True

    url_lower = url.lower()
    return any(keyword.lower() in url_lower for keyword in keywords)


def filter_relevant_urls(urls: list[str], country: str) -> list[str]:
    return [url for url in urls if is_relevant_url(url, country)]


# ==============================
# Main entry point
# ==============================

async def discover_urls(crawler, seed_url: str, country: str) -> list[str]:
    """
    Full discovery pipeline for a single seed URL.

    1. Check robots.txt permission.
    2. Try sitemap-based discovery.
    3. Fall back to BFS internal-link crawling if no sitemap URLs found.
    4. Apply per-country relevance filtering.
    5. Deduplicate and cap at MAX_PAGES.

    Returns a list of URLs ready to be handed to the extraction pipeline.
    """

    print(f"\nDiscovering URLs for seed: {seed_url}")

    allowed, sitemap_urls = check_robots_permission(seed_url)

    if not allowed:
        print(f"Crawling disallowed by robots.txt for {seed_url}. Skipping.")
        return []

    raw_urls = discover_via_sitemap(seed_url, sitemap_urls)

    if not raw_urls:
        print("No sitemap URLs found. Falling back to BFS link crawl.")
        raw_urls = await discover_via_bfs(crawler, seed_url)

    relevant_urls = filter_relevant_urls(raw_urls, country)
    print(f"{len(relevant_urls)} of {len(raw_urls)} discovered URLs are relevant.")

    # Dedupe while preserving order, cap at MAX_PAGES
    seen = set()
    final_urls = []
    for url in relevant_urls:
        if url not in seen:
            seen.add(url)
            final_urls.append(url)
        if len(final_urls) >= MAX_PAGES:
            break

    print(f"Final discovery count: {len(final_urls)} URLs (capped at {MAX_PAGES}).")

    return final_urls