# # retrieval/comparison_retrieval.py

# """
# Comparison-path retrieval.

# Given two or more countries (and optionally a shared purpose), fetch
# matching rows deterministically, one query per country — guaranteed
# to return results for EACH side being compared, unlike vector search
# which might over-favor one side depending on how the query embeds.

# Falls back to relaxing the purpose filter per-country if a strict
# match returns nothing for one side. If a country has NO data at all
# (not in our dataset), this is surfaced explicitly via "missing_countries"
# rather than silently returning an empty list for that side.
# """

# import sqlite3

# DATABASE_NAME = "visa_assistant.db"


# def _connect():
#     conn = sqlite3.connect(DATABASE_NAME)
#     conn.row_factory = sqlite3.Row
#     return conn


# def _fetch_for_country(cursor, country: str, purpose: str = None, limit: int = 3) -> list:
#     """
#     Fetch rows for ONE country, optionally filtered by purpose.
#     Falls back to purpose-less fetch if the filtered query is empty.
#     """
#     if purpose:
#         cursor.execute(
#             "SELECT * FROM visa_knowledge WHERE country = ? AND purpose = ? LIMIT ?",
#             (country, purpose, limit),
#         )
#         rows = cursor.fetchall()
#         if rows:
#             return rows
#         print(f"No '{purpose}' results for {country} — relaxing to all purposes.")

#     cursor.execute(
#         "SELECT * FROM visa_knowledge WHERE country = ? LIMIT ?",
#         (country, limit),
#     )
#     return cursor.fetchall()


# def compare(countries: list, purpose: str = None, per_country_limit: int = 3) -> dict:
#     """
#     Returns:
#         {
#             "results": {country: [rows...], ...},
#             "missing_countries": [country, ...],   # countries with ZERO data at all
#         }

#     "missing_countries" is populated when even the relaxed (purpose-less)
#     query returns nothing for a country — meaning we have no data on it
#     whatsoever, not just no match for this specific purpose. Callers
#     (router.py, generation.py) MUST check this before treating the
#     comparison as complete, rather than assuming every requested
#     country got a real answer.
#     """
#     if not countries or len(countries) < 2:
#         raise ValueError("compare() needs at least 2 countries to compare against each other.")

#     conn = _connect()
#     cursor = conn.cursor()

#     results = {}
#     missing_countries = []

#     for country in countries:
#         rows = _fetch_for_country(cursor, country, purpose, limit=per_country_limit)
#         row_dicts = [dict(row) for row in rows]
#         results[country] = row_dicts

#         if not row_dicts:
#             missing_countries.append(country)

#     conn.close()

#     return {
#         "results": results,
#         "missing_countries": missing_countries,
#     }


# if __name__ == "__main__":

#     print("\n--- Test: Germany vs USA, purpose=work ---")
#     output = compare(countries=["Germany", "USA"], purpose="work")
#     for country, rows in output["results"].items():
#         print(f"\n{country}:")
#         for r in rows:
#             print(f"  {r['title']} (visa_type={r['visa_type']})")
#     print(f"\nMissing countries: {output['missing_countries']}")

#     print("\n\n--- Test: Germany vs Canada, purpose=study (Canada has NO data) ---")
#     output = compare(countries=["Germany", "Canada"], purpose="study")
#     for country, rows in output["results"].items():
#         print(f"\n{country}:")
#         for r in rows:
#             print(f"  {r['title']}")
#     print(f"\nMissing countries: {output['missing_countries']}")

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