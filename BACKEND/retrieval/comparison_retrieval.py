"""
comparison_retrieval.py — Postgres version. Logic unchanged.
"""


from retrieval.shared_resource import get_connection
from retrieval.normalization import normalize_country, normalize_purpose
from retrieval.recommendation_retrieval import _score_row


def _fetch_for_country(cursor, country: str, purpose: str = None, limit: int = 3) -> list:
    """
    Fetch rows for ONE country, optionally filtered by purpose, ranked
    by relevance (via the same _score_row heuristic recommend() uses —
    PR pathway availability, processing speed, data completeness)
    rather than an arbitrary DB row order. Previously this had no
    ORDER BY at all, so which rows appeared was effectively determined
    by insertion order / last_verified_date — not a meaningful signal
    for "which visas are most worth showing in a comparison."

    Falls back to purpose-less fetch if the filtered query is empty.
    """
    if purpose:
        cursor.execute(
            "SELECT * FROM visa_knowledge WHERE country = %s AND purpose = %s",
            (country, purpose),
        )
        rows = cursor.fetchall()
        if rows:
            # Sort by score DESC, then title ASC as a deterministic
            # tiebreak — without this, rows with equal scores fall
            # back to whatever order Postgres happens to return them
            # in, which isn't guaranteed stable across runs and made
            # this exact query flake in testing.
            ranked = sorted(rows, key=lambda r: (-_score_row(r), r["title"]))
            return ranked[:limit]
        print(f"No '{purpose}' results for {country} — relaxing to all purposes.")

    cursor.execute(
        "SELECT * FROM visa_knowledge WHERE country = %s",
        (country,),
    )
    rows = cursor.fetchall()
    ranked = sorted(rows, key=lambda r: (-_score_row(r), r["title"]))
    return ranked[:limit]

# def _fetch_for_country(cursor, country: str, purpose: str = None, limit: int = 3) -> list:
#     if purpose:
#         cursor.execute(
#             "SELECT * FROM visa_knowledge WHERE country = %s AND purpose = %s LIMIT %s",
#             (country, purpose, limit),
#         )
#         rows = cursor.fetchall()
#         if rows:
#             return rows
#         print(f"No '{purpose}' results for {country} — relaxing to all purposes.")

#     cursor.execute(
#         "SELECT * FROM visa_knowledge WHERE country = %s LIMIT %s",
#         (country, limit),
#     )
#     return cursor.fetchall()


def compare(countries: list, purpose: str = None, per_country_limit: int = 3) -> dict:
    if not countries or len(countries) < 2:
        raise ValueError("compare() needs at least 2 countries to compare against each other.")

    countries = [normalize_country(c) for c in countries]
    purpose = normalize_purpose(purpose)

    conn = get_connection()
    cursor = conn.cursor()

    results = {}
    missing_countries = []

    for country in countries:
        rows = _fetch_for_country(cursor, country, purpose, limit=per_country_limit)
        row_dicts = [dict(r) for r in rows]
        results[country] = row_dicts
        if not row_dicts:
            missing_countries.append(country)

    cursor.close()
    conn.close()

    return {"results": results, "missing_countries": missing_countries}