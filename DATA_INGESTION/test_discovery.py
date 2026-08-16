"""
test_discovery.py
...
"""

import asyncio

from crawl4ai import AsyncWebCrawler
from DATA_INGESTION.config import SEED_URLS

from DATA_INGESTION.utils.scraper_utils import get_browser_config
from DATA_INGESTION.utils.discovery_utils import (
    check_robots_permission,
    discover_via_sitemap,
    discover_via_bfs,
    filter_relevant_urls,
    filter_by_language,
)


async def test_seed(crawler, seed_url: str, country: str):

    print("\n" + "#" * 80)
    print(f"COUNTRY: {country}")
    print(f"SEED:    {seed_url}")
    print("#" * 80)

    allowed, sitemap_urls = check_robots_permission(seed_url)

    print(f"\n[robots.txt] allowed to crawl: {allowed}")
    print(f"[robots.txt] sitemap(s) declared: {sitemap_urls or 'none'}")

    if not allowed:
        print("\nCrawling disallowed. Discovery would return [] here.")
        return

    raw_urls = discover_via_sitemap(seed_url, sitemap_urls)
    print(f"\n[sitemap] raw URLs found: {len(raw_urls)}")

    if raw_urls:
        print("[sitemap] first 10 raw URLs:")
        for url in raw_urls[:10]:
            print(f"    {url}")

    if raw_urls:
        # CHANGED: country -> seed_url
        filtered = filter_relevant_urls(raw_urls, seed_url)
        print(f"\n[filter] {len(filtered)} of {len(raw_urls)} sitemap URLs passed the relevance filter.")

        # CHANGED: country -> seed_url
        filtered = filter_by_language(filtered, seed_url)
        print(f"[filter] {len(filtered)} remain after language filtering.")

        if filtered:
            print("[filter] matched URLs:")
            for url in filtered:
                print(f"    {url}")
        else:
            print(
                "[filter] ZERO matches. Either the keyword list doesn't match "
                "this site's URL structure, or the sitemap covers a different "
                "section of the site entirely. Check a few raw URLs above "
                "manually to see what pattern they actually follow."
            )

    if not raw_urls:
        print("\n[sitemap] No sitemap URLs at all. Running BFS fallback instead...")
        print("(This will open real browser pages — may take a minute.)\n")

        bfs_urls = await discover_via_bfs(crawler, seed_url)
        print(f"\n[BFS] raw URLs found: {len(bfs_urls)}")

        if bfs_urls:
            print("[BFS] first 10 raw URLs:")
            for url in bfs_urls[:10]:
                print(f"    {url}")

            # CHANGED: country -> seed_url
            filtered_bfs = filter_relevant_urls(bfs_urls, seed_url)
            print(f"\n[filter] {len(filtered_bfs)} of {len(bfs_urls)} BFS URLs passed the relevance filter.")

            # CHANGED: country -> seed_url
            filtered_bfs = filter_by_language(filtered_bfs, seed_url)
            print(f"[filter] {len(filtered_bfs)} remain after language filtering.")

            if filtered_bfs:
                print("[filter] matched URLs:")
                for url in filtered_bfs:
                    print(f"    {url}")
            else:
                print("[filter] ZERO matches from BFS either. Keyword list likely needs adjusting.")


async def main():

    browser_config = get_browser_config()

    async with AsyncWebCrawler(config=browser_config) as crawler:

        for country, seeds in SEED_URLS.items():
            for seed_url in seeds:
                await test_seed(crawler, seed_url, country)


if __name__ == "__main__":
    asyncio.run(main())