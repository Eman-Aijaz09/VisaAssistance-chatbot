# # retrieval/recommendation_retrieval.py

# """
# Recommendation-path retrieval.

# Unlike factual/general retrieval, this does NOT rely on vector
# similarity — recommendation queries ("which countries can I apply to
# with X qualifications") are a structured filtering problem, not a
# semantic-similarity problem. We query the hard-filter fields directly
# in SQLite, then rank survivors using the soft-scoring fields.

# Falls back to a relaxed query (fewer constraints) if the strict query
# returns nothing, rather than returning an empty result outright.

# If no specific country was requested, results are diversified
# round-robin across countries rather than pure score-order — otherwise
# whichever country has the most/highest-scoring rows fills every slot.
# """

# import sqlite3

# from retrieval.normalization import (
#     normalize_education_level, normalize_language_test,
#     normalize_countries, normalize_purpose,
# )


# DATABASE_NAME = "visa_assistant.db"

# EDUCATION_RANK = {
#     "none": 0,
#     "bachelor": 1,
#     "master": 2,
#     "phd": 3,
# }


# def _connect():
#     conn = sqlite3.connect(DATABASE_NAME)
#     conn.row_factory = sqlite3.Row
#     return conn

# def fetch_by_ids(ids: list[int]) -> list[dict]:
#     """
#     Fetch specific rows by their SQLite id — used when a follow-up
#     question refers to an already-shown recommendation set ("which
#     one is cheapest", "compare these"), rather than running a fresh
#     filter or similarity search.
#     """
#     if not ids:
#         return []

#     conn = _connect()
#     cursor = conn.cursor()
#     placeholders = ",".join("?" for _ in ids)
#     cursor.execute(f"SELECT * FROM visa_knowledge WHERE id IN ({placeholders})", ids)
#     rows = cursor.fetchall()
#     conn.close()

#     return [dict(row) for row in rows]

# def _score_row(row: sqlite3.Row) -> int:
#     """
#     Soft-scoring: prefer rows with a defined PR pathway, shorter
#     processing time, and more complete structured data.

#     Also boosts visas where min_education_level / required_language_test
#     are actually POPULATED (not null) — when a user states real
#     qualifications, they're implicitly asking "where do these
#     qualifications matter", not just "where am I technically not
#     disqualified". A tourist visa with no education requirement is
#     technically eligible but not what they meant, so it should rank
#     behind genuinely qualification-gated visas, not alongside them.
#     """
#     score = 0

#     if row["pr_pathway_available"]:
#         score += 5

#     if row["processing_time_days_max"] is not None:
#         score += max(0, 100 - row["processing_time_days_max"]) // 10

#     if row["min_income_threshold"]:
#         score += 1
#     if row["required_language_test"]:
#         score += 1

#     if row["min_education_level"] is not None:
#         score += 4
#     if row["required_language_test"] is not None:
#         score += 3

#     return score


# def _diversify_by_country(sorted_rows: list, top_k: int) -> list:
#     """
#     Takes rows already sorted by score (best first), and redistributes
#     them round-robin across countries so no single country can fill
#     every slot when no country was explicitly requested.
#     """
#     buckets = {}
#     for row in sorted_rows:
#         buckets.setdefault(row["country"], []).append(row)

#     countries_order = list(buckets.keys())
#     interleaved = []
#     max_len = max(len(v) for v in buckets.values())

#     for i in range(max_len):
#         for country in countries_order:
#             if i < len(buckets[country]):
#                 interleaved.append(dict(buckets[country][i]))

#     return interleaved[:top_k]


# def recommend(
#     countries: list = None,
#     purpose: str = None,
#     visa_type=None,
#     education_level: str = None,
#     language_test: str = None,
#     language_score: str = None,
#     max_budget: float = None,   # MUST be in USD — convert at the caller before passing in
#     top_k: int = 8,
# ) -> list:
#     """
#     Query visa_knowledge directly using structured hard-filter fields.
#     All filter args are optional — pass only what the query classifier
#     actually extracted. Returns a ranked (and, if no country was
#     specified, diversified) list of matching rows as dicts.

#     max_budget is compared against total_estimated_cost_usd. Callers
#     are responsible for converting the user's stated budget (which may
#     be in any currency) to USD BEFORE calling this function — recommend()
#     itself is currency-agnostic and does no conversion.
#     """
#     relaxed = False
#     message = None

#     # NEW — normalize everything once, at the entry point, regardless of caller
#     countries = normalize_countries(countries)
#     purpose = normalize_purpose(purpose)
#     education_level = normalize_education_level(education_level)
#     language_test = normalize_language_test(language_test)

#     conn = _connect()
#     cursor = conn.cursor()

#     conditions = []
#     params = []

#     if countries:
#         placeholders = ",".join("?" for _ in countries)
#         conditions.append(f"country IN ({placeholders})")
#         params.extend(countries)

#     if purpose:
#         conditions.append("purpose = ?")
#         params.append(purpose)

