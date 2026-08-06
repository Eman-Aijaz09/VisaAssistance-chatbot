# # config.py

# # ==============================
# # Seed URL(s) — grouped by country
# # ==============================

# SEED_URLS = {
#     "Germany": [
#         #"https://pakistan.diplo.de",
#         "https://www.make-it-in-germany.com/"
#     ],
#     # "France": [
#     #     "https://...",
#     # ],
#     # "Qatar": [
#     #     "https://...",
#     # ],
# }

# # ==============================
# # Language preference (per country, where sites are multilingual)
# # ==============================

# PREFERRED_LANGUAGE_PATH = {
#     "Germany": "/pk-en/",   # pakistan.diplo.de mirrors content in /pk-de/ and /pk-en/
# }

# # ==============================
# # Relevance filtering (per country)
# # ==============================

# # Used by discovery_utils.is_relevant_url() to filter out irrelevant
# # pages (press releases, contact forms, etc.) found via sitemap/BFS.
# COUNTRY_KEYWORDS = {
#     "Germany": ["visa", "visum", "aufenthalt", "einreise", "staatsangehoerigkeit"],
#     "France": ["visa", "visas", "venir-en-france", "titre-de-sejour"],
#     "Qatar": ["visa", "visit-visa", "residence-permit", "immigration"],
# }

# # ==============================
# # Post-crawl exclusion (title/content based)
# # ==============================
# # Pages matching these are skipped BEFORE the LLM call — catches junk
# # that URL-based filtering can't see (e.g. diplo.de uses opaque numeric
# # IDs in URLs, so title/content is the only reliable signal).

# # Applies to ALL countries — CMS/platform-level placeholder markers,
# # not tied to any language. Confirmed so far only on diplo.de (Germany);
# # revisit once other countries are live to see what's actually shared.
# UNIVERSAL_PLACEHOLDER_MARKERS = [
#     "(dummy)",
# ]

# # Per-country, language-specific junk categories (non-visa consular
# # services: inheritance, notarization, police certificates, complaints,
# # etc). Add an entry here when a new country is enabled.
# EXCLUDED_TITLE_KEYWORDS = {
#     "Germany": [
#         "erbschaftsangelegenheiten",   # inheritance matters
#         "beglaubigungen",              # document authentication/notarization
#         "führungszeugnis",             # police certificate requests
#         "complaints about",            # complaints process
#         "zoll",
#         "anwälten, ärzten und übersetzern",
#     ],
#     "France": [],
#     "Qatar": [],
# }

# # Per-country placeholder/stub content markers found IN the page body
# # (not just the title) — e.g. literal CMS dummy Q&A text.
# PLACEHOLDER_CONTENT_MARKERS = {
#     "Germany": [
#         "frage 1 ?",
#         "antwort 1 !",
#     ],
#     "France": [],
#     "Qatar": [],
# }

# # ==============================
# # Crawl Settings
# # ==============================

# # Leave None if you want Crawl4AI to extract the whole page.
# # Use a selector only if the website has a consistent content container.
# CSS_SELECTOR = "#main"

# MAX_PAGES = 60
# MAX_DEPTH = 3


# # ==============================
# # Validation
# # ==============================

# REQUIRED_KEYS = [
#     "country",
#     "purpose",
#     "topic",
#     "title",
#     "summary",
# ]


# # ==============================
# # Output
# # ==============================

# OUTPUT_CSV = "germany_knowledge.csv"


# # ==============================
# # LLM
# # ==============================

# MODEL = "llama-3.3-70b-versatile"


# config.py

# ==============================
# Source configuration — ONE ENTRY PER WEBSITE
# ==============================
# Everything specific to a given website lives here: which country it
# belongs to, how to extract its content, and how to filter its junk.
#
# To add a new source: add one block below, keyed by domain (netloc only,
# no https://, no trailing slash).
# To remove a source: delete its block. Nothing else needs to change.

SOURCE_CONFIG = {

    "pakistan.diplo.de": {
        "country": "Germany",
        "css_selector": "#main",
        "preferred_language_path": "/pk-en/",
        "content_path_hints": ["/service/", "-visa-", "/visa"],
        "excluded_url_path_patterns": [],
        "keywords": ["visa", "visum", "aufenthalt", "einreise", "staatsangehoerigkeit"],
        "excluded_title_keywords": [
            "erbschaftsangelegenheiten", "beglaubigungen", "führungszeugnis",
            "complaints about", "zoll", "anwälten, ärzten und übersetzern",
        ],
        "placeholder_content_markers": ["frage 1 ?", "antwort 1 !"],
    },

    # "www.make-it-in-germany.com": {
    #     "country": "Germany",
    #     "css_selector": "#main",  # TODO: confirm
    #     "preferred_language_path": "/en/",
    #     "content_path_hints": [],  # TODO: fill from test_discovery output, don't reuse diplo.de's
    #     "excluded_url_path_patterns": ["/glossar/", "/glossary/"],
    #     "keywords": ["visa", "residence", "blue-card", "work", "study", "skilled", "pakistan", "card", "employment"],
    #     "excluded_title_keywords": ["glossary", "press-news", "worldwide"],
    #     "placeholder_content_markers": [],
    #     "anti_bot": True, 
    # },

    "pk.usembassy.gov": {
        "country": "USA",
        "css_selector": "#main",  # TODO: confirm
        "preferred_language_path": "",
        "content_path_hints": ["/visas/"],  # TODO: fill from test_discovery output, don't reuse diplo.de's
        "excluded_url_path_patterns": ["/glossar/", "/glossary/","/ur/","/snd/"],
        "keywords": ["visa"],
        "excluded_title_keywords": ["glossary", "press-news", "worldwide"],
        "placeholder_content_markers": [],
        "anti_bot": False, 
    },

    "travel.state.gov": {
        "country": "USA",
        "css_selector": "#main",  # TODO: confirm
        "preferred_language_path": "",
        "content_path_hints": ["/visas/"],  # TODO: fill from test_discovery output, don't reuse diplo.de's
        "excluded_url_path_patterns": ["/glossar/", "/glossary/","/ur/","/snd/"],
        "keywords": ["visa"],
        "excluded_title_keywords": ["glossary", "press-news", "worldwide"],
        "placeholder_content_markers": [],
        "anti_bot": True, 
    },

}

SITEMAP_FETCH_TIMEOUT = 30
SITEMAP_FETCH_RETRIES = 2

# ==============================
# Seed URLs — the actual crawl entry points
# ==============================
# Derived automatically from SOURCE_CONFIG below — you should NOT need
# to maintain this by hand. It's built at import time so main.py can
# still loop "for country, urls in SEED_URLS.items()" without change.

def _build_seed_urls() -> dict:
    seeds: dict[str, list[str]] = {}
    for domain, cfg in SOURCE_CONFIG.items():
        country = cfg["country"]
        seeds.setdefault(country, []).append(f"https://{domain}/")
    return seeds

SEED_URLS = _build_seed_urls()

# ==============================
# Global (non-source-specific) settings
# ==============================

UNIVERSAL_PLACEHOLDER_MARKERS = [
    "(dummy)",
]

MAX_PAGES = 5
MAX_DEPTH = 3

REQUIRED_KEYS = [
    "country",
    "purpose",
    "topic",
    "title",
    "summary",
]

OUTPUT_CSV = "germany_knowledge.csv"

MODEL = "llama-3.3-70b-versatile"