from urllib.parse import (
    urljoin,
    urlparse,
    urlunparse,
    parse_qsl,
    urlencode,
)


class LinkExtractor:
    """
    ================================================================

    LinkExtractor

    Responsibility
    --------------

    Discover links from a rendered webpage.

    Input
    -----
    Playwright page object

    Output
    ------
    List of URL metadata objects.

    This class DOES NOT

        • visit URLs
        • filter URLs
        • assign priorities
        • save data

    It ONLY discovers links.

    ================================================================

    Flow

    Rendered HTML
            │
            ▼
    Find every <a href="">
            │
            ▼
    Convert relative URLs to absolute URLs
            │
            ▼
    Ignore unwanted links
            │
            ▼
    Normalize URLs
            │
            ▼
    Return URL metadata

    ================================================================
    """

    TRACKING_PARAMS = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "gclid",
        "fbclid",
    }

    # ---------------------------------------------------------
    # Normalize URLs
    # ---------------------------------------------------------

    @staticmethod
    def normalize_url(url):
        """
        Convert different versions of the same page
        into one canonical URL.

        Examples

        /visa/

        /visa

        /visa#section

        /visa?utm_source=google

        all become

        /visa
        """

        parsed = urlparse(url)

        query = parse_qsl(parsed.query)

        filtered_query = [
            (k, v)
            for k, v in query
            if k.lower() not in LinkExtractor.TRACKING_PARAMS
        ]

        path = parsed.path

        if path != "/":
            path = path.rstrip("/")

        normalized = parsed._replace(
            path=path,
            query=urlencode(filtered_query),
            fragment=""
        )

        return urlunparse(normalized)

    # ---------------------------------------------------------
    # Extract links
    # ---------------------------------------------------------

    @staticmethod
    async def extract(page, source, country, depth):
        """
        Discover all internal links from the page.

        Returns

        [
            {
                "url": "...",
                "type": "html",
                "parent": "...",
                "source": "page",
                "depth": 1,
                "anchor_text": "Work Visa"
            }
        ]
        """

        current_url = page.url
        current_domain = urlparse(current_url).netloc

        links = await page.locator("a").evaluate_all("""
        elements => elements.map(a => ({
            href: a.getAttribute("href"),
            text: a.innerText.trim()
        }))
        """)

        discovered = []

        seen = set()

        for link in links:

            href = link["href"]
            text = link["text"]

            if not href:
                continue

            href = href.strip()

            if href.startswith("#"):
                continue

            if href.startswith("javascript:"):
                continue

            if href.startswith("mailto:"):
                continue

            if href.startswith("tel:"):
                continue

            # Ignore browser-generated resources
            if (
                href.startswith("blob:")
                or href.startswith("data:")
                or href.startswith("chrome-extension:")
            ):
                continue

            absolute = urljoin(current_url, href)
            if absolute.startswith(("blob:", "data:", "chrome-extension:")):
                continue

            parsed = urlparse(absolute)

            # Skip external websites
            if parsed.netloc not in source["allowed_domains"]:
                continue    

            normalized = LinkExtractor.normalize_url(absolute)

            if normalized in seen:
                continue

            seen.add(normalized)

            if normalized.lower().endswith(".pdf"):
                doc_type = "pdf"
            else:
                doc_type = "html"

            discovered.append({

                "url": normalized,

                "type": doc_type,

                "parent": current_url,

                "depth": depth + 1,

                "anchor_text": text,

                "country": country,

                "website": source["website"],

            })

        return discovered


"""
===========================================================================
CURRENT VERSION (v3)
===========================================================================

Purpose

Discover links from rendered webpages.

Unlike sitemap.py, this discovers only the links that are actually present
on the page after JavaScript has finished rendering.

===========================================================================

Flow

Browser
    │
    ▼
Rendered HTML
    │
    ▼
Find every <a href="">
    │
    ▼
Convert relative URLs to absolute URLs
    │
    ▼
Remove

    • JavaScript links
    • Email links
    • Telephone links
    • External websites

    │
    ▼
Normalize URLs
    │
    ▼
Return URL metadata

===========================================================================

Returned Object

Each discovered link looks like

{
    "url": "...",

    "type": "html" | "pdf",

    "parent": "https://site.com",

    "depth": 2,

    "country": country,
    
    "website": source["website"],

    "anchor_text": "Work Visa",

}

Notice that priority is NOT assigned here.

That is the responsibility of filters.py.

===========================================================================

Future Improvements

1. Detect link location

Record whether a link came from

    • Header
    • Footer
    • Sidebar
    • Main content

Links in the main content are usually more useful than navigation menus.

-------------------------------------------------------------

2. Capture surrounding context

Instead of storing only the anchor text

    Work Visa

also capture the nearby paragraph or section heading.

This provides richer context for relevance scoring.

-------------------------------------------------------------

3. Detect file types beyond PDFs

Examples

.doc
.docx
.xls
.xlsx
.csv
.zip

These can then be routed to specialized processors.

-------------------------------------------------------------

4. Extract structured navigation

Some websites expose breadcrumbs or menu hierarchies.

Capturing this structure helps reconstruct the site's organization.

===========================================================================
"""