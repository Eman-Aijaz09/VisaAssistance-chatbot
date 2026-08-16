"""
factual_retrieval.py

Vector similarity search via pgvector, replacing the old Chroma
collection.query() call. Country/purpose filters are now a normal
SQL WHERE clause combined with the vector ORDER BY in one query,
instead of Chroma's separate `where` dict mechanism.
"""

from retrieval.shared_resource import get_model, get_connection

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
TOP_K = 5


def retrieve_factual(query: str, top_k: int = TOP_K, countries: list = None, purpose: str = None) -> list:
    """
    Returns a list of dicts: [{"content": ..., "metadata": ..., "score": ...}, ...]
    Same standardized shape as before, so citation_utils/generator.py
    consume this identically regardless of the underlying store.
    """
    model = get_model()
    query_embedding = model.encode(
        QUERY_PREFIX + query,
        normalize_embeddings=True,
    ).tolist()

    conditions = []
    params = []

    if countries:
        placeholders = ",".join(["%s"] * len(countries))
        conditions.append(f"country IN ({placeholders})")
        params.extend(countries)

    if purpose:
        conditions.append("purpose = %s")
        params.append(purpose)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # pgvector's <=> operator computes cosine distance; we convert to
    # a similarity score (1 - distance) to match the old Chroma shape.
    sql = f"""
        SELECT title, country, visa_type, purpose, source_url,
               last_verified_date, content,
               1 - (embedding <=> %s::vector) AS score
        FROM visa_knowledge
        {where_clause}
        AND embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """ if conditions else f"""
        SELECT title, country, visa_type, purpose, source_url,
               last_verified_date, content,
               1 - (embedding <=> %s::vector) AS score
        FROM visa_knowledge
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, [query_embedding, *params, query_embedding, top_k])
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return [
        {
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
        for row in rows
    ]