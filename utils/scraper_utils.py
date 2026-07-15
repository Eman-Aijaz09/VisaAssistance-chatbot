from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
)
from config import CSS_SELECTOR


def get_browser_config() -> BrowserConfig:
    """
    Browser configuration for Crawl4AI.
    """

    return BrowserConfig(
        browser_type="chromium",
        headless=False,
        verbose=True,
    )


async def fetch_page(
    crawler: AsyncWebCrawler,
    url: str,
):
    """
    Fetch a webpage and return the Crawl4AI result.

    Parameters
    ----------
    crawler : AsyncWebCrawler
    url : str

    Returns
    -------
    CrawlResult | None
    """

    result = await crawler.arun(
        url=url,
        config=CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            css_selector=CSS_SELECTOR, 
        ),
    )

    if not result.success:
        print(f"\nFailed to crawl: {url}")
        print(result.error_message)
        return None

    return result


def extract_page_content(result) -> str:
    """
    Returns the best textual representation of a webpage.

    Preference:
        Markdown
        Cleaned HTML
        Raw HTML
    """

    if result.markdown:
        return result.markdown

    if result.cleaned_html:
        return result.cleaned_html

    return result.html or ""


def extract_internal_links(result):

    """
    Returns all discovered internal links.
    """

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