#     if education_level:
#         user_rank = EDUCATION_RANK.get(education_level, 0)
#         acceptable_levels = [
#             level for level, rank in EDUCATION_RANK.items() if rank <= user_rank
#         ]
#         placeholders = ",".join("?" for _ in acceptable_levels)
#         conditions.append(
#             f"(min_education_level IS NULL OR min_education_level IN ({placeholders}))"
#         )
#         params.extend(acceptable_levels)

#     if max_budget is not None:
#         # max_budget MUST already be in USD by the time it reaches here —
#         # conversion happens one layer up, at the API boundary, not here.
#         conditions.append("(total_estimated_cost_usd IS NULL OR total_estimated_cost_usd <= ?)")
#         params.append(max_budget)

#     if language_test:
#         conditions.append("(required_language_test IS NULL OR required_language_test = ?)")
#         params.append(language_test)

#     if visa_type:
#         conditions.append("visa_type = ?")
#         params.append(visa_type)

#     where_clause = " AND ".join(conditions) if conditions else "1=1"

#     print("\nSTRICT QUERY")
#     print("WHERE:", where_clause)
#     print("PARAMS:", params)

#     cursor.execute(f"SELECT * FROM visa_knowledge WHERE {where_clause}", params)
#     rows = cursor.fetchall()

#     print("Strict rows:", len(rows))

#     if not rows and conditions:
#         print("No exact matches — relaxing education/language filters while keeping budget.")
#         relaxed = True

#         relaxed_conditions = []
#         relaxed_params = []

#         # Keep country filter
#         if countries:
#             placeholders = ",".join("?" for _ in countries)
#             relaxed_conditions.append(f"country IN ({placeholders})")
#             relaxed_params.extend(countries)

#         # Keep purpose filter
#         if purpose:
#             relaxed_conditions.append("purpose = ?")
#             relaxed_params.append(purpose)

#         # KEEP budget as a hard constraint
#         if max_budget is not None:
#             relaxed_conditions.append(
#                 "(total_estimated_cost_usd IS NULL OR total_estimated_cost_usd <= ?)"
#             )
#             relaxed_params.append(max_budget)

#         if visa_type:
#             relaxed_conditions.append("visa_type = ?")
#             relaxed_params.append(visa_type)

#         # Education and language are intentionally omitted

#         relaxed_where = (
#             " AND ".join(relaxed_conditions)
#             if relaxed_conditions else "1=1"
#         )

#         print("\nRELAXED QUERY")
#         print("WHERE:", relaxed_where)
#         print("PARAMS:", relaxed_params)

#         cursor.execute(
#             f"SELECT * FROM visa_knowledge WHERE {relaxed_where}",
#             relaxed_params,
#         )

#         rows = cursor.fetchall()

#         print("Relaxed rows:", len(rows))

#         if rows:
#             message = (
#                 "No visas matched all of your requirements. "
#                 "The results below ignore some optional constraints such as "
#                 "education or language requirements."
#             )
#         else:
#             message = (
#                 "No visas match your selected country, purpose, and budget. "
#                 "Try increasing your budget or changing your selected filters."
#             )

        

#     conn.close()

#     scored = [(row, _score_row(row)) for row in rows]
#     scored.sort(key=lambda x: x[1], reverse=True)

#     if not scored:
#         return {
#             "relaxed": relaxed,
#             "message": message or "No visas found matching your criteria.",
#             "results": []
#         }

#     if not countries:
#         results = _diversify_by_country([row for row, score in scored], top_k)
#     else:
#         results = [dict(row) for row, score in scored[:top_k]]

#     return {
#     "results": results,
#     "relaxed": relaxed,
#     "message": message,
#     }


# if __name__ == "__main__":
#     print("\n--- Test: Germany, work purpose, Bachelor's degree ---")
#     results = recommend(countries=["Germany"], purpose="work", education_level="bachelor")
#     for r in results:
#         print(f"  {r['country']} | {r['title']} (visa_type={r['visa_type']})")

#     print("\n--- Test: no country filter, work purpose (diversity should kick in) ---")
#     results = recommend(purpose="work")
#     for r in results:
#         print(f"  {r['country']} | {r['title']}")

#     print("\n--- Test: overly strict filter (should trigger fallback) ---")
#     results = recommend(countries=["Germany"], purpose="tourist", education_level="phd", max_budget=1)
#     for r in results:
#         print(f"  {r['title']}")

"""
recommendation_retrieval.py — Postgres version.

Structured filtering, unchanged in logic from the SQLite version —
only the connection layer and placeholder syntax (%s instead of ?)
changed. Filters directly on total_estimated_cost_usd, same as before.
"""

from RAG.retrieval.shared_resource import get_connection
from RAG.retrieval.normalization import (
    normalize_education_level, normalize_language_test,
    normalize_countries, normalize_purpose,
)

EDUCATION_RANK = {"none": 0, "bachelor": 1, "master": 2, "phd": 3}


