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
# Post-crawl exclusion (title/content based)
# ==============================
# Pages matching these are skipped BEFORE the LLM call — catches junk
# that URL-based filtering can't see (e.g. diplo.de uses opaque numeric
# IDs in URLs, so title/content is the only reliable signal).

# Applies to ALL countries — CMS/platform-level placeholder markers,
# not tied to any language. Confirmed so far only on diplo.de (Germany);
# revisit once other countries are live to see what's actually shared.
UNIVERSAL_PLACEHOLDER_MARKERS = [
    "(dummy)",
]

# Per-country, language-specific junk categories (non-visa consular
# services: inheritance, notarization, police certificates, complaints,
# etc). Add an entry here when a new country is enabled.
EXCLUDED_TITLE_KEYWORDS = {
    "Germany": [
        "erbschaftsangelegenheiten",   # inheritance matters
        "beglaubigungen",              # document authentication/notarization
        "führungszeugnis",             # police certificate requests
        "complaints about",            # complaints process
        "zoll",
        "anwälten, ärzten und übersetzern",
    ],
    "France": [],
    "Qatar": [],
}

# Per-country placeholder/stub content markers found IN the page body
# (not just the title) — e.g. literal CMS dummy Q&A text.
PLACEHOLDER_CONTENT_MARKERS = {
    "Germany": [
        "frage 1 ?",
        "antwort 1 !",
    ],
    "France": [],
    "Qatar": [],
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