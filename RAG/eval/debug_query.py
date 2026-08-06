# eval/debug_query.py
from RAG.retrieval.router import route_query

for query, category in [
    ("Show me family reunion visas, my spouse has a bachelor's degree", "recommendation"),
    ("Compare Germany and France for work visas", "comparison"),
]:
    print("=" * 70)
    print(query)
    print("=" * 70)
    routed = route_query(query)
    results = routed["results"]

    if category == "recommendation":
        for r in results:
            print(f"  {r['country']:12} {r['source_url']}")
    elif category == "comparison":
        for country, rows in results.items():
            print(f"\n{country}:")
            for r in rows:
                print(f"  {r['source_url']}")