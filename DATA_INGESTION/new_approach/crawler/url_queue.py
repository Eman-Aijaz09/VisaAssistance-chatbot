import heapq
import json
from pathlib import Path

class URLQueue:
    """
    URLQueue

    Responsibility
    --------------
    Manage which URLs should be crawled next.

    This class does NOT:
        - Visit webpages
        - Scrape HTML
        - Extract links
        - Filter URLs
        - Assign priorities

    All URLs reaching this queue have already been
    accepted by filters.py.

    This class is responsible for:

        1. Storing accepted URLs
        2. Returning the highest-priority URL first
        3. Preventing duplicate crawling

    Think of it as the crawler's task manager.
    """

    def __init__(self):

        # Priority queue
        #
        # heapq is a min-heap, therefore we store
        # negative priority so that larger priorities
        # are returned first.
        #
        # Example:
        #
        # (-100, url_info)
        # (-90, url_info)
        # (-50, url_info)
        #
        self.to_visit = []

        # Used to break ties when two URLs have the same priority.
        # This preserves insertion order and avoids comparing dictionaries.
        
        self.counter = 0

        # URLs already crawled
        self.visited = set()

        # URLs currently waiting
        self.in_queue = set()

    def save_state(self, filepath):
        """
        Save queue and visited URLs.
        """

        state = {

            "visited": list(self.visited),

            "queue": [item for _, _, item in self.to_visit]

        }

        with open(filepath, "w", encoding="utf-8") as f:

            json.dump(state, f, indent=2)

    def load_state(self, filepath):

        path = Path(filepath)

        if not path.exists():
            return False

        with open(path, "r", encoding="utf-8") as f:

            state = json.load(f)

        self.visited = set(state["visited"])

        self.to_visit.clear()
        self.in_queue.clear()

        self.counter = 0

        for item in state["queue"]:

            self.add(item)

        print(f"Loaded {len(self.visited)} visited URLs.")

        return True

    def add(self, item):
        """
        Add a URL to the crawl queue.

        Expected format

        item = {
            "url": "...",
            "type": "html",
            "parent": "...",
            "source": "html",
            "depth": 2,
            "anchor_text": "...",
            "priority": 85
        }
        """

        url = item["url"]

        # Ignore rejected URLs
        if not item.get("crawl", False):
            return

        if url in self.visited:
            return

        if url in self.in_queue:
            return
        priority = item["priority"]

        # Negative priority because heapq pops
        # the smallest value first.
        heapq.heappush(
            self.to_visit,
            (-priority, self.counter, item)
        )

        # Increment counter for the next URL
        self.counter += 1

        self.in_queue.add(url)

    def add_many(self, items):
        """
        Add multiple URL objects.
        """

        for item in items:
            self.add(item)

    def get_next(self):
        """
        Returns the highest-priority URL.

        Example
        {
            "url": "...",
            "type": "html",

            "country": "Germany",
            "website": "German Embassy Pakistan",

            "parent": "...",
            "depth": 1,
            "anchor_text": None,

            "crawl": True,
            "priority": 95,
            "reason": "accepted",
        }

        Returns None if queue is empty.
        """

        if not self.to_visit:
            return None

        _, _, item = heapq.heappop(self.to_visit)

        url = item["url"]

        self.in_queue.remove(url)
       # self.visited.add(url)

        return item

    def mark_visited(self, url):
        """
        Mark a URL as successfully crawled.
        """

        self.visited.add(url)

    def has_urls(self):
        """
        Returns True if URLs are waiting.
        """

        return len(self.to_visit) > 0

    def queue_size(self):
        """
        Number of URLs waiting.
        """

        return len(self.to_visit)

    def visited_count(self):
        """
        Number of crawled URLs.
        """

        return len(self.visited)

"""
===========================================================================
CURRENT VERSION
===========================================================================

Purpose

This module manages the crawler's work queue.

It remembers:

    • URLs waiting to be crawled
    • URLs already crawled

this queue is PRIORITY-BASED.
The highest-priority URL is always crawled first.

===========================================================================

Flow

                    sitemap.py
                         │
                         ▼

                 URL metadata object

                         │

                    filters.py
      (reject junk + assign priority)

                         │

                         ▼

                    add_many()

                         │

HTML pages ──► link_extractor.py

                         │

                         ▼

                    filters.py

                         │

                         ▼

                    add_many()

                         │

                +----------------------+
                |      URL Queue       |
                +----------------------+
                | Priority Queue       |
                | Visited URLs         |
                +----------------------+

                         │

                 crawler.py asks

                     get_next()

                         ▼

        Highest-priority URL returned

===========================================================================

URL Object

Every item inside the queue has the format

item = {
    "url": "...",
    "type": "html",

    "country": "Germany",
    "website": "German Embassy Pakistan",

    "parent": "...",
    "depth": 2,
    "anchor_text": "Work Visa",

    "crawl": True,
    "priority": 85,
    "reason": "accepted",
}

===========================================================================

Future Improvements

1. Dynamic Priority

Instead of fixed scores, adjust priority based on:

    • Parent page relevance
    • Previous crawl results
    • Content relevance
    • LLM scoring

---------------------------------------------------------------------------

2. Retry Failed URLs

Retry temporary failures instead of discarding them.

---------------------------------------------------------------------------

3. Persist Queue

Save queue to disk so crawling can resume after interruption.

---------------------------------------------------------------------------

4. Canonicalization

Normalize URLs so these are treated as the same page:

/page
/page/
/page#section
/page?utm_source=google

---------------------------------------------------------------------------

5. Crawl Budget

Support limits such as:

Maximum pages per domain
Maximum crawl depth
Maximum PDFs
Maximum crawl time

==========================================================================="""