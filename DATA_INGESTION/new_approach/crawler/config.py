"""
===============================================================================
config.py

Purpose
-------
This file contains ONLY website-specific configuration.

It should answer:

    "Which websites should the crawler visit?"

It should NOT contain:

    - Filtering rules
    - Crawl logic
    - Browser logic
    - Queue logic
    - HTML extraction logic

Those belong in their own modules.

===============================================================================
"""

# =============================================================================
# Websites to Crawl
# =============================================================================
#
# Each country can have multiple official websites.
#
# Example:
#
# Germany
#     ├── pakistan.diplo.de
#     └── make-it-in-germany.com
#
# USA
#     ├── travel.state.gov
#     └── pk.usembassy.gov
#
# crawler.py will automatically loop through every country and every website.
#

CRAWL_SOURCES = {

    "Germany": [

        {

            "website": "German Embassy Pakistan",
            "base_url": "https://pakistan.diplo.de/pk-en",
            "allowed_domains": [
                "pakistan.diplo.de",
            ],
            "preferred_language_path": "/pk-en/",
        },

        {
            "website": "Make it in Germany",
            "base_url": "https://www.make-it-in-germany.com/en/",
            "allowed_domains": [
                "www.make-it-in-germany.com",
            ],
            "preferred_language_path": "/pk-en/",
        },

    ],

    "USA": [

        {
            "website": "Travel State US",
            "base_url": "https://travel.state.gov/en.html",
            "allowed_domains": [
                            "travel.state.gov",
                        ],
            "preferred_language_path": "/en",
        },

        {
            "website": "US Embassy Pakistan",
            "base_url": "https://pk.usembassy.gov/",
            "allowed_domains": [
                                        "pk.usembassy.gov",
                                    ],
            "preferred_language_path": "/",
        },

    ],

    # "France": [
    # ],
    #
    # "Qatar": [
    # ],

}
# =============================================================================
# Generic Crawl Settings
# =============================================================================
MAX_DEPTH = 4

MAX_PAGES_PER_SOURCE = 200

REQUEST_DELAY = 2

SAVE_HTML = True

OUTPUT_FOLDER = "debug_html"
QUEUE_STATE_FOLDER = "queue_state"
NON_ENGLISH_URL_SEGMENTS = [
    "/pk-de/",
    "/de/",
    "/fr/",
    "/es/",
    "/it/",
    "/ru/",
    "/ar/",
    "/zh/",
]