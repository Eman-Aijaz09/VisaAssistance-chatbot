"""
discovery_utils.py

URL discovery for the Visa Assistant crawling pipeline.

Given a seed URL, this module figures out which other pages on the
same site are worth crawling, using two strategies:

    1. Sitemap-based discovery (preferred, when allowed + available)
    2. BFS internal-link crawling (fallback)

Both strategies converge on the same relevance filter, resolved per
DOMAIN via config.SOURCE_CONFIG — each site's own keywords, path
hints, and exclusion lists are used automatically based on which
URL is being processed. Nothing here is keyed by country directly.
"""

import urllib.request
import urllib.error
import urllib.robotparser
from urllib.parse import urlparse, urljoin
import requests
import gzip
import time
import xml.etree.ElementTree as ET
from config import (
    SOURCE_CONFIG,
    MAX_PAGES,
    MAX_DEPTH,
    UNIVERSAL_PLACEHOLDER_MARKERS,
    SITEMAP_FETCH_TIMEOUT,
    SITEMAP_FETCH_RETRIES,
)

USER_AGENT = "VisaAssistantBot/0.1"

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


# ==============================
# Source config resolution
# ==============================

def get_source_config(url: str) -> dict:
    """
    Resolve the SOURCE_CONFIG block for whatever domain a URL belongs to.
    Returns {} if unregistered — callers treat missing keys as
    "no restriction" (permissive default).
    """
    domain = urlparse(url).netloc
    return SOURCE_CONFIG.get(domain, {})


# ==============================
# robots.txt handling  (unchanged)
# ==============================

def _get_robots_url(seed_url: str) -> str:
    parsed = urlparse(seed_url)
    return f"{parsed.scheme}://{parsed.netloc}/robots.txt"


def _fetch_text(url: str, timeout: int = None) -> str | None:
    """
    Fetch raw text content from a URL using a plain HTTP GET, with
    retry logic matching _fetch_sitemap_bytes — a flaky robots.txt
    fetch shouldn't silently fall through to "assume allowed" when
    the real answer might have been "disallowed."
    """
    timeout = timeout or SITEMAP_FETCH_TIMEOUT

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    last_error = None

    for attempt in range(1, SITEMAP_FETCH_RETRIES + 2):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)

            if response.status_code != 200:
                print(f"Fetch failed for {url}: HTTP {response.status_code} (attempt {attempt})")
                last_error = f"HTTP {response.status_code}"
                continue

            return response.text

        except requests.exceptions.RequestException as e:
            print(f"Fetch failed for {url}: {e} (attempt {attempt})")
            last_error = str(e)
            if attempt <= SITEMAP_FETCH_RETRIES:
                time.sleep(1.5 * attempt)

    print(f"Giving up on {url} after {SITEMAP_FETCH_RETRIES + 1} attempts. Last error: {last_error}")
    return None

def _fetch_sitemap_bytes(url: str, timeout: int = None) -> bytes | None:
    """
    Fetch raw bytes for a sitemap URL, with retry logic — some
    government/embassy sites are slow or flaky, and silently dropping
    a timed-out sitemap means quietly losing a chunk of that site's
    URLs with no indication anything went wrong.
    """
    timeout = timeout or SITEMAP_FETCH_TIMEOUT

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    last_error = None

    for attempt in range(1, SITEMAP_FETCH_RETRIES + 2):  # +2: initial try + N retries
        try:
            response = requests.get(url, headers=headers, timeout=timeout)

            if response.status_code != 200:
                print(f"Fetch failed for {url}: HTTP {response.status_code} (attempt {attempt})")
                last_error = f"HTTP {response.status_code}"
                continue

            raw = response.content

            if raw[:2] == b"\x1f\x8b":
                try:
                    return gzip.decompress(raw)
                except OSError as e:
                    print(f"Failed to gunzip {url}: {e}")
                    return None

            return raw

        except requests.exceptions.RequestException as e:
            print(f"Fetch failed for {url}: {e} (attempt {attempt})")
            last_error = str(e)
            if attempt <= SITEMAP_FETCH_RETRIES:
                time.sleep(1.5 * attempt)  # small backoff between retries

    print(f"Giving up on {url} after {SITEMAP_FETCH_RETRIES + 1} attempts. Last error: {last_error}")
    return None


