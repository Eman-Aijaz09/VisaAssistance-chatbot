"""
eval/golden_queries.py

Golden retrieval-evaluation set for the visa assistant.

Every query below is written against ACTUAL rows in the current
dataset (dummy_data.csv / visa_knowledge), so expected_sources are
real source_url values you can go verify by eye rather than invented
facts. source_url is used as the stable identifier instead of the
DB `id`, since ids aren't guaranteed stable across reloads.

Structure per query:
  id                : unique string, used in reports
  query             : the natural-language question a user would type
  expected_category : what query_classifier.py SHOULD return
  expected_sources  : list[str] of source_url values that MUST appear
                       in the results for this query to "pass".
                       - factual/general: recall + rank checked
                       - recommendation/comparison: presence-only checked
  expected_missing_countries : (comparison only) countries with no
                       data at all, that compare() should flag
  notes             : why this query is in the set / what it stresses

HOW TO EXTEND:
  Add new dicts to GOLDEN_QUERIES. Keep the id prefix matching the
  category (factual_, general_, recommendation_, comparison_) so
  run_eval.py's per-category breakdown stays meaningful.
"""

GOLDEN_QUERIES = [

    # ============================================================
    # FACTUAL — narrow, single-fact questions.
    # A few of these are deliberately "exact term" queries (visa
    # codes, subclass numbers) that plain vector search often
    # under-ranks. Use these specifically to judge hybrid search (#5)
    # later — note the rank they get NOW, before that change.
    # ============================================================
    {
        "id": "factual_01",
        "query": "What is the total estimated cost of a USA H-1B visa?",
        "expected_category": "factual",
        "expected_sources": [
            "https://www.uscis.gov/working-in-the-united-states/h-1b-specialty-occupations"
        ],
        "notes": "Exact alphanumeric visa code (H-1B) — vector-only baseline check for hybrid search later.",
    },
    {
        "id": "factual_02",
        "query": "What is the minimum salary threshold for the Germany EU Blue Card?",
        "expected_category": "factual",
        "expected_sources": [
            "https://www.make-it-in-germany.com/en/visa-residence/types/eu-blue-card"
        ],
        "notes": "Numeric threshold buried in JSON field (min_income_threshold) — tests whether build_content surfaces it.",
    },
    {
        "id": "factual_03",
        "query": "How many points are required for Australia's Subclass 189 Skilled Independent Visa?",
        "expected_category": "factual",
        "expected_sources": [
            "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/skilled-independent-189"
        ],
        "notes": "Exact subclass number — another hybrid-search stress test.",
    },
    {
        "id": "factual_04",
        "query": "What IELTS score is required for the Qatar Student Residence Permit?",
        "expected_category": "factual",
        "expected_sources": [
            "https://portal.moi.gov.qa/qatarportal/visa/student-visa"
        ],
        "notes": "Language-test detail specific to one country/visa.",
    },
    {
        "id": "factual_05",
        "query": "What is the processing time for the France Airport Transit Visa?",
        "expected_category": "factual",
        "expected_sources": [
            "https://france-visas.gouv.fr/en/web/france-visas/airport-transit-visa"
        ],
        "notes": "Processing-time lookup; France has two tourist-adjacent visas (Schengen + Airport Transit) so also checks disambiguation.",
    },
    {
        "id": "factual_06",
        "query": "How many points does the Germany Opportunity Card require?",
        "expected_category": "factual",
        "expected_sources": [
            "https://www.make-it-in-germany.com/en/visa-residence/types/opportunity-card"
        ],
        "notes": "points_required field, distinct from EU Blue Card in same country/purpose — confusability check.",
    },
    {
        "id": "factual_07",
        "query": "What JLPT level is needed for Japan's Specified Skilled Worker visa?",
        "expected_category": "factual",
        "expected_sources": [
            "https://www.isa.go.jp/en/ssw/index.html"
        ],
        "notes": "Japan has two JLPT-gated work-adjacent visas (Specified Skilled Worker N4 vs Technical Intern N5) — disambiguation check.",
    },
    {
        "id": "factual_08",
        "query": "What is the application fee for a USA B1/B2 visitor visa?",
        "expected_category": "factual",
        "expected_sources": [
            "https://pk.usembassy.gov/visas/nonimmigrant-visas/"
        ],
        "notes": "Straightforward fee lookup, common real-world query shape.",
    },
    {
        "id": "factual_09",
        "query": "Does the Germany Job Seeker Visa lead to permanent residency?",
        "expected_category": "factual",
        "expected_sources": [
            "https://www.make-it-in-germany.com/en/visa-residence/types/job-seeker-visa"
        ],
        "notes": "pr_pathway_available=FALSE for this one, unlike most other Germany work visas — good negative-fact check.",
    },

    # ============================================================
    # GENERAL — broad conceptual questions, single or multi-source
    # synthesis, no hard country/visa filter expected.
    # ============================================================
    {
        "id": "general_01",
        "query": "What is the EU Blue Card?",
        "expected_category": "general",
        "expected_sources": [
            "https://www.make-it-in-germany.com/en/visa-residence/types/eu-blue-card"
        ],
        "notes": "Classic 'what is X' general query — single dominant source.",
    },
    {
        "id": "general_02",
        "query": "How does Australia's points-based skilled migration system work?",
        "expected_category": "general",
        "expected_sources": [
            "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/skilled-independent-189",
            "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/skilled-nominated-190",
        ],
        "notes": "Should synthesize across the two points-based visas (189 & 190), not just one.",
    },
    {
        "id": "general_03",
        "query": "What are Talent Passport visas in France?",
        "expected_category": "general",
        "expected_sources": [
            "https://france-visas.gouv.fr/en/web/france-visas/talent-passport",
            "https://www.euraxess.fr/france/information-assistance/entry-and-residence-conditions",
        ],
        "notes": "France has 4 Talent Passport sub-categories in the dataset — tests multi-source synthesis without missing the family.",
    },
    {
        "id": "general_04",
        "query": "What is the USA Diversity Visa lottery program?",
        "expected_category": "general",
        "expected_sources": [
            "https://travel.state.gov/content/travel/en/us-visas/immigrate/diversity-visa-program-entry.html"
        ],
        "notes": "Single well-known program, good sanity check for general-path retrieval.",
    },
    {
        "id": "general_05",
        "query": "How does family sponsorship work in Qatar?",
        "expected_category": "general",
        "expected_sources": [
            "https://portal.moi.gov.qa/qatarportal/visa/family-visa"
        ],
        "notes": "Broad conceptual phrasing of a specific visa — tests general vs factual boundary.",
    },
    {
        "id": "general_06",
        "query": "What immigration options exist for researchers in Germany and France?",
        "expected_category": "general",
        "expected_sources": [
            "https://www.make-it-in-germany.com/en/visa-residence/types/researchers",
            "https://www.euraxess.fr/france/information-assistance/entry-and-residence-conditions",
        ],
        "notes": "Cross-country synthesis without an explicit 'compare' — tests general vs comparison boundary.",
    },

    # ============================================================
    # RECOMMENDATION — structured filtering. `profile` mirrors what
    # the classifier is expected to extract (or what /recommend
    # would receive directly). expected_sources are presence-only
    # checks (order doesn't matter — this path isn't rank-based).
    # ============================================================
    {
        "id": "recommendation_01",
        "query": "I have a Bachelor's degree and want to work in Germany, what are my options?",
        "expected_category": "recommendation",
        "profile": {"countries": ["Germany"], "purpose": "work", "education_level": "bachelor"},
        "expected_sources": [
            "https://www.make-it-in-germany.com/en/visa-residence/types/eu-blue-card",
            "https://www.make-it-in-germany.com/en/visa-residence/types/skilled-workers",
            "https://www.make-it-in-germany.com/en/visa-residence/types/job-seeker-visa",
            "https://www.make-it-in-germany.com/en/visa-residence/types/opportunity-card",
        ],
        "notes": "4 Germany work visas accept bachelor's — checks hard filter isn't over- or under-inclusive.",
    },
    {
        "id": "recommendation_02",
        "query": "I have a Master's degree, IELTS 6, and want to move to Australia permanently. My budget is 5000 AUD.",
        "expected_category": "recommendation",
        "profile": {
            "countries": ["Australia"], "purpose": "permanent_residency",
            "education_level": "master", "language_test": "IELTS", "language_score": "6",
            "budget": 5000, "budget_currency": "AUD",
        },
        "expected_sources": [
            "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/skilled-independent-189",
            "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/skilled-nominated-190",
        ],
        "notes": "Budget (4770 AUD cost) sits just under the stated 5000 cap — tests budget filter boundary, not just presence/absence.",
    },
    {
        "id": "recommendation_03",
        "query": "My budget is only 50000, what are my options for studying?",
        "expected_category": "recommendation",
        "profile": {"purpose": "study", "budget": 50000, "budget_currency": None},
        "expected_sources": [],
        "notes": (
            "No currency stated — router should set needs_currency_clarification=True and "
            "return the clarifying question, NOT silently guess a currency. Pass condition is "
            "the flag being set, not a source match."
        ),
    },
    {
        "id": "recommendation_04",
        "query": "I only have a high school education, what work visas can I get in Japan?",
        "expected_category": "recommendation",
        "profile": {"countries": ["Japan"], "purpose": "work", "education_level": "none"},
        "expected_sources": [
            "https://www.isa.go.jp/en/ssw/index.html",
            "https://www.otit.go.jp/en/",
        ],
        "notes": "Only 2 of Japan's 6 work visas have min_education_level=none — checks filter isn't too permissive.",
    },
    {
        "id": "recommendation_05",
        "query": "I have a PhD and want to do research work, which countries should I consider?",
        "expected_category": "recommendation",
        "profile": {"purpose": "work", "education_level": "phd"},
        "expected_sources": [
            "https://www.make-it-in-germany.com/en/visa-residence/types/researchers",
        ],
        "notes": "No country specified — diversification logic should surface this even though only one visa in the dataset requires a PhD.",
    },
    {
    "id": "recommendation_06",
    "query": "Show me family reunion visas, my spouse has a bachelor's degree",
    "expected_category": "recommendation",
    "profile": {"purpose": "family_reunion"},
    "expected_sources": [
        "https://www.auswaertiges-amt.de/en/visa-service/familynachzug",
        "https://www.isa.go.jp/en/applications/status/spouse.html",
        "https://travel.state.gov/content/travel/en/us-visas/immigrate/family-immigration.html",
        "https://france-visas.gouv.fr/en/web/france-visas/family-reunification",
        "https://portal.moi.gov.qa/qatarportal/visa/family-visa",
        "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/contributory-parent-143",
        "https://www.isa.go.jp/en/applications/status/long_term_resident.html",
        "https://travel.state.gov/content/travel/en/us-visas/immigrate/family-immigration/fiance-visa.html",
    ],
    "notes": (
        "Education is about the SPOUSE, not the applicant — checks the classifier doesn't "
        "wrongly attach education_level to the filter. NOTE: top_k=8 default caps this "
        "9-country match set; Australia's partner-820 visa is the one round-robin diversify "
        "drops (Australia already has contributory-parent-143 in the list, so it loses the "
        "tiebreak on its 2nd entry). This is deterministic given current scoring, but fragile "
        "to any future _score_row() or diversify change — worth an explicit product decision "
        "later on whether dropping same-country duplicates like this is desired behavior."
    ),
},

    # ============================================================
    # COMPARISON — side-by-side, deterministic per-country fetch.
    # ============================================================
    {
    "id": "comparison_01",
    "query": "Compare Germany and France for work visas",
    "expected_category": "comparison",
    "countries": ["Germany", "France"],
    "expected_sources": {
        "Germany": [
            "https://www.make-it-in-germany.com/en/visa-residence/types/vocational-training",
            "https://www.auswaertiges-amt.de/en/visa-service/au-pair",
            "https://www.make-it-in-germany.com/en/visa-residence/types/opportunity-card",
        ],
        "France": [
            "https://www.euraxess.fr/france/information-assistance/entry-and-residence-conditions",
            "https://france-visas.gouv.fr/en/web/france-visas/talent-passport",
            "https://france-visas.gouv.fr/en/web/france-visas/au-pair",
        ],
    },
    "expected_missing_countries": [],
    "notes": (
        "Basic 2-country comparison. Top-3 per country determined by _score_row() "
        "(PR pathway, processing speed, data completeness), with title ASC as a "
        "deterministic tiebreak for equal scores. Germany's slots 2-3 (Au-Pair, "
        "Opportunity Card, Research Visa) are a 3-way tie at score 14 — 'Research' "
        "loses the alphabetical tiebreak against 'Au-Pair' and 'Opportunity' and is "
        "correctly excluded from the top-3. France's 3rd slot was a tie between "
        "Au-Pair Visa and Trainee Visa (both score 10) — Au-Pair wins alphabetically. "
        "Verified stable across 4 consecutive runs with the title-ASC tiebreak in place."
    ),
},
    {
        "id": "comparison_02",
        "query": "Compare Australia, Japan, and Qatar for permanent residency",
        "expected_category": "comparison",
        "countries": ["Australia", "Japan", "Qatar"],
        "expected_sources": {
            "Australia": [
                "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/skilled-independent-189",
                "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/skilled-nominated-190",
            ],
            "Japan": [
                "https://www.isa.go.jp/en/applications/status/newimmiact_3_index.html",
            ],
            "Qatar": [
                "https://portal.moi.gov.qa/qatarportal/visa/permanent-residency",
            ],
        },
        "expected_missing_countries": [],
        "notes": "3-way comparison, all 3 countries have >=1 permanent_residency row.",
    },
    {
        "id": "comparison_03",
        "query": "Compare Germany and Canada for studying",
        "expected_category": "comparison",
        "countries": ["Germany", "Canada"],
        "expected_sources": {
            "Germany": [
                "https://www.study-in-germany.de/en/plan-your-studies/requirements/visa",
            ],
        },
        "expected_missing_countries": ["Canada"],
        "notes": (
            "Canada has ZERO rows in this dataset — must be explicitly flagged in "
            "missing_countries, not silently dropped or answered as if data existed."
        ),
    },
    {
        "id": "comparison_04",
        "query": "Compare USA and Australia student visas",
        "expected_category": "comparison",
        "countries": ["USA", "Australia"],
        "expected_sources": {
            "USA": [
                "https://travel.state.gov/content/travel/en/us-visas/study/student-visa.html",
            ],
            "Australia": [
                "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/student-500",
            ],
        },
        "expected_missing_countries": [],
        "notes": "Straightforward 2-country, single-visa-per-side comparison — the simplest case, good smoke test.",
    },
]


def get_by_category(category: str) -> list:
    return [q for q in GOLDEN_QUERIES if q["expected_category"] == category]


def get_by_id(query_id: str) -> dict | None:
    return next((q for q in GOLDEN_QUERIES if q["id"] == query_id), None)


if __name__ == "__main__":
    from collections import Counter
    counts = Counter(q["expected_category"] for q in GOLDEN_QUERIES)
    print(f"Total golden queries: {len(GOLDEN_QUERIES)}")
    for cat, n in counts.items():
        print(f"  {cat:15} {n}")