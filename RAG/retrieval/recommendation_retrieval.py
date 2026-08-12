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