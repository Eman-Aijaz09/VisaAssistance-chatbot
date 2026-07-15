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
import requests
import gzip
import xml.etree.ElementTree as ET
from config import COUNTRY_KEYWORDS, MAX_PAGES, MAX_DEPTH, PREFERRED_LANGUAGE_PATH

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
    Returns None on failure, but prints the real reason so failures
    are debuggable instead of silently downgrading to "not found".
    """

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)

        if response.status_code != 200:
            print(f"Fetch failed for {url}: HTTP {response.status_code}")
            return None

        return response.text

    except requests.exceptions.RequestException as e:
        print(f"Fetch failed for {url}: {e}")
        return None


def _fetch_sitemap_bytes(url: str, timeout: int = 10) -> bytes | None:
    """
    Fetch raw bytes for a sitemap URL, transparently handling
    gzip-compressed sitemaps (.xml.gz), which are common on
    large government/embassy sites.
    """

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)

        if response.status_code != 200:
            print(f"Fetch failed for {url}: HTTP {response.status_code}")
            return None

        raw = response.content

        # Gzip magic bytes: 0x1f 0x8b — check content, not just the
        # .gz extension, since some servers rename/serve it differently.
        if raw[:2] == b"\x1f\x8b":
            try:
                return gzip.decompress(raw)
            except OSError as e:
                print(f"Failed to gunzip {url}: {e}")
                return None

        return raw

    except requests.exceptions.RequestException as e:
        print(f"Fetch failed for {url}: {e}")
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

    if max_depth <= 0:
        return []

    raw_bytes = _fetch_sitemap_bytes(sitemap_url)
    if raw_bytes is None:
        print(f"Could not fetch sitemap: {sitemap_url}")
        return []

    xml_text = raw_bytes.decode("utf-8", errors="ignore")
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

def filter_by_language(urls: list[str], country: str) -> list[str]:
    """
    For multilingual sites, keep only the preferred-language mirror
    (e.g. pakistan.diplo.de duplicates every page under /pk-de/ and
    /pk-en/). If no preference is configured for a country, all
    URLs pass through unchanged.
    """

    preferred_path = PREFERRED_LANGUAGE_PATH.get(country)

    if not preferred_path:
        return urls

    return [url for url in urls if preferred_path in url]

def is_relevant_url(url: str, country: str) -> bool:
    """
    Broad-net relevance check. Two passes:
      1. Path-based: content lives under known site sections
         (e.g. diplo.de sites put everything under /service/).
      2. Keyword-based: explicit visa/immigration terms, as a
         secondary signal for sites with descriptive URL slugs.

    This is intentionally permissive — true precision happens at
    the LLM extraction step, which already returns zero entities
    for off-topic pages. This filter only needs to exclude
    obviously irrelevant sections (embassy staff, press, etc.)
    to save on crawl/LLM calls, not decide topic relevance itself.
    """

    keywords = COUNTRY_KEYWORDS.get(country, [])
    url_lower = url.lower()

    # Path-based: broad content sections known to hold service pages
    CONTENT_PATH_HINTS = ["/service/", "-visa-", "/visa"]
    if any(hint in url_lower for hint in CONTENT_PATH_HINTS):
        return True

    # Keyword-based fallback
    if keywords and any(keyword.lower() in url_lower for keyword in keywords):
        return True

    if not keywords:
        return True

    return False


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
    5. Apply language-preference filtering (drop non-preferred mirrors).
    6. Deduplicate and cap at MAX_PAGES.

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
    relevant_urls = filter_by_language(relevant_urls, country)
    print(f"{len(relevant_urls)} of {len(raw_urls)} discovered URLs passed relevance + language filtering.")

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