import asyncio
import time


from crawl4ai import AsyncWebCrawler
from dotenv import load_dotenv
from config import SEED_URLS, OUTPUT_CSV, SOURCE_CONFIG
from urllib.parse import urlparse

from utils.scraper_utils import (
    get_browser_config,
    fetch_page,
    extract_page_content,
    get_page_title,
    #save_markdown,
)
from utils.llm_utils import extract_entities
from utils.data_utils import save_entities_to_csv, classify_entry_type, merge_duplicate_entities
from utils.discovery_utils import discover_urls, is_relevant_page
from utils.storage_utils import save_markdown,append_entities_jsonl, load_entities_jsonl, log_url_outcome, save_discovered_urls, get_processed_urls, load_raw_json_if_exists

load_dotenv()


def _format_elapsed(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m {secs}s" if minutes else f"{secs}s"


async def crawl_knowledge():

    browser_config = get_browser_config()
    run_started_at = time.monotonic()
    countries_processed = []

    async with AsyncWebCrawler(config=browser_config) as crawler:

        for country, seeds in SEED_URLS.items():

            print("\n" + "#" * 80)
            print(f"COUNTRY: {country}")
            print("#" * 80)

            countries_processed.append(country)

            # NEW: resume support — what's already fully processed for this country
            already_processed = get_processed_urls(country)
            if already_processed:
                print(f"Resuming: {len(already_processed)} URL(s) already processed for {country}, will skip these.")

            country_entities = 0
            country_pages_ok = 0
            country_pages_failed = 0
            country_pages_skipped = 0
            country_started_at = time.monotonic()

            for seed_url in seeds:

                # ---- Discovery step ----
                discovered_urls = await discover_urls(crawler, seed_url)

                if not discovered_urls:
                    print(f"Discovery returned nothing for {seed_url}. Falling back to crawling the seed URL only.")
                    discovered_urls = [seed_url]

                # NEW: persist the full discovered list, regardless of what happens to each URL after
                save_discovered_urls(discovered_urls, country, seed_url)

                total_pages = len(discovered_urls)
                print(f"\n>>> {country}: {total_pages} page(s) discovered from this seed.\n")

                for index, url in enumerate(discovered_urls, start=1):

                    # NEW: skip fully-processed URLs from a previous run
                    if url in already_processed:
                        print(f"[{country}] Skipping (already processed): {url}")
                        country_pages_skipped += 1
                        log_url_outcome(url, country, "skipped_resume")
                        continue

                    elapsed = _format_elapsed(time.monotonic() - run_started_at)
                    print("\n" + "=" * 80)
                    print(f"[{country}] Page {index}/{total_pages} (elapsed: {elapsed})")
                    print(f"Crawling: {url}")
                    print("=" * 80)

                    result = await fetch_page(crawler, url)

                    if result is None:
                        print(f"Skipping {url} (crawl failed).")
                        country_pages_failed += 1
                        log_url_outcome(url, country, "scrape_failed")
                        continue

                    markdown = extract_page_content(result)

                    if not markdown or not markdown.strip():
                        print(f"No content extracted from {url}.")
                        country_pages_failed += 1
                        log_url_outcome(url, country, "empty_content")
                        continue

                    saved_path = save_markdown(markdown, url, country)
                    page_title = get_page_title(result)

                    if not is_relevant_page(page_title, markdown, seed_url):
                        print(f"Skipping {url} (excluded: irrelevant/placeholder content).")
                        country_pages_failed += 1
                        log_url_outcome(url, country, "irrelevant")
                        continue

                    # NEW: check for a cached raw LLM response before re-calling Groq
                    raw_cached = load_raw_json_if_exists(url, country)

                    try:
                        extraction = extract_entities(
                            markdown=markdown,
                            country=country,
                            source_url=url,
                            page_title=page_title,
                            cached_raw_response=raw_cached,   # None if nothing cached — extract_entities handles both cases
                        )
                    except Exception as e:
                        print(f"LLM extraction failed for {url}")
                        print(e)
                        country_pages_failed += 1
                        log_url_outcome(url, country, "llm_failed", reason=str(e))
                        continue

                    if not extraction.entities:
                        print(f"No knowledge entities extracted from {url}.")
                        country_pages_ok += 1
                        log_url_outcome(url, country, "no_entities")
                        continue

                    page_entities = []
                    for entity in extraction.entities:
                        entity_dict = entity.model_dump()
                        entity_dict["entry_type"] = classify_entry_type(entity_dict)
                        page_entities.append(entity_dict)

                    append_entities_jsonl(page_entities, country)

                    country_entities += len(page_entities)
                    country_pages_ok += 1
                    log_url_outcome(url, country, "scraped_ok")

                    print(f"Extracted {len(page_entities)} entities from this page (country running total: {country_entities}).")

            country_elapsed = _format_elapsed(time.monotonic() - country_started_at)
            print("\n" + "~" * 80)
            print(
                f"{country} summary: {country_entities} entities | {country_pages_ok} pages ok | "
                f"{country_pages_failed} pages failed/skipped | {country_pages_skipped} pages skipped (resumed) | "
                f"took {country_elapsed}"
            )
            print("~" * 80)

    # ---- Final step: read back everything from JSONL, merge, export ----
    total_elapsed = _format_elapsed(time.monotonic() - run_started_at)
    print(f"\nTotal run time: {total_elapsed}")

    all_entities = []
    for country in countries_processed:
        all_entities.extend(load_entities_jsonl(country))

    print(f"Total Knowledge Entities (loaded from disk): {len(all_entities)}")

    all_entities = merge_duplicate_entities(all_entities)
    print(f"Total Knowledge Entities (after merging duplicates): {len(all_entities)}")

    if all_entities:
        save_entities_to_csv(all_entities, OUTPUT_CSV)
        print(f"\nFinished! Saved to '{OUTPUT_CSV}'.")
    else:
        print("\nNo entities were extracted.")

async def main():
    await crawl_knowledge()


if __name__ == "__main__":
    asyncio.run(main())


# import asyncio
# import time

# from crawl4ai import AsyncWebCrawler
# from dotenv import load_dotenv
# from config import SEED_URLS, OUTPUT_CSV

# from utils.scraper_utils import (
#     get_browser_config,
#     fetch_page,
#     extract_page_content,
#     get_page_title,
#     save_markdown,
# )
# from utils.llm_utils import extract_entities
# from utils.data_utils import save_entities_to_csv, classify_entry_type, merge_duplicate_entities
# from utils.discovery_utils import discover_urls, is_relevant_page

# load_dotenv()


# def _format_elapsed(seconds: float) -> str:
#     minutes, secs = divmod(int(seconds), 60)
#     return f"{minutes}m {secs}s" if minutes else f"{secs}s"


# async def crawl_knowledge():
#     """
#     Discover, crawl, and extract immigration knowledge for every
#     configured country/seed pair, then save all extracted entities
#     to a CSV file.
#     """

#     browser_config = get_browser_config()
#     all_entities = []
#     run_started_at = time.monotonic()

#     async with AsyncWebCrawler(config=browser_config) as crawler:

#         for country, seeds in SEED_URLS.items():

#             print("\n" + "#" * 80)
#             print(f"COUNTRY: {country}")
#             print("#" * 80)

#             country_entities = 0
#             country_pages_ok = 0
#             country_pages_failed = 0
#             country_started_at = time.monotonic()

#             for seed_url in seeds:

#                 # ---- Discovery step ----
#                 discovered_urls = await discover_urls(crawler, seed_url, country)

#                 if not discovered_urls:
#                     print(
#                         f"Discovery returned nothing for {seed_url}. "
#                         f"Falling back to crawling the seed URL only."
#                     )
#                     discovered_urls = [seed_url]

#                 total_pages = len(discovered_urls)
#                 print(f"\n>>> {country}: {total_pages} page(s) to process from this seed.\n")

#                 # ---- Crawl + extract each discovered URL ----
#                 for index, url in enumerate(discovered_urls, start=1):

#                     elapsed = _format_elapsed(time.monotonic() - run_started_at)

#                     print("\n" + "=" * 80)
#                     print(
#                         f"[{country}] Page {index}/{total_pages} "
#                         f"(overall entities so far: {len(all_entities)}, elapsed: {elapsed})"
#                     )
#                     print(f"Crawling: {url}")
#                     print("=" * 80)

#                     result = await fetch_page(crawler, url)

#                     if result is None:
#                         print(f"Skipping {url} (crawl failed).")
#                         country_pages_failed += 1
#                         continue

#                     markdown = extract_page_content(result)

#                     if not markdown or not markdown.strip():
#                         print(f"No content extracted from {url}.")
#                         country_pages_failed += 1
#                         continue

#                     saved_path = save_markdown(markdown, url, country)
#                     print(f"Saved markdown -> {saved_path}")

#                     print(f"\nMarkdown Length: {len(markdown)} characters")
#                     print("\nFirst 1000 characters:\n")
#                     print(markdown[:1000])
#                     print("\n" + "-" * 80)

#                     page_title = get_page_title(result)
#                     print(f"Page Title: {page_title}")

#                     if not is_relevant_page(page_title, markdown, country):
#                         print(f"Skipping {url} (excluded: irrelevant/placeholder content).")
#                         country_pages_failed += 1
#                         continue

#                     try:
#                         extraction = extract_entities(
#                             markdown=markdown,
#                             country=country,
#                             source_url=url,
#                             page_title=page_title,
#                         )

#                     except Exception as e:
#                         print(f"LLM extraction failed for {url}")
#                         print(e)
#                         country_pages_failed += 1
#                         continue

#                     if not extraction.entities:
#                         print(f"No knowledge entities extracted from {url}.")
#                         country_pages_ok += 1
#                         continue

#                     for entity in extraction.entities:
#                         entity_dict = entity.model_dump()
#                         entity_dict["entry_type"] = classify_entry_type(entity_dict)
#                         all_entities.append(entity_dict)

#                     country_entities += len(extraction.entities)
#                     country_pages_ok += 1

#                     print(
#                         f"Extracted {len(extraction.entities)} entities from this page "
#                         f"(country running total: {country_entities})."
#                     )

#             country_elapsed = _format_elapsed(time.monotonic() - country_started_at)
#             print("\n" + "~" * 80)
#             print(
#                 f"{country} summary: {country_entities} entities | "
#                 f"{country_pages_ok} pages ok | {country_pages_failed} pages failed/skipped | "
#                 f"took {country_elapsed}"
#             )
#             print("~" * 80)

#     total_elapsed = _format_elapsed(time.monotonic() - run_started_at)

#     print("\n" + "=" * 80)
#     print(f"Total Knowledge Entities (before merge): {len(all_entities)}")
#     print(f"Total run time: {total_elapsed}")
#     print("=" * 80)

#     all_entities = merge_duplicate_entities(all_entities)
#     print(f"Total Knowledge Entities (after merging duplicates): {len(all_entities)}")

#     if all_entities:
#         save_entities_to_csv(all_entities, OUTPUT_CSV)
#         print(f"\nFinished! Saved to '{OUTPUT_CSV}'.")
#     else:
#         print("\nNo entities were extracted.")


# async def main():
#     await crawl_knowledge()


# if __name__ == "__main__":
#     asyncio.run(main())