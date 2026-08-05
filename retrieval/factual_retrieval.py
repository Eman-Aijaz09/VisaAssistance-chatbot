# # retrieval/factual_retrieval.py

# import chromadb
# from sentence_transformers import SentenceTransformer
# from retrieval.shared_resource import get_model, get_collection

# CHROMA_PATH = "embeddings/chroma_db"
# COLLECTION_NAME = "visa_knowledge"
# EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
# QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
# TOP_K = 5

# def retrieve_factual(query: str, top_k: int = TOP_K, countries: list = None, purpose: str = None) -> list:
#     """
#     Returns a list of dicts: [{"content": ..., "metadata": ..., "score": ...}, ...]
#     Same standardized shape as general_retrieval, so generation.py can
#     consume either path identically.
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

#     # Build where clause from whatever the classifier extracted
#     where_conditions = []
#     if countries:
#         if len(countries) == 1:
#             where_conditions.append({"country": countries[0]})
#         else:
#             where_conditions.append({"country": {"$in": countries}})
#     if purpose:
#         where_conditions.append({"purpose": purpose})
   

#     if len(where_conditions) == 1:
#         query_kwargs["where"] = where_conditions[0]
#     elif len(where_conditions) > 1:
#         query_kwargs["where"] = {"$and": where_conditions}

#     results = collection.query(**query_kwargs)

#     documents = results["documents"][0]
#     metadatas = results["metadatas"][0]
#     distances = results["distances"][0]

#     return [
#         {"content": doc, "metadata": meta, "score": 1 - dist}
#         for doc, meta, dist in zip(documents, metadatas, distances)
#     ]

# if __name__ == "__main__":

#     test_queries = [
#         "what documents do I need for a German student visa",
#         "how much does the H-1B visa cost",
#         "what is the processing time for the EU Blue Card",
#         "what are the eligibility requirements for the F-1 visa",
#     ]

#     for query in test_queries:

#         print(f"\n{'='*80}")
#         print(f"Question: {query}")
#         print(f"{'='*80}")

#         results = retrieve_factual(query)

#         for i, r in enumerate(results, start=1):

#             meta = r["metadata"]

#             print("-" * 80)
#             print(f"Rank       : {i}")
#             print(f"Score      : {r['score']:.4f}")
#             print(f"Title      : {meta['title']}")
#             print(f"Visa Type  : {meta['visa_type']}")
#             print(f"Country    : {meta['country']}")
#             print(f"Source URL : {meta['source_url']}")
#             print("-" * 80)
#             print(r["content"][:500])
#             print()


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