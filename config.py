# config.py

# ==============================
# Seed URL(s) — grouped by country
# ==============================

SEED_URLS = {
    "Germany": [
        "https://pakistan.diplo.de",
        # "https://www.make-it-in-germany.com/"
    ],
    # "France": [
    #     "https://...",
    # ],
    # "Qatar": [
    #     "https://...",
    # ],
}

# ==============================
# Language preference (per country, where sites are multilingual)
# ==============================

PREFERRED_LANGUAGE_PATH = {
    "Germany": "/pk-en/",   # pakistan.diplo.de mirrors content in /pk-de/ and /pk-en/
}

# ==============================
# Relevance filtering (per country)
# ==============================

# Used by discovery_utils.is_relevant_url() to filter out irrelevant
# pages (press releases, contact forms, etc.) found via sitemap/BFS.
COUNTRY_KEYWORDS = {
    "Germany": ["visa", "visum", "aufenthalt", "einreise", "staatsangehoerigkeit"],
    "France": ["visa", "visas", "venir-en-france", "titre-de-sejour"],
    "Qatar": ["visa", "visit-visa", "residence-permit", "immigration"],
}


# ==============================
# Crawl Settings
# ==============================

# Leave None if you want Crawl4AI to extract the whole page.
# Use a selector only if the website has a consistent content container.
CSS_SELECTOR = "#main"

MAX_PAGES = 60
MAX_DEPTH = 3


# ==============================
# Validation
# ==============================

REQUIRED_KEYS = [
    "country",
    "purpose",
    "topic",
    "title",
    "summary",
]


# ==============================
# Output
# ==============================

OUTPUT_CSV = "germany_knowledge.csv"


# ==============================
# LLM
# ==============================

MODEL = "llama-3.3-70b-versatile"