import asyncio

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

load_dotenv()


async def crawl_knowledge():
    """
    Crawl one or more webpages, extract immigration knowledge,
    and save the extracted entities to a CSV file.
    """

    browser_config = get_browser_config()
    all_entities = []

    async with AsyncWebCrawler(config=browser_config) as crawler:

        for url in SEED_URLS:

            print("\n" + "=" * 80)
            print(f"Crawling: {url}")
            print("=" * 80)

            # Crawl webpage
            result = await fetch_page(crawler, url)

            if result is None:
                print(f"Skipping {url} (crawl failed).")
                continue

            # Extract page content (Markdown preferred)
            markdown = extract_page_content(result)

            if not markdown or not markdown.strip():
                print(f"No content extracted from {url}.")
                continue

            # Debug information
            print(f"\nMarkdown Length: {len(markdown)} characters")
            print("\nFirst 1000 characters:\n")
            print(markdown[:1000])
            print("\n" + "-" * 80)

            # Get page title
            page_title = get_page_title(result)

            print(f"Page Title: {page_title}")

            try:
                extraction = extract_entities(
                    markdown=markdown,
                    country="Germany",
                    source_url=url,
                    page_title=page_title,
                )

            except Exception as e:
                print(f"LLM extraction failed for {url}")
                print(e)
                continue

            if not extraction.entities:
                print(f"No knowledge entities extracted from {url}.")
                continue

            for entity in extraction.entities:
                all_entities.append(entity.model_dump())

            print(
                f"Extracted {len(extraction.entities)} entities from this page."
            )

    print("\n" + "=" * 80)
    print(f"Total Knowledge Entities: {len(all_entities)}")
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