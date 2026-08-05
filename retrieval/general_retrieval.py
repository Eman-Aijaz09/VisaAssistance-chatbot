# # retrieval/general_retrieval.py

# """
# General-path retrieval.

# For broad, conceptual questions not tied to one specific visa's
# procedural details (e.g. "what is the Opportunity Card", "how does
# Germany's immigration system work"). Pure vector similarity search
# is the right tool here — no structured filtering, no multi-fetch —
# since these queries are asking to understand a topic, not to get a
# specific fact or compare options.

# Reuses the same Chroma collection and embedding model as factual
# retrieval, but with a slightly higher top_k, since a general/broad
# question's answer may need to synthesize across a couple of related
# documents rather than pull from one exact match.
# """

# import chromadb
# from sentence_transformers import SentenceTransformer
# from retrieval.shared_resource import get_model, get_collection

# CHROMA_PATH = "embeddings/chroma_db"
# COLLECTION_NAME = "visa_knowledge"
# EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
# QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# TOP_K = 7   # higher than factual's default 5 — broader questions benefit from more context

# def retrieve_general_diverse(query: str, top_k: int = 7, per_country_k: int = 2) -> list:
#     """
#     Diversity-aware retrieval for broad queries with no country specified.
#     Instead of one global top-k similarity search (which clusters toward
#     whichever country has the densest semantic neighborhood), fetches
#     top per_country_k results FROM EACH country separately, then
#     interleaves them — guaranteeing cross-country representation.

#     Falls back to plain retrieve_general() if only one country exists
#     in the data, or if country list can't be determined.
#     """
#     model = get_model()
#     collection = get_collection()

#     query_embedding = model.encode(
#         QUERY_PREFIX + query,
#         normalize_embeddings=True,
#     ).tolist()

#     # Discover which countries actually exist in the collection
#     all_metadata = collection.get(include=["metadatas"])["metadatas"]
#     countries = sorted(set(m["country"] for m in all_metadata if m.get("country")))

#     if len(countries) <= 1:
#         return retrieve_general(query, top_k=top_k)

#     # Fetch top per_country_k results PER COUNTRY
#     per_country_results = {}
#     for country in countries:
#         results = collection.query(
#             query_embeddings=[query_embedding],
#             n_results=per_country_k,
#             where={"country": country},
#         )
#         documents = results["documents"][0]
#         metadatas = results["metadatas"][0]
#         distances = results["distances"][0]

#         per_country_results[country] = [
#             {"content": doc, "metadata": meta, "score": 1 - dist}
#             for doc, meta, dist in zip(documents, metadatas, distances)
#         ]

#     # Interleave round-robin: one from each country in turn, by rank
#     interleaved = []
#     max_len = max(len(v) for v in per_country_results.values())
#     for i in range(max_len):
#         for country in countries:
#             bucket = per_country_results[country]
#             if i < len(bucket):
#                 interleaved.append(bucket[i])

#     return interleaved[:top_k]

# def retrieve_general(query: str, top_k: int = TOP_K, countries: list = None,visa_type=None,) -> list:
#     """
#     Returns a list of dicts: [{"content": ..., "metadata": ..., "score": ...}, ...]
#     No hard filtering by default — general questions are usually not
#     country-specific. If countries ARE extracted by the classifier
#     (rare for general queries, but possible), apply as an optional
#     pre-filter rather than ignoring it.
#     """
#     model = get_model()
#     collection = get_collection()

#     query_embedding = model.encode(
#         QUERY_PREFIX + query,
#         normalize_embeddings=True,
#     ).tolist()

#     query_kwargs = {
#         "query_embeddings": [query_embedding],
#         "n_results": top_k,
#     }

#     # if countries:
#     #     if len(countries) == 1:
#     #         query_kwargs["where"] = {"country": countries[0]}
#     #     else:
#     #         query_kwargs["where"] = {"country": {"$in": countries}}

#     where_conditions = []

#     if countries:
#         if len(countries)==1:
#             where_conditions.append({"country":countries[0]})
#         else:
#             where_conditions.append({"country":{"$in":countries}})

#     # if visa_type:
#     #     where_conditions.append({"visa_type":visa_type})

#     if len(where_conditions)==1:
#         query_kwargs["where"]=where_conditions[0]

#     elif len(where_conditions)>1:
#         query_kwargs["where"]={"$and":where_conditions}

#     results = collection.query(**query_kwargs)

#     documents = results["documents"][0]
#     metadatas = results["metadatas"][0]
#     distances = results["distances"][0]

#     return [
#         {
#             "content": doc,
#             "metadata": meta,
#             "score": 1 - dist,
#         }
#         for doc, meta, dist in zip(documents, metadatas, distances)
#     ]


# if __name__ == "__main__":
#     test_queries = [
#         "what is the Opportunity Card",
#         "how does Germany's immigration system work for skilled workers",
#         "what is a diversity visa lottery",
#     ]

#     for q in test_queries:
#         print(f"\n{'='*80}")
#         print(f"Query: {q}")
#         print(f"{'='*80}")
#         results = retrieve_general(q)
#         for i, r in enumerate(results, start=1):
#             print(f"{i}. [{r['score']:.4f}] {r['metadata']['title']} ({r['metadata']['country']})")

"""
general_retrieval.py

Vector search for broad conceptual questions, via pgvector. Includes
the diversity-aware round-robin variant, now using a SQL query per
country instead of a Chroma where-filtered query per country.
"""

from retrieval.shared_resource import get_model, get_connection

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


def retrieve_general_diverse(query: str, top_k: int = 7, per_country_k: int = 2) -> list:
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