#scraper_utils.py
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
)
from utils.discovery_utils import get_source_config

import os
import re
from datetime import datetime

def get_browser_config() -> BrowserConfig:
    return BrowserConfig(
        browser_type="chromium",
        headless=False,
        verbose=True,
        enable_stealth=True, 
    )


async def fetch_page(crawler: AsyncWebCrawler, url: str, _attempt: int = 1):
    cfg = get_source_config(url)
    css_selector = cfg.get("css_selector")
    anti_bot = cfg.get("anti_bot", False)
    max_attempts = 3 if anti_bot else 1

    result = await crawler.arun(
        url=url,
        config=CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            css_selector=css_selector,
            magic=anti_bot,
            simulate_user=anti_bot,
            override_navigator=anti_bot,
            wait_until="load" if anti_bot else "domcontentloaded",
            page_timeout=30000,
            delay_before_return_html=5.0 if anti_bot else 0.1,
            max_retries=3 if anti_bot else 0,
        ),
    )

    if not result.success and _attempt < max_attempts:
        print(f"Retrying {url} (attempt {_attempt + 1}/{max_attempts})")
        return await fetch_page(crawler, url, _attempt + 1)

    if not result.success:
        print(f"\nFailed to crawl: {url}")
        print(result.error_message)
        return None

    return result

def extract_page_content(result) -> str:
    if result.markdown:
        return result.markdown

    if result.cleaned_html:
        return result.cleaned_html

    return result.html or ""


def extract_internal_links(result):
    if not result.links:
        return []

    return [
        link["href"]
        for link in result.links.get("internal", [])
        if link.get("href")
    ]


def get_page_title(result):
    if hasattr(result, "metadata"):
        return result.metadata.get("title", "")

    return ""



# #scraper_utils.py
# from crawl4ai import (
#     AsyncWebCrawler,
#     BrowserConfig,
#     CacheMode,
#     CrawlerRunConfig,
# )
# from config import CSS_SELECTOR

# import os
# import re
# from datetime import datetime


# def safe_filename(url: str) -> str:
#     """Convert a URL into a safe filename."""
#     name = re.sub(r'https?://', '', url)
#     name = re.sub(r'[^a-zA-Z0-9]+', '_', name)
#     return name[:100]


# def save_markdown(content: str, url: str, output_dir: str = "scraped_output") -> str:
#     """
#     Save scraped markdown content to a file.

#     Parameters
#     ----------
#     content : str
#         The markdown/text content to save.
#     url : str
#         Source URL, used to generate the filename.
#     output_dir : str
#         Directory to save files in.

#     Returns
#     -------
#     str
#         Path to the saved file.
#     """
#     os.makedirs(output_dir, exist_ok=True)

#     filename = f"{safe_filename(url)}.md"
#     filepath = os.path.join(output_dir, filename)

#     with open(filepath, "w", encoding="utf-8") as f:
#         f.write(f"<!-- Source: {url} -->\n")
#         f.write(f"<!-- Scraped: {datetime.now().isoformat()} -->\n\n")
#         f.write(content)

#     print(f"Saved markdown -> {filepath}")
#     return filepath


# def get_browser_config() -> BrowserConfig:
#     """
#     Browser configuration for Crawl4AI.
#     """

#     return BrowserConfig(
#         browser_type="chromium",
#         headless=False,
#         verbose=True,
#     )


# async def fetch_page(
#     crawler: AsyncWebCrawler,
#     url: str,
# ):
#     """
#     Fetch a webpage and return the Crawl4AI result.

#     Parameters
#     ----------
#     crawler : AsyncWebCrawler
#     url : str

#     Returns
#     -------
#     CrawlResult | None
#     """

#     result = await crawler.arun(
#         url=url,
#         config=CrawlerRunConfig(
#             cache_mode=CacheMode.BYPASS,
#             css_selector=CSS_SELECTOR, 
#         ),
#     )

#     if not result.success:
#         print(f"\nFailed to crawl: {url}")
#         print(result.error_message)
#         return None

#     return result


# def extract_page_content(result) -> str:
#     """
#     Returns the best textual representation of a webpage.

#     Preference:
#         Markdown
#         Cleaned HTML
#         Raw HTML
#     """

#     if result.markdown:
#         return result.markdown

#     if result.cleaned_html:
#         return result.cleaned_html

#     return result.html or ""


# def extract_internal_links(result):

#     """
#     Returns all discovered internal links.
#     """

#     if not result.links:
#         return []

#     return [
#         link["href"]
#         for link in result.links.get("internal", [])
#         if link.get("href")
#     ]


# def get_page_title(result):

#     if hasattr(result, "metadata"):
#         return result.metadata.get("title", "")

#     return ""