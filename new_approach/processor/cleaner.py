from bs4 import BeautifulSoup, Comment
import trafilatura
import re


class HTMLCleaner:
    """
    Cleans HTML pages into readable text.

    Responsibilities
    ----------------
    ✓ Remove boilerplate
    ✓ Extract main article
    ✓ Normalize whitespace
    ✓ Return clean text
    """

    @staticmethod
    def clean(html):

        # ---------------------------------------------------------
        # First try Trafilatura
        # ---------------------------------------------------------

        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            include_links=False,
            favor_precision=True,
        )

        if text:

            return HTMLCleaner.normalize(text)

        # ---------------------------------------------------------
        # Fallback to BeautifulSoup
        # ---------------------------------------------------------

        soup = BeautifulSoup(html, "lxml")

        remove_tags = [

            "script",
            "style",
            "noscript",
            "svg",
            "canvas",
            "iframe",
            "footer",

        ]

        for tag in remove_tags:

            for element in soup.find_all(tag):

                element.decompose()

        # Remove HTML comments

        for comment in soup.find_all(
            string=lambda t: isinstance(t, Comment)
        ):

            comment.extract()

        text = soup.get_text(
            separator="\n",
            strip=True,
        )

        return HTMLCleaner.normalize(text)

    @staticmethod
    def normalize(text):

        # Convert multiple spaces to one
        text = re.sub(r"[ \t]+", " ", text)

        # Remove trailing spaces
        text = re.sub(r" *\n *", "\n", text)

        # Collapse 3+ blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()