def check_robots_permission(seed_url: str) -> tuple[bool, list[str]]:
    robots_url = _get_robots_url(seed_url)
    robots_text = _fetch_text(robots_url)

    if robots_text is None:
        print(f"No robots.txt found at {robots_url}. Assuming crawl allowed.")
        return True, []

    parser = urllib.robotparser.RobotFileParser()
    parser.parse(robots_text.splitlines())
    allowed = parser.can_fetch(USER_AGENT, seed_url)

    sitemap_urls = [
        line.split(":", 1)[1].strip()
        for line in robots_text.splitlines()
        if line.strip().lower().startswith("sitemap:")
    ]

    return allowed, sitemap_urls


# ==============================
# Sitemap parsing  (unchanged)
# ==============================

def _parse_sitemap_xml(xml_text: str) -> tuple[list[str], list[str]]:
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
# BFS internal-link fallback  (unchanged)
# ==============================

async def discover_via_bfs(
    crawler,
    seed_url: str,
    max_depth: int = MAX_DEPTH,
    max_pages: int = MAX_PAGES,
) -> list[str]:
    from DATA_INGESTION.utils.scraper_utils import fetch_page, extract_internal_links

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

def filter_by_language(urls: list[str], seed_url: str) -> list[str]:
    """
    Keep only the preferred-language mirror, per this seed's own
    SOURCE_CONFIG entry. If a site doesn't use locale-prefixed URLs
    (preferred_language_path is None), all URLs pass through unchanged.
    """
    cfg = get_source_config(seed_url)
    preferred_path = cfg.get("preferred_language_path")

    if not preferred_path:
        return urls

    return [url for url in urls if preferred_path in url]


def is_relevant_url(url: str, seed_url: str) -> bool:
    """
    Broad-net relevance check, now fully config-driven per source:
      1. excluded_url_path_patterns — hard exclude, checked first
         (cheaper to reject early than to keep checking).
      2. content_path_hints — this site's own known content sections
         (was hardcoded CONTENT_PATH_HINTS before; now per-domain,
         since diplo.de's "/service/" pattern has no reason to apply
         to a different site's URL structure).
      3. keywords — fallback keyword match.
      4. If a source has no keywords configured, permissive default
         (True) — same behavior as before.
    """
    cfg = get_source_config(seed_url)
    url_lower = url.lower()

    excluded_patterns = cfg.get("excluded_url_path_patterns", [])
    if any(pattern.lower() in url_lower for pattern in excluded_patterns):
        return False

    content_path_hints = cfg.get("content_path_hints", [])
    if any(hint.lower() in url_lower for hint in content_path_hints):
        return True

    keywords = cfg.get("keywords", [])
    if keywords and any(keyword.lower() in url_lower for keyword in keywords):
        return True

    if not keywords and not content_path_hints:
        return True

    return False


def is_relevant_page(page_title: str, markdown: str, seed_url: str) -> bool:
    """
    Post-crawl relevance check. All exclusion lists now come from
    this seed's own SOURCE_CONFIG entry.
    """
    cfg = get_source_config(seed_url)
    title_lower = (page_title or "").lower()
    markdown_lower = (markdown or "").lower()

    for marker in UNIVERSAL_PLACEHOLDER_MARKERS:
        if marker in title_lower or marker in markdown_lower:
            return False

    for keyword in cfg.get("excluded_title_keywords", []):
        if keyword in title_lower:
            return False

    for marker in cfg.get("placeholder_content_markers", []):
        if marker in markdown_lower:
            return False

    return True


def filter_relevant_urls(urls: list[str], seed_url: str) -> list[str]:
    return [url for url in urls if is_relevant_url(url, seed_url)]


# ==============================
# Main entry point
# ==============================

async def discover_urls(crawler, seed_url: str) -> list[str]:
    """
    Full discovery pipeline for a single seed URL. No `country` param —
    everything resolves from seed_url alone via SOURCE_CONFIG.
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

    relevant_urls = filter_relevant_urls(raw_urls, seed_url)
    relevant_urls = filter_by_language(relevant_urls, seed_url)
    print(f"{len(relevant_urls)} of {len(raw_urls)} discovered URLs passed relevance + language filtering.")

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