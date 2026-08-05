"""
filters.py

Purpose
-------
Every discovered URL (from sitemap or HTML links) passes through this file.

This file decides:
1. Should we crawl this URL?
2. What priority should it have?

NOTE:
We DO NOT reject pages because they don't contain words like
'visa' or 'permit' in the URL.

Many government websites (Germany, France, etc.) use random URLs.

Instead, we only reject obvious junk and assign priorities.
"""

from urllib.parse import urlparse
from .config import NON_ENGLISH_URL_SEGMENTS
# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

# Ignore these file extensions
IGNORE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".ico",
    ".css",
    ".js",
    ".xml",
    ".zip",
    ".rar",
    ".mp4",
    ".mp3",
}

# Ignore URLs containing these words
IGNORE_WORDS = {
    "login",
    "logout",
    "privacy",
    "cookie",
    "cookies",
    "terms",
    "facebook",
    "passport",
    "twitter",
    "instagram",
    "linkedin",
    "passport",
    "youtube",
    "glossary",
}

# Words that increase priority
HIGH_PRIORITY_WORDS = {
    "visa",
    "permit",
    "residence",
    "immigration",
    "travel",
    "study",
    "student",
    "work",
    "employment",
    "family",
    "citizenship",
    "entry",
}

# ------------------------------------------------------------------
# Priority values
# ------------------------------------------------------------------

BASE_PRIORITY = 50

PDF_BONUS = 20
HOMEPAGE_BONUS = 40
ANCHOR_TEXT_BONUS = 20

DEPTH_PENALTY = 5
MAX_PRIORITY = 100
MIN_PRIORITY = 1


# ------------------------------------------------------------------
# Main function
# ------------------------------------------------------------------

def evaluate_url(url_info: dict) -> dict:
    """
    Evaluates whether a discovered URL should be crawled and
    assigns a crawl priority.

    Input
    -----
    {
        "url": "...",
        "type": "html" | "pdf",

        "country": "...",
        "website": "...",

        "parent": "...",
        "depth": 0,

        "anchor_text": "..."
    }

    Output
    ------
    Returns the SAME dictionary enriched with:

    {
        "crawl": True/False,
        "priority": int,
        "reason": "..."
    }
    """

    url = url_info["url"].lower()

    if any(segment in url for segment in NON_ENGLISH_URL_SEGMENTS):
        return {
            "crawl": False,
            "priority": 0,
            "reason": "non_english_url",
        }

    # --------------------------------------------------------------
    # Ignore unwanted file types
    # --------------------------------------------------------------

    for ext in IGNORE_EXTENSIONS:
        if url.endswith(ext):

            url_info["crawl"] = False
            url_info["priority"] = 0
            url_info["reason"] = f"ignored extension ({ext})"

            return url_info

    # --------------------------------------------------------------
    # Ignore obvious junk pages
    # --------------------------------------------------------------

    for word in IGNORE_WORDS:
        if word in url:

            url_info["crawl"] = False
            url_info["priority"] = 0
            url_info["reason"] = f"ignored ({word})"

            return url_info

    # --------------------------------------------------------------
    # Calculate priority
    # --------------------------------------------------------------

    priority = BASE_PRIORITY

    # PDFs are usually useful immigration guides
    if url_info["type"] == "pdf":
        priority += PDF_BONUS

    # Homepage
    parsed = urlparse(url)

    if parsed.path in ("", "/"):
        priority += HOMEPAGE_BONUS

    # Useful anchor text
    anchor = (url_info.get("anchor_text") or "").lower()

    for word in HIGH_PRIORITY_WORDS:
        if word in anchor:
            priority += ANCHOR_TEXT_BONUS
            break

    # Penalize deep pages slightly
    depth = url_info.get("depth", 0)

    priority -= depth * DEPTH_PENALTY

    priority = max(MIN_PRIORITY, min(MAX_PRIORITY, priority))

    # --------------------------------------------------------------
    # Enrich the existing URL object
    # --------------------------------------------------------------

    url_info["crawl"] = True
    url_info["priority"] = priority
    url_info["reason"] = "accepted"

    return url_info