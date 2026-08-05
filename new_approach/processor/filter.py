from bs4 import BeautifulSoup
from pathlib import Path


class HTMLFilter:
    """
    Decides whether an HTML page should be processed.

    Responsibilities
    ----------------
    - Read HTML
    - Inspect URL/file name
    - Inspect title
    - Inspect visible text
    - Decide KEEP or SKIP

    It DOES NOT:
        - Clean HTML
        - Extract structured information
        - Generate embeddings
    """

    # ---------------------------------------------------------
    # Pages we almost never want
    # ---------------------------------------------------------

    SKIP_URL_KEYWORDS = {

        "privacy",
        "cookie",
        "cookies",
        "terms",
        "accessibility",
        "contact",
        "newsletter",
        "press",
        "media",
        "rss",

    }

    SKIP_TITLE_KEYWORDS = {

        "privacy",
        "cookie",
        "terms",
        "accessibility",
        "newsletter",

    }

    RELEVANT_KEYWORDS = {

        "visa",
        "permit",
        "passport",
        "application",
        "immigration",
        "residence",
        "documents",
        "requirements",
        "embassy",
        "consulate",

    }

    MIN_WORDS = 150

    @staticmethod
    def evaluate(html_path):
        """
        Returns

        {
            "keep": True,
            "reason": "Relevant page",
            "title": "...",
            "word_count": 712
        }
        """

        html_path = Path(html_path)

        with open(html_path, encoding="utf-8") as f:
            html = f.read()

        soup = BeautifulSoup(html, "html.parser")

        # -----------------------------------------------------
        # Title
        # -----------------------------------------------------

        title = ""

        if soup.title:

            title = soup.title.get_text(" ", strip=True)

        title_lower = title.lower()

        # -----------------------------------------------------
        # Filename
        # -----------------------------------------------------

        filename = html_path.name.lower()

        # -----------------------------------------------------
        # URL/Filename rules
        # -----------------------------------------------------

        for keyword in HTMLFilter.SKIP_URL_KEYWORDS:

            if keyword in filename:

                return {

                    "keep": False,

                    "reason": f"Filename contains '{keyword}'",

                    "title": title,

                    "word_count": 0,

                }

        # -----------------------------------------------------
        # Title rules
        # -----------------------------------------------------

        for keyword in HTMLFilter.SKIP_TITLE_KEYWORDS:

            if keyword in title_lower:

                return {

                    "keep": False,

                    "reason": f"Title contains '{keyword}'",

                    "title": title,

                    "word_count": 0,

                }

        # -----------------------------------------------------
        # Remove obvious junk
        # -----------------------------------------------------

        for tag in soup(

            [
                "script",
                "style",
                "noscript",
                "svg",
                "footer",
                "header",
                "nav",
                "aside",
            ]

        ):
            tag.decompose()

        # -----------------------------------------------------
        # Visible text
        # -----------------------------------------------------

        text = soup.get_text(" ", strip=True)

        words = text.split()

        word_count = len(words)

        # -----------------------------------------------------
        # Too short
        # -----------------------------------------------------

        if word_count < HTMLFilter.MIN_WORDS:

            return {

                "keep": False,

                "reason": "Too little content",

                "title": title,

                "word_count": word_count,

            }

        # -----------------------------------------------------
        # Relevant keywords
        # -----------------------------------------------------

        text_lower = text.lower()

        hits = 0

        for keyword in HTMLFilter.RELEVANT_KEYWORDS:

            if keyword in text_lower:

                hits += 1

        if hits == 0:

            return {

                "keep": False,

                "reason": "No immigration keywords",

                "title": title,

                "word_count": word_count,

            }

        return {

            "keep": True,

            "reason": "Relevant page",

            "title": title,

            "word_count": word_count,

        }