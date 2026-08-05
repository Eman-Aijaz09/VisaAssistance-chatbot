# import sqlite3, chromadb

# conn = sqlite3.connect("visa_assistant.db")
# sqlite_count = conn.execute("SELECT COUNT(*) FROM visa_knowledge").fetchone()[0]

# client = chromadb.PersistentClient(path="embeddings/chroma_db")
# collection = client.get_collection("visa_knowledge")
# chroma_count = collection.count()

# print(f"SQLite: {sqlite_count} | Chroma: {chroma_count}")
# assert sqlite_count == chroma_count, "Mismatch — investigate before proceeding"


# from retrieval.query_classifier import classify_query_llm

# result = classify_query_llm("which is faster to get, USA H-1B or Australia skilled visa?")
# print(result)

# from retrieval.comparison_retrieval import compare

# output = compare(countries=["USA", "Australia"], purpose="work")
# print("Missing countries:", output["missing_countries"])
# for country, rows in output["results"].items():
#     print(f"\n{country}: {len(rows)} rows")
#     for r in rows:
#         print(f"  - {r['title']}")

from retrieval.query_classifier import classify_query_llm

history = [
    {"role": "user", "text": "tell me more about the EU Blue Card"},
    {"role": "assistant", "text": "The EU Blue Card is a residence permit... [full answer text from turn 1]"},
]
result = classify_query_llm("how much does it cost?", history=history)
print(result)