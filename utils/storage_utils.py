"""
storage_utils.py

Persists raw scraped content and raw LLM responses to disk, organized
per country, keyed by the same safe_filename(url) used for markdown —
so a page's markdown and its raw JSON response always share a base name
and can be looked up from one another.
"""

import os
import re
from datetime import datetime
import json

def save_discovered_urls(urls: list, country: str, seed_url: str, base_dir: str = "scraped_output") -> str:
    """
    Persist the full list of discovered URLs for a seed, so you have
    a record of every URL that was ever considered — independent of
    whether it was later scraped, skipped, or failed.
    """
    output_dir = os.path.join(base_dir, country)
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, "discovered_urls.jsonl")

    with open(filepath, "a", encoding="utf-8") as f:
        for url in urls:
            record = {
                "url": url,
                "seed_url": seed_url,
                "discovered_at": datetime.now().isoformat(),
            }
            f.write(json.dumps(record) + "\n")

    return filepath


def log_url_outcome(url: str, country: str, status: str, reason: str = "",
                     base_dir: str = "scraped_output") -> str:
    """
    Record what happened to a discovered URL: scraped_ok, scrape_failed,
    irrelevant, llm_failed, no_entities, skipped_resume. This is your
    full trace — cross-reference against discovered_urls.jsonl to see
    every URL's fate, not just the ones that made it into entities.
    """
    output_dir = os.path.join(base_dir, country)
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, "url_status.jsonl")

    with open(filepath, "a", encoding="utf-8") as f:
        record = {
            "url": url,
            "status": status,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }
        f.write(json.dumps(record) + "\n")

    return filepath

def get_processed_urls(country: str, base_dir: str = "scraped_output") -> set:
    """
    Return the set of source_urls already recorded in this country's
    JSONL file, so a rerun can skip pages already scraped + extracted
    instead of redoing the work (and re-appending duplicates).
    """
    entities = load_entities_jsonl(country, base_dir)
    return {e.get("source_url") for e in entities if e.get("source_url")}

def append_entities_jsonl(entities: list, country: str, base_dir: str = "scraped_output") -> str:
    """
    Append entities (as dicts) to a running per-country JSONL file,
    one JSON object per line. Called after EACH page's extraction
    succeeds, so a crash mid-run loses at most one page's work —
    everything already written stays on disk regardless of what
    happens next.

    JSONL (not a single JSON array) because appending to it is O(1)
    and crash-safe: a partially-written array corrupts the whole file,
    but a partially-written line is just one bad line at the end,
    the rest stay valid.
    """
    output_dir = os.path.join(base_dir, country)
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, f"{country}_entities.jsonl")

    with open(filepath, "a", encoding="utf-8") as f:
        for entity in entities:
            f.write(json.dumps(entity, ensure_ascii=False, default=str) + "\n")

    return filepath


def load_entities_jsonl(country: str, base_dir: str = "scraped_output") -> list:
    """
    Read back all entities appended so far for a country. Used both
    for final merge+CSV export, and as a recovery path if a run
    crashed partway — nothing here depends on the in-memory list
    having survived.
    """
    filepath = os.path.join(base_dir, country, f"{country}_entities.jsonl")

    if not os.path.exists(filepath):
        return []

    entities = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                entities.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Skipping corrupted line {line_num} in {filepath}")
                continue

    return entities


def safe_filename(url: str) -> str:
    """Convert a URL into a safe filename. Same logic as scraper_utils.py —
    duplicated here rather than imported, to keep this module dependency-free
    of scraper_utils (avoids a circular import risk later)."""
    name = re.sub(r'https?://', '', url)
    name = re.sub(r'[^a-zA-Z0-9]+', '_', name)
    return name[:100]


def save_markdown(content: str, url: str, country: str, base_dir: str = "scraped_output") -> str:
    """
    Save scraped markdown to scraped_output/<country>/markdown/<safe_filename>.md
    """
    output_dir = os.path.join(base_dir, country, "markdown")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"{safe_filename(url)}.md"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"<!-- Source: {url} -->\n")
        f.write(f"<!-- Scraped: {datetime.now().isoformat()} -->\n\n")
        f.write(content)

    print(f"Saved markdown -> {filepath}")
    return filepath


def save_raw_json(raw_json_text: str, url: str, country: str, base_dir: str = "scraped_output") -> str:
    """
    Save the RAW, pre-validation LLM JSON response (before
    _normalize_empty_strings / Pydantic parsing touches it) to
    scraped_output/<country>/raw_json/<safe_filename>.json

    raw_json_text is the exact string returned by the LLM — saved as-is,
    not re-serialized, so it reflects precisely what the LLM emitted
    (including any formatting quirks worth debugging later).
    """
    output_dir = os.path.join(base_dir, country, "raw_json")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"{safe_filename(url)}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(raw_json_text)

    print(f"Saved raw LLM response -> {filepath}")
    return filepath


def load_raw_json_if_exists(url: str, country: str, base_dir: str = "scraped_output") -> str | None:
    """
    If a raw LLM response was already saved for this URL (from a
    previous run that crashed before the entity made it into the
    country's JSONL), return it so it can be re-validated without
    another LLM call. Returns None if no raw file exists.
    """
    filepath = os.path.join(base_dir, country, "raw_json", f"{safe_filename(url)}.json")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    return None