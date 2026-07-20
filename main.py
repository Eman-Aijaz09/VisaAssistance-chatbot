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
    save_markdown,
)
from utils.llm_utils import extract_entities
from utils.data_utils import save_entities_to_csv, classify_entry_type, merge_duplicate_entities
from utils.discovery_utils import discover_urls, is_relevant_page

load_dotenv()


def _format_elapsed(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m {secs}s" if minutes else f"{secs}s"


async def crawl_knowledge():

    browser_config = get_browser_config()
    all_entities = []
    run_started_at = time.monotonic()

    async with AsyncWebCrawler(config=browser_config) as crawler:

        for country, seeds in SEED_URLS.items():

            print("\n" + "#" * 80)
            print(f"COUNTRY: {country}")
            print("#" * 80)

            country_entities = 0
            country_pages_ok = 0
            country_pages_failed = 0
            country_started_at = time.monotonic()

            for seed_url in seeds:

                # ---- Discovery step ----
                # CHANGED: dropped `country` arg — discover_urls now resolves
                # everything (keywords, language path, css selector) from
                # seed_url alone via SOURCE_CONFIG.
                discovered_urls = await discover_urls(crawler, seed_url)

                if not discovered_urls:
                    print(
                        f"Discovery returned nothing for {seed_url}. "
                        f"Falling back to crawling the seed URL only."
                    )
                    discovered_urls = [seed_url]

                total_pages = len(discovered_urls)
                print(f"\n>>> {country}: {total_pages} page(s) to process from this seed.\n")

                for index, url in enumerate(discovered_urls, start=1):

                    elapsed = _format_elapsed(time.monotonic() - run_started_at)

                    print("\n" + "=" * 80)
                    print(
                        f"[{country}] Page {index}/{total_pages} "
                        f"(overall entities so far: {len(all_entities)}, elapsed: {elapsed})"
                    )
                    print(f"Crawling: {url}")
                    print("=" * 80)

                    result = await fetch_page(crawler, url)

                    if result is None:
                        print(f"Skipping {url} (crawl failed).")
                        country_pages_failed += 1
                        continue

                    markdown = extract_page_content(result)

                    if not markdown or not markdown.strip():
                        print(f"No content extracted from {url}.")
                        country_pages_failed += 1
                        continue

                    # UNCHANGED: this `country` here is just used as the output
                    # subfolder name for saved markdown files, not a config
                    # lookup key — save_markdown's signature doesn't touch
                    # SOURCE_CONFIG at all, so nothing to change here.
                    saved_path = save_markdown(markdown, url, country)
                    print(f"Saved markdown -> {saved_path}")

                    print(f"\nMarkdown Length: {len(markdown)} characters")
                    print("\nFirst 1000 characters:\n")
                    print(markdown[:1000])
                    print("\n" + "-" * 80)

                    page_title = get_page_title(result)
                    print(f"Page Title: {page_title}")

                    # CHANGED: is_relevant_page now takes seed_url, not country,
                    # so it reads excluded_title_keywords / placeholder_content_markers
                    # from THIS site's own SOURCE_CONFIG block.
                    if not is_relevant_page(page_title, markdown, seed_url):
                        print(f"Skipping {url} (excluded: irrelevant/placeholder content).")
                        country_pages_failed += 1
                        continue

                    try:
                        extraction = extract_entities(
                            markdown=markdown,
                            country=country,
                            source_url=url,
                            page_title=page_title,
                        )

                    except Exception as e:
                        print(f"LLM extraction failed for {url}")
                        print(e)
                        country_pages_failed += 1
                        continue

                    if not extraction.entities:
                        print(f"No knowledge entities extracted from {url}.")
                        country_pages_ok += 1
                        continue

                    for entity in extraction.entities:
                        entity_dict = entity.model_dump()
                        entity_dict["entry_type"] = classify_entry_type(entity_dict)
                        all_entities.append(entity_dict)

                    country_entities += len(extraction.entities)
                    country_pages_ok += 1

                    print(
                        f"Extracted {len(extraction.entities)} entities from this page "
                        f"(country running total: {country_entities})."
                    )

            country_elapsed = _format_elapsed(time.monotonic() - country_started_at)
            print("\n" + "~" * 80)
            print(
                f"{country} summary: {country_entities} entities | "
                f"{country_pages_ok} pages ok | {country_pages_failed} pages failed/skipped | "
                f"took {country_elapsed}"
            )
            print("~" * 80)

    total_elapsed = _format_elapsed(time.monotonic() - run_started_at)

    print("\n" + "=" * 80)
    print(f"Total Knowledge Entities (before merge): {len(all_entities)}")
    print(f"Total run time: {total_elapsed}")
    print("=" * 80)

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