def fetch_by_ids(ids: list[int]) -> list[dict]:
    if not ids:
        return []
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ",".join(["%s"] * len(ids))
    cursor.execute(f"SELECT * FROM visa_knowledge WHERE id IN ({placeholders})", ids)
    rows = [dict(r) for r in cursor.fetchall()]
    cursor.close()
    conn.close()
    return rows


def _score_row(row: dict) -> int:
    score = 0
    if row.get("pr_pathway_available"):
        score += 5
    if row.get("processing_time_days_max") is not None:
        score += max(0, 100 - row["processing_time_days_max"]) // 10
    if row.get("min_income_threshold"):
        score += 1
    if row.get("required_language_test"):
        score += 1
    if row.get("min_education_level") is not None:
        score += 4
    if row.get("required_language_test") is not None:
        score += 3
    return score


def _diversify_by_country(sorted_rows: list, top_k: int) -> list:
    buckets = {}
    for row in sorted_rows:
        buckets.setdefault(row["country"], []).append(row)
    countries_order = list(buckets.keys())
    interleaved = []
    max_len = max((len(v) for v in buckets.values()), default=0)
    for i in range(max_len):
        for country in countries_order:
            if i < len(buckets[country]):
                interleaved.append(buckets[country][i])
    return interleaved[:top_k]


def recommend(
    countries: list = None,
    purpose: str = None,
    visa_type=None,
    education_level: str = None,
    language_test: str = None,
    language_score: str = None,
    max_budget: float = None,   # MUST be in USD — convert at the caller before passing in
    top_k: int = 8,
) -> dict:
    relaxed = False
    message = None

    countries = normalize_countries(countries)
    purpose = normalize_purpose(purpose)
    education_level = normalize_education_level(education_level)
    language_test = normalize_language_test(language_test)

    conn = get_connection()
    cursor = conn.cursor()

    conditions = []
    params = []

    if countries:
        placeholders = ",".join(["%s"] * len(countries))
        conditions.append(f"country IN ({placeholders})")
        params.extend(countries)

    if purpose:
        conditions.append("purpose = %s")
        params.append(purpose)

    if education_level:
        user_rank = EDUCATION_RANK.get(education_level, 0)
        acceptable_levels = [lvl for lvl, rank in EDUCATION_RANK.items() if rank <= user_rank]
        placeholders = ",".join(["%s"] * len(acceptable_levels))
        conditions.append(f"(min_education_level IS NULL OR min_education_level IN ({placeholders}))")
        params.extend(acceptable_levels)

    if max_budget is not None:
        conditions.append("(total_estimated_cost_usd IS NULL OR total_estimated_cost_usd <= %s)")
        params.append(max_budget)

    if language_test:
        conditions.append("(required_language_test IS NULL OR required_language_test = %s)")
        params.append(language_test)

    if visa_type:
        conditions.append("visa_type = %s")
        params.append(visa_type)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    print("\nSTRICT QUERY")
    print("WHERE:", where_clause)
    print("PARAMS:", params)

    cursor.execute(f"SELECT * FROM visa_knowledge WHERE {where_clause}", params)
    rows = [dict(r) for r in cursor.fetchall()]
    print("Strict rows:", len(rows))

    if not rows and conditions:
        print("No exact matches — relaxing education/language filters while keeping budget.")
        relaxed = True

        relaxed_conditions = []
        relaxed_params = []

        if countries:
            placeholders = ",".join(["%s"] * len(countries))
            relaxed_conditions.append(f"country IN ({placeholders})")
            relaxed_params.extend(countries)

        if purpose:
            relaxed_conditions.append("purpose = %s")
            relaxed_params.append(purpose)

        if max_budget is not None:
            relaxed_conditions.append("(total_estimated_cost_usd IS NULL OR total_estimated_cost_usd <= %s)")
            relaxed_params.append(max_budget)

        if visa_type:
            relaxed_conditions.append("visa_type = %s")
            relaxed_params.append(visa_type)

        relaxed_where = " AND ".join(relaxed_conditions) if relaxed_conditions else "1=1"

        print("\nRELAXED QUERY")
        print("WHERE:", relaxed_where)
        print("PARAMS:", relaxed_params)

        cursor.execute(f"SELECT * FROM visa_knowledge WHERE {relaxed_where}", relaxed_params)
        rows = [dict(r) for r in cursor.fetchall()]
        print("Relaxed rows:", len(rows))

        if rows:
            message = ("No visas matched all of your requirements. "
                       "The results below ignore some optional constraints such as "
                       "education or language requirements.")
        else:
            message = ("No visas match your selected country, purpose, and budget. "
                       "Try increasing your budget or changing your selected filters.")

    cursor.close()
    conn.close()

    scored = [(row, _score_row(row)) for row in rows]
    scored.sort(key=lambda x: x[1], reverse=True)

    if not scored:
        return {"relaxed": relaxed, "message": message or "No visas found matching your criteria.", "results": []}

    if not countries:
        results = _diversify_by_country([row for row, score in scored], top_k)
    else:
        results = [row for row, score in scored[:top_k]]

    return {"results": results, "relaxed": relaxed, "message": message}