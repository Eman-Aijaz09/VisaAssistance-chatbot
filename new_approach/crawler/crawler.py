"""
===============================================================================
crawler.py

Purpose
-------

The crawler is the orchestrator of the system.

It DOES NOT know how to:

    • render webpages
    • discover links
    • parse sitemaps
    • filter URLs

Instead, it coordinates the specialized modules.

Flow

config.py
      │
      ▼
browser.py
      │
      ▼
sitemap.py
      │
      ▼
filters.py
      │
      ▼
url_queue.py
      │
      ▼
link_extractor.py
      │
      ▼
Repeat until queue is empty.

===============================================================================
"""

import asyncio
import httpx

from .config import (
    CRAWL_SOURCES,
    MAX_DEPTH,
    MAX_PAGES_PER_SOURCE,
    OUTPUT_FOLDER,
    QUEUE_STATE_FOLDER,
)

from .browser import BrowserManager
from .sitemap import SitemapDiscovery
from .link_extractor import LinkExtractor
from .filters import evaluate_url
from .url_queue import URLQueue
from pathlib import Path
from urllib.parse import urlparse
import re

class WebCrawler:
    """
    Coordinates the complete crawling process.

    One crawler instance can crawl multiple countries,
    with multiple official websites per country.
    """

    def __init__(self):

        self.browser = BrowserManager()

    def get_html_filename(self, country, source, url):
        """
        Build a readable path for saving rendered HTML.

        Example

        debug_html/
            Germany/
                German Embassy Pakistan/
                    work-visa.html
        """

        parsed = urlparse(url)

        path = parsed.path.strip("/")

        if not path:
            filename = "homepage"
        else:
            filename = path.replace("/", "_")

        # Remove characters Windows doesn't allow
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)

        folder = (
            Path(OUTPUT_FOLDER)
            / country
            / source["website"]
        )

        folder.mkdir(parents=True, exist_ok=True)

        return folder / f"{filename}.html"

    def get_pdf_filename(self, country, source, url):

        parsed = urlparse(url)

        parts = parsed.path.strip("/").split("/")

        filename = parts[-1]

        if "blob" in parts:
            blob_index = parts.index("blob")
            if blob_index + 1 < len(parts):
                filename = f"{parts[blob_index + 1]}_{filename}"

        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)

        folder = (
            Path(OUTPUT_FOLDER)
            / country
            / source["website"]
        )

        folder.mkdir(parents=True, exist_ok=True)

        return folder / filename

    async def save_pdf(self, page, item, country, source):

        filepath = self.get_pdf_filename(
            country,
            source,
            item["url"],
        )

        async with httpx.AsyncClient(follow_redirects=True) as client:

            response = await client.get(item["url"])

            if response.status_code == 200:

                with open(filepath, "wb") as f:
                    f.write(response.content)

                print(f"Saved PDF -> {filepath}")

            else:

                print(f"Failed to download PDF ({response.status_code})")

    def get_queue_state_filename(self, country, source):
        """
        Returns the JSON file used to save the crawl state
        for one website.
        """

        folder = Path(QUEUE_STATE_FOLDER) / country
        folder.mkdir(parents=True, exist_ok=True)

        website = re.sub(r'[<>:"/\\|?*]', "_", source["website"])

        return folder / f"{website}.json"

    async def run(self):
        """
        Main entry point.

        Loops over every configured country and website.
        """

        print("\nStarting crawler...\n")
        Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

        page = await self.browser.start()

        try:

            for country, websites in CRAWL_SOURCES.items():

                print("=" * 80)
                print(f"Country : {country}")
                print("=" * 80)

                for website in websites:

                    await self.crawl_website(
                        page=page,
                        country=country,
                        source=website,
                    )

        finally:

            await self.browser.stop()

        print("\nCrawler finished.")

    async def crawl_website(self, page, country, source):
        """
            Crawl one website.

            Every website gets its own queue.

            Flow

            Create Queue
                │
                ▼
            Discover Sitemap
                │
                ▼
            Filter URLs
                │
                ▼
            Add accepted URLs to queue
                │
                ▼
            If no URLs remain
                │
                ▼
            Seed queue with homepage
                │
                ▼
            Process queue
        """

        print("\n" + "=" * 80)
        print(f"Website : {source['website']}")
        print(f"Base URL: {source['base_url']}")
        print("=" * 80)

    # ---------------------------------------------------------
    # Create a fresh queue for this website
    # ---------------------------------------------------------

        queue = URLQueue()

        state_file = self.get_queue_state_filename(
            country,
            source,
        )

        loaded = queue.load_state(state_file)

        if loaded:
            print("Resuming previous crawl...")

        # ---------------------------------------------------------
        # Discover sitemap only for a new crawl
        # ---------------------------------------------------------

        if not loaded:

            print("Discovering sitemap...")

            sitemap_urls = SitemapDiscovery.discover(
                country=country,
                source=source,
            )

            print(f"Discovered {len(sitemap_urls)} URLs.")

            # ---------------------------------------------------------
            # Evaluate every discovered URL
            # ---------------------------------------------------------

            accepted = []

            for item in sitemap_urls:

                result = evaluate_url(item)

                item.update(result)

                if item["crawl"]:
                    accepted.append(item)

            print(f"Accepted {len(accepted)} sitemap URLs.")

            # ---------------------------------------------------------
            # Add accepted URLs to queue
            # ---------------------------------------------------------

            queue.add_many(accepted)

            # Save the initial queue
            queue.save_state(state_file)

    # ---------------------------------------------------------
    # If sitemap is empty,
    # crawl homepage first.
    # ---------------------------------------------------------

        if not loaded and not queue.has_urls():

            print("No usable sitemap found.")
            print("Adding homepage to queue.")

            homepage = {

                "url": source["base_url"],

                "type": "html",

                "country": country,

                "website": source["website"],

                "parent": None,

                "depth": 0,

                "anchor_text": None,

                "crawl": True,

                "priority": 100,

                "reason": "homepage",

            }

            queue.add(homepage)

        print(f"Initial Queue Size : {queue.queue_size()}")

    # ---------------------------------------------------------
    # Begin crawling
    # ---------------------------------------------------------

        await self.process_queue(
            page=page,
            queue=queue,
            country=country,
            source=source,
        )

    async def process_queue(self, page, queue, country, source):
        """
        Process URLs until the queue becomes empty or the crawl limit is reached.
        """

        pages_crawled = 0

        # State file for this website
        state_file = self.get_queue_state_filename(
            country,
            source,
        )

        while queue.has_urls():

            # ---------------------------------------------------------
            # Respect crawl limit
            # ---------------------------------------------------------

            if pages_crawled >= MAX_PAGES_PER_SOURCE:

                print("\nMaximum page limit reached.")

                # Save current queue before stopping
                queue.save_state(state_file)

                break

            # ---------------------------------------------------------
            # Get next URL
            # ---------------------------------------------------------

            item = queue.get_next()

            if item is None:
                break

            print("\n" + "-" * 80)
            print(f"URL      : {item['url']}")
            print(f"Priority : {item['priority']}")
            print(f"Depth    : {item['depth']}")
            print(f"Type     : {item['type']}")
            print("-" * 80)

            # ---------------------------------------------------------
            # Skip pages beyond maximum depth
            # ---------------------------------------------------------

            if item["depth"] > MAX_DEPTH:

                print("Maximum depth reached.")

                queue.mark_visited(item["url"])
                queue.save_state(state_file)

                continue

            try:

                # ---------------------------------------------------------
                # Visit page
                # ---------------------------------------------------------

                await self.browser.goto(item["url"])

                page = self.browser.page

                pages_crawled += 1

                print("Page loaded.")

                # ---------------------------------------------------------
                # PDFs
                # ---------------------------------------------------------

                if item["type"] == "pdf":

                    print("Downloading PDF...")

                    await self.save_pdf(
                        page,
                        item,
                        country,
                        source,
                    )

                    queue.mark_visited(item["url"])
                    queue.save_state(state_file)

                    continue


                # ---------------------------------------------------------
                # Save rendered HTML
                # ---------------------------------------------------------

                html = await page.content()

                filepath = self.get_html_filename(
                    country,
                    source,
                    item["url"],
                )

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(html)

                print(f"Saved HTML -> {filepath}")

                # ---------------------------------------------------------
                # Extract links
                # ---------------------------------------------------------

                discovered = await LinkExtractor.extract(
                    page=page,
                    source=source,
                    country=country,
                    depth=item["depth"],
                )

                print(f"Discovered {len(discovered)} links.")

                # ---------------------------------------------------------
                # Evaluate links
                # ---------------------------------------------------------

                accepted = []

                for link in discovered:

                    result = evaluate_url(link)

                    link.update(result)

                    if link["crawl"]:
                        accepted.append(link)

                print(f"Accepted {len(accepted)} links.")

                # ---------------------------------------------------------
                # Add new URLs
                # ---------------------------------------------------------

                queue.add_many(accepted)

                # Mark current page as successfully crawled
                queue.mark_visited(item["url"])

                # Save progress
                queue.save_state(state_file)

                print(f"Queue Size : {queue.queue_size()}")

            except Exception as e:

                print(f"Failed to crawl: {item['url']}")
                print(e)

                # Put failed page back in queue so it can be retried
                queue.add(item)

                # Save queue after failure
                queue.save_state(state_file)

        # ---------------------------------------------------------
        # Finished this website
        # ---------------------------------------------------------

        queue.save_state(state_file)

        print("Queue state saved.")
    
    # =============================================================================
    # Program Entry Point
    # =============================================================================

async def main():
        """
        Program entry point.

        Creates the crawler and starts it.
        """

        crawler = WebCrawler()

        await crawler.run()


if __name__ == "__main__":

    asyncio.run(main())