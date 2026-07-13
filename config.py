# config.py

# ==============================
# Seed URL(s)
# ==============================

SEED_URLS = [
    "https://pakistan.diplo.de/pk-en/service/1673894-1673894",
#     "https://www.make-it-in-germany.com/"
]


# ==============================
# Crawl Settings
# ==============================

# Leave None if you want Crawl4AI to extract the whole page.
# Use a selector only if the website has a consistent content container.
CSS_SELECTOR = None

MAX_PAGES = 20
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