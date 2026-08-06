import gzip
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urljoin


class SitemapDiscovery:
    """
    SitemapDiscovery

    Responsibility
    --------------
    Discover URLs published in a website's sitemap.

    This module ONLY discovers URLs.

    It DOES NOT:
        • visit webpages
        • render JavaScript
        • scrape HTML
        • filter URLs
        • assign priorities
        • save files

    Every discovered URL is returned as a metadata object.

    That object will later pass through:

        filters.py
            ↓
        url_queue.py
            ↓
        browser.py
    """

    # ---------------------------------------------------------
    # Common sitemap locations
    # Used if robots.txt doesn't specify one.
    # ---------------------------------------------------------

    COMMON_SITEMAPS = [
        "/sitemap.xml",
        "/sitemap_index.xml",
        "/sitemap-index.xml",
        "/sitemap.xml.gz",
    ]

    # ---------------------------------------------------------
    # STEP 1
    # Find sitemap from robots.txt
    # ---------------------------------------------------------

    @staticmethod
    def find_sitemap(base_url):

        robots_url = urljoin(base_url, "/robots.txt")

        try:

            response = requests.get(
                robots_url,
                timeout=10,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            if response.status_code == 200:

                for line in response.text.splitlines():

                    if line.lower().startswith("sitemap:"):

                        return line.split(":", 1)[1].strip()

        except Exception:
            pass

        return None

    # ---------------------------------------------------------
    # STEP 2
    # Download sitemap and extract URLs
    # ---------------------------------------------------------

    @classmethod
    def extract_urls(cls, sitemap_url, source, country):

        try:

            response = requests.get(
                sitemap_url,
                timeout=20,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            if response.status_code != 200:
                return []

            # --------------------------------------------
            # Handle compressed sitemaps (.xml.gz)
            # --------------------------------------------

            content = response.content

            if sitemap_url.endswith(".gz"):
                content = gzip.decompress(content)

            root = ET.fromstring(content)

            namespace = {
                "ns": "http://www.sitemaps.org/schemas/sitemap/0.9"
            }

            # ======================================================
            # CASE 1 : Sitemap Index
            # ======================================================

            if root.tag.endswith("sitemapindex"):

                all_urls = []

                for sitemap in root.findall(
                    ".//ns:sitemap/ns:loc",
                    namespace
                ):

                    child_urls = cls.extract_urls(
                        sitemap.text.strip(),
                        source,
                        country,
                    )

                    all_urls.extend(child_urls)

                # Remove duplicates
                unique = []
                seen = set()

                for item in all_urls:

                    if item["url"] not in seen:
                        seen.add(item["url"])
                        unique.append(item)

                return unique

            # ======================================================
            # CASE 2 : Normal Sitemap
            # ======================================================

            urls = []

            for url_node in root.findall(".//ns:url", namespace):

                loc = url_node.find("ns:loc", namespace)

                if loc is None:
                    continue

                url = loc.text.strip()

                lastmod = url_node.find("ns:lastmod", namespace)

                changefreq = url_node.find("ns:changefreq", namespace)

                sitemap_priority = url_node.find("ns:priority", namespace)

                urls.append({

                    "url": url,

                    "type": "pdf"
                    if url.lower().endswith(".pdf")
                    else "html",

                    "parent": None,

                    "website": source["website"],

                    "country": country,

                    "depth": 0,


                    "anchor_text": None,

                    "lastmod":
                        lastmod.text if lastmod is not None else None,

                    "changefreq":
                        changefreq.text if changefreq is not None else None,

                    "sitemap_priority":
                        sitemap_priority.text
                        if sitemap_priority is not None
                        else None,
                })

            # Remove duplicates

            unique = []
            seen = set()

            for item in urls:

                if item["url"] not in seen:
                    seen.add(item["url"])
                    unique.append(item)

            return unique

        except Exception:

            return []

            # ---------------------------------------------------------
        # STEP 3
        # Main entry point used by crawler.py
        # ---------------------------------------------------------

    @classmethod
    def discover(cls, source, country):
        """
        Discover all URLs published in a website's sitemap.

        Parameters
        ----------
        source : dict
            Website configuration from config.py

        country : str
            Country this website belongs to.

        Returns
        -------
        List of URL metadata objects.
        """

        base_url = source["base_url"]

        # -----------------------------------------------------
        # Try robots.txt first
        # -----------------------------------------------------

        sitemap = cls.find_sitemap(base_url)

        if sitemap:

            print(f"[SITEMAP] Found in robots.txt -> {sitemap}")

            urls = cls.extract_urls(
                sitemap,
                source,
                country,
            )

            if urls:

                print(f"[SITEMAP] Discovered {len(urls)} URLs")

                return urls

        # -----------------------------------------------------
        # Otherwise try common locations
        # -----------------------------------------------------

        for candidate in cls.COMMON_SITEMAPS:

            sitemap = urljoin(base_url, candidate)

            print(f"[SITEMAP] Trying {sitemap}")

            urls = cls.extract_urls(
                sitemap,
                source,
                country,
            )

            if urls:

                print(f"[SITEMAP] Discovered {len(urls)} URLs")

                return urls

        print("[SITEMAP] No sitemap found.")

        return []
"""
Purpose

This module discovers URLs published by a website.

It does NOT decide whether those URLs should be crawled.

That decision belongs to filters.py.

===========================================================================

Architecture

                    Base URL
                        │
                        ▼
                  robots.txt
                        │
                        ▼
              Find sitemap location
                        │
                        ▼
             Download sitemap XML
                        │
                        ▼
      Extract URL metadata objects
                        │
                        ▼
                 Return URLs

===========================================================================

Returned Object

Each discovered URL is returned as

{
    "url": "...",

    "type": "html" | "pdf",

    "parent": None,

    "website": "German.."

    "depth": 0,

    "anchor_text": None,

    "lastmod": "...",

    "changefreq": "...",

    "sitemap_priority": "0.8"
}

This object is later passed to

filters.py

which decides

    • Crawl?
    • Priority?
"""



# import requests
# import xml.etree.ElementTree as ET
# from urllib.parse import urljoin


# class SitemapDiscovery:
#     """
#     SitemapDiscovery

#     Responsibility:
#         Discover URLs published in a website's sitemap.

#     Important:
#         This class ONLY discovers URLs.
#         It does NOT:
#             - visit webpages
#             - scrape HTML
#             - extract content
#             - filter URLs
#             - save data

#     The crawler will later decide which URLs should actually be visited.
#     """

#     # Common sitemap locations used if robots.txt does not specify one
#     COMMON_SITEMAPS = [
#         "/sitemap.xml",
#         "/sitemap_index.xml",
#         "/sitemap-index.xml",
#     ]

#     @staticmethod
#     def find_sitemap(base_url):
#         """
#         Step 1
#         Read robots.txt and look for:

#             Sitemap: https://example.com/sitemap.xml

#         Returns:
#             sitemap URL if found
#             otherwise None
#         """

#         robots_url = urljoin(base_url, "/robots.txt")

#         try:
#             response = requests.get(robots_url, timeout=10)

#             if response.status_code == 200:

#                 for line in response.text.splitlines():

#                     if line.lower().startswith("sitemap:"):
#                         return line.split(":", 1)[1].strip()

#         except Exception:
#             pass

#         return None

#     @staticmethod
#     def extract_urls(sitemap_url):
#         """
#         Step 2

#         Download the sitemap XML.

#         Example:

#         <urlset>
#             <url>
#                 <loc>https://example.com/visa</loc>
#             </url>
#         </urlset>

#         Returns:
#             List of URLs
#         """

#         try:

#             response = requests.get(sitemap_url, timeout=15)

#             if response.status_code != 200:
#                 return []

#             root = ET.fromstring(response.content)

#             urls = []

#             namespace = {
#                 "ns": "http://www.sitemaps.org/schemas/sitemap/0.9"
#             }

#             for loc in root.findall(".//ns:loc", namespace):
#                 urls.append(loc.text)

#             return urls

#         except Exception:
#             return []

#     @classmethod
#     def discover(cls, base_url):
#         """
#         Main function used by crawler.py
#         Flow
#         Base URL
#              ↓
#         robots.txt
#              ↓
#         Find sitemap
#              ↓
#         Download XML
#              ↓
#         Extract URLs
#              ↓
#         Return URL list
#         """

#         sitemap = cls.find_sitemap(base_url)

#         if sitemap:
#             return cls.extract_urls(sitemap)

#         # If robots.txt doesn't mention a sitemap,
#         # try common sitemap locations.
#         for candidate in cls.COMMON_SITEMAPS:

#             sitemap = urljoin(base_url, candidate)

#             urls = cls.extract_urls(sitemap)

#             if urls:
#                 return urls

#         return []


# """
# ===========================================================================
# CURRENT VERSION (v1)
# ===========================================================================

# This is intentionally a simple implementation.

# Goal:
#     Discover URLs from a website sitemap.

# This module DOES NOT crawl the website.

# It simply answers the question:

#     "What pages does this website advertise?"

# ===========================================================================

# Future Improvements (v2)

# 1. Support Sitemap Indexes

# Many large government websites don't have one sitemap.

# Instead they have:

# sitemap_index.xml
#     ├── sitemap-pages.xml
#     ├── sitemap-news.xml
#     ├── sitemap-images.xml

# Future version should recursively visit each child sitemap.

# ---------------------------------------------------------------------------

# 2. Support .xml.gz files

# Some websites compress their sitemap.

# Example:

#     sitemap.xml.gz

# Future version should automatically decompress and parse these files.

# ---------------------------------------------------------------------------

# 3. Cache sitemap results

# Downloading the same sitemap repeatedly wastes time.

# Future version should cache results so each sitemap is only downloaded once.

# ---------------------------------------------------------------------------

# 4. Extract metadata

# Sitemaps often contain useful metadata:

#     <lastmod>
#     <priority>
#     <changefreq>

# Example:

# <url>
#     <loc>https://example.com/work-visa</loc>
#     <lastmod>2026-06-18</lastmod>
#     <priority>0.8</priority>
# </url>

# We can later use this information to:

#     • Skip unchanged pages
#     • Prioritize important pages
#     • Perform incremental crawling

# ---------------------------------------------------------------------------

# 5. URL Filtering

# This module intentionally returns ALL URLs.

# Filtering belongs in filters.py.

# Keeping responsibilities separate makes the system easier to maintain.

# ===========================================================================
# """