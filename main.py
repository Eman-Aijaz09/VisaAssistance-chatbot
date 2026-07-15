import asyncio
import time

from crawl4ai import AsyncWebCrawler
from dotenv import load_dotenv
from config import SEED_URLS, OUTPUT_CSV

from utils.scraper_utils import (
    get_browser_config,
    fetch_page,
    extract_page_content,
    get_page_title,
)
from utils.llm_utils import extract_entities
from utils.data_utils import save_entities_to_csv
from utils.discovery_utils import discover_urls

load_dotenv()


def _format_elapsed(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m {secs}s" if minutes else f"{secs}s"


async def crawl_knowledge():
    """
    Discover, crawl, and extract immigration knowledge for every
    configured country/seed pair, then save all extracted entities
    to a CSV file.
    """

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
                discovered_urls = await discover_urls(crawler, seed_url, country)

                if not discovered_urls:
                    print(
                        f"Discovery returned nothing for {seed_url}. "
                        f"Falling back to crawling the seed URL only."
                    )
                    discovered_urls = [seed_url]

                total_pages = len(discovered_urls)
                print(f"\n>>> {country}: {total_pages} page(s) to process from this seed.\n")

                # ---- Crawl + extract each discovered URL ----
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

                    print(f"\nMarkdown Length: {len(markdown)} characters")
                    print("\nFirst 1000 characters:\n")
                    print(markdown[:1000])
                    print("\n" + "-" * 80)

                    page_title = get_page_title(result)
                    print(f"Page Title: {page_title}")

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
                        all_entities.append(entity.model_dump())

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
    print(f"Total Knowledge Entities: {len(all_entities)}")
    print(f"Total run time: {total_elapsed}")
    print("=" * 80)

    if all_entities:
        save_entities_to_csv(all_entities, OUTPUT_CSV)
        print(f"\nFinished! Saved to '{OUTPUT_CSV}'.")
    else:
        print("\nNo entities were extracted.")


async def main():
    await crawl_knowledge()


if __name__ == "__main__":
    asyncio.run(main())