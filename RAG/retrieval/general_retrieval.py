"""
general_retrieval.py

Vector search for broad conceptual questions, via pgvector. Includes
the diversity-aware round-robin variant, now using a SQL query per
country instead of a Chroma where-filtered query per country.
"""

from RAG.retrieval.shared_resource import get_model, get_connection

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
TOP_K = 7


def _row_to_result(row):
    return {
        "content": row["content"],
        "metadata": {
            "title": row["title"],
            "country": row["country"],
            "visa_type": row["visa_type"],
            "purpose": row["purpose"],
            "source_url": row["source_url"],
            "last_verified_date": row["last_verified_date"],
        },
        "score": row["score"],
    }


def _get_known_countries(cursor) -> list:
    cursor.execute("SELECT DISTINCT country FROM visa_knowledge WHERE country IS NOT NULL")
    return sorted(r["country"] for r in cursor.fetchall())


def retrieve_general_diverse(query: str, top_k: int = 7, per_country_k: int = 1) -> list:
    """
    Fetches top per_country_k results FROM EACH country separately,
    then interleaves them — guarantees cross-country representation
    instead of one country's dense semantic neighborhood dominating.
    """
    model = get_model()
    query_embedding = model.encode(QUERY_PREFIX + query, normalize_embeddings=True).tolist()

    conn = get_connection()
    cursor = conn.cursor()

    countries = _get_known_countries(cursor)

    if len(countries) <= 1:
        cursor.close()
        conn.close()
        return retrieve_general(query, top_k=top_k)

    per_country_results = {}
    for country in countries:
        cursor.execute("""
            SELECT title, country, visa_type, purpose, source_url,
                   last_verified_date, content,
                   1 - (embedding <=> %s::vector) AS score
            FROM visa_knowledge
            WHERE country = %s AND embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, [query_embedding, country, query_embedding, per_country_k])
        per_country_results[country] = [_row_to_result(r) for r in cursor.fetchall()]

    cursor.close()
    conn.close()

    interleaved = []
    max_len = max((len(v) for v in per_country_results.values()), default=0)
    for i in range(max_len):
        for country in countries:
            bucket = per_country_results[country]
            if i < len(bucket):
                interleaved.append(bucket[i])

    return interleaved[:top_k]


def retrieve_general(query: str, top_k: int = TOP_K, countries: list = None, visa_type=None) -> list:
    """
    Plain vector search, optionally pre-filtered by country if the
    classifier extracted one (rare for general queries, but possible).
    """
    model = get_model()
    query_embedding = model.encode(QUERY_PREFIX + query, normalize_embeddings=True).tolist()

    conditions = []
    params = []

    if countries:
        placeholders = ",".join(["%s"] * len(countries))
        conditions.append(f"country IN ({placeholders})")
        params.extend(countries)

    where_clause = "WHERE " + " AND ".join(conditions) + " AND embedding IS NOT NULL" \
        if conditions else "WHERE embedding IS NOT NULL"

    sql = f"""
        SELECT title, country, visa_type, purpose, source_url,
               last_verified_date, content,
               1 - (embedding <=> %s::vector) AS score
        FROM visa_knowledge
        {where_clause}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, [query_embedding, *params, query_embedding, top_k])
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return [_row_to_result(r) for r in rows]