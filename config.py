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
        "css_selector": ".main-content-wrapper",  # TODO: confirm
        "preferred_language_path": "",
        "content_path_hints": ["/visas/"],  # TODO: 
        "excluded_url_path_patterns": ["/glossar/", "/glossary/","/ur/","/snd/"],
        "keywords": ["visa"],
        "excluded_title_keywords": ["glossary", "press-news", "worldwide"],
        "placeholder_content_markers": [],
        "anti_bot": False, 
    },

    # "travel.state.gov": {
    #     "country": "USA",
    #     "css_selector": ".tsg-rwd-body-frame-row",  # TODO: confirm
    #     "preferred_language_path": "",
    #     "content_path_hints": ["/visas/"],  # TODO: 
    #     "excluded_url_path_patterns": ["/glossar/", "/glossary/","/ur/","/snd/"],
    #     "keywords": ["visa"],
    #     "excluded_title_keywords": ["glossary", "press-news", "worldwide"],
    #     "placeholder_content_markers": [],
    #     "anti_bot": True, 
    # },

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

MAX_PAGES = 60
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