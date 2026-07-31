"""
test_pipeline.py

Tests the scrape -> extract -> incremental storage pipeline for ONE
url (or a small hand-picked list), without running the full main.py
loop and without touching the final merge/CSV step.

Exercises exactly the same functions main.py uses per-page:
    fetch_page -> save_markdown -> is_relevant_page ->
    load_raw_json_if_exists -> extract_entities -> save_raw_json (inside extract_entities) ->
    append_entities_jsonl -> log_url_outcome

Run:
    python test_pipeline.py https://pakistan.diplo.de/pk-en/service/... Germany
    python test_pipeline.py   (uses DEFAULT_URL / DEFAULT_COUNTRY below)
"""

import asyncio
import sys

from crawl4ai import AsyncWebCrawler

from utils.scraper_utils import get_browser_config, fetch_page, extract_page_content, get_page_title
from utils.discovery_utils import is_relevant_page
from utils.llm_utils import extract_entities
from utils.data_utils import classify_entry_type
from utils.storage_utils import (
    save_markdown,
    append_entities_jsonl,
    log_url_outcome,
    load_raw_json_if_exists,
    get_processed_urls,
)

DEFAULT_URL = "https://pakistan.diplo.de/pk-de/erbschaftsangelegenheiten"
DEFAULT_COUNTRY = "Germany"
DEFAULT_SEED_URL = "https://pakistan.diplo.de/"   # only needed for is_relevant_page's config lookup


async def test_single_url(url: str, country: str, seed_url: str):

    print(f"\n{'='*80}")
    print(f"Testing pipeline for: {url}")
    print(f"Country: {country}")
    print(f"{'='*80}\n")

    # ---- Check resume state first, same as main.py would ----
    already_processed = get_processed_urls(country)
    if url in already_processed:
        print(f"NOTE: {url} is already in {country}_entities.jsonl.")
        print("If you want to force a fresh test, either use a different URL,")
        print("or manually remove its line from that file / delete the file.")
        proceed = input("Continue anyway and re-process it? (y/n): ").strip().lower()
        if proceed != "y":
            print("Aborted.")
            return

    browser_config = get_browser_config()

    async with AsyncWebCrawler(config=browser_config) as crawler:

        # ---- 1. Scrape ----
        result = await fetch_page(crawler, url)

        if result is None:
            print("FAILED: fetch_page returned None (crawl failed).")
            log_url_outcome(url, country, "scrape_failed")
            return

        markdown = extract_page_content(result)

        if not markdown or not markdown.strip():
            print("FAILED: No content extracted (empty markdown).")
            log_url_outcome(url, country, "empty_content")
            return

        print(f"OK: Scraped {len(markdown)} characters of markdown.")

        # ---- 2. Save markdown ----
        saved_path = save_markdown(markdown, url, country)
        page_title = get_page_title(result)
        print(f"Page title: {page_title!r}")

        # ---- 3. Relevance check ----
        if not is_relevant_page(page_title, markdown, seed_url):
            print("SKIPPED: Page failed is_relevant_page check (excluded/placeholder).")
            log_url_outcome(url, country, "irrelevant")
            return

        print("OK: Passed relevance check.")

        # ---- 4. Check for cached raw JSON (crash-recovery path) ----
        raw_cached = load_raw_json_if_exists(url, country)
        if raw_cached:
            print("NOTE: Found existing cached raw JSON for this URL — will reuse it (no fresh Groq call).")
        else:
            print("NOTE: No cached raw JSON found — will make a fresh Groq call.")

        # ---- 5. Extract entities ----
        try:
            extraction = extract_entities(
                markdown=markdown,
                country=country,
                source_url=url,
                page_title=page_title,
                cached_raw_response=raw_cached,
            )
        except Exception as e:
            print(f"FAILED: LLM extraction failed — {e}")
            log_url_outcome(url, country, "llm_failed", reason=str(e))
            return

        if not extraction.entities:
            print("NOTE: LLM returned zero entities for this page.")
            log_url_outcome(url, country, "no_entities")
            return

        print(f"OK: Extracted {len(extraction.entities)} entit{'y' if len(extraction.entities)==1 else 'ies'}.")

        # ---- 6. Build entity dicts + classify entry_type ----
        page_entities = []
        for entity in extraction.entities:
            entity_dict = entity.model_dump()
            entity_dict["entry_type"] = classify_entry_type(entity_dict)
            page_entities.append(entity_dict)

        # ---- 7. Append to JSONL ----
        jsonl_path = append_entities_jsonl(page_entities, country)
        log_url_outcome(url, country, "scraped_ok")

        print(f"\nOK: Appended {len(page_entities)} entities to {jsonl_path}")

        # ---- 8. Print what was actually extracted, for eyeballing ----
        print(f"\n{'='*80}")
        print("EXTRACTED ENTITIES (for manual review):")
        print(f"{'='*80}")
        for i, entity_dict in enumerate(page_entities, start=1):
            print(f"\n--- Entity {i} ---")
            print(f"Title       : {entity_dict.get('title')}")
            print(f"Visa Type   : {entity_dict.get('visa_type')}")
            print(f"Purpose     : {entity_dict.get('purpose')}")
            print(f"Entry Type  : {entity_dict.get('entry_type')}")
            print(f"Eligibility : {entity_dict.get('eligibility')}")
            print(f"Documents   : {entity_dict.get('required_documents')}")

        print(f"\n{'='*80}")
        print("DONE. Check these files to verify storage:")
        print(f"  - scraped_output/{country}/markdown/  (this page's .md)")
        print(f"  - scraped_output/{country}/raw_json/  (this page's raw LLM .json)")
        print(f"  - scraped_output/{country}/{country}_entities.jsonl  (appended entities)")
        print(f"  - scraped_output/{country}/url_status.jsonl  (outcome logged)")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        target_url = sys.argv[1]
        target_country = sys.argv[2]
    else:
        target_url = DEFAULT_URL
        target_country = DEFAULT_COUNTRY

    asyncio.run(test_single_url(target_url, target_country, DEFAULT_SEED_URL))