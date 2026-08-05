"""
embedder_postgres.py

Postgres-native replacement for the old Chroma-based embedder.py.
Reads embedding_text from Supabase, computes embeddings locally,
writes them back into the same row's `embedding` column.

No separate vector store to sync — content and embedding live in one
table, one transaction. No stale-vector cleanup needed either: deleting
a row deletes its embedding, atomically, by definition.
"""

import os
import psycopg2
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_DB_URL")
EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"

FORCE_REBUILD = False   # set True once if you deliberately change EMBEDDING_MODEL


def get_connection():
    return psycopg2.connect(SUPABASE_URL)


def embed_all(force_rebuild: bool = False):
    print("Loading embedding model...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print("Embedding model loaded.")

    conn = get_connection()
    cursor = conn.cursor()

    if force_rebuild:
        ...
        cursor.execute("""
            SELECT id, stable_id, title, embedding_text, content_hash
            FROM visa_knowledge
        """)
    else:
        cursor.execute("""
            SELECT id, stable_id, title, embedding_text, content_hash
            FROM visa_knowledge
            WHERE embedding IS NULL
               OR embedding_model IS DISTINCT FROM %s
               OR content_hash IS DISTINCT FROM embedded_content_hash
        """, (EMBEDDING_MODEL,))

    rows = cursor.fetchall()
    print(f"{len(rows)} row(s) need embedding.")

    embedded = 0
    skipped = 0
    failed = []

    for row_id, stable_id, title, embedding_text, content_hash in rows:
        if not embedding_text:
            print(f"  SKIP (no embedding_text): {title}")
            skipped += 1
            continue

        try:
            vector = model.encode(embedding_text, normalize_embeddings=True).tolist()

            cursor.execute("""
                UPDATE visa_knowledge
                SET embedding = %s,
                    embedding_model = %s,
                    embedded_content_hash = %s,
                    last_embedded_at = now()
                WHERE id = %s
            """, (vector, EMBEDDING_MODEL, content_hash, row_id))

            conn.commit()
            embedded += 1
            print(f"  Embedded: {title}")

        except Exception as e:
            conn.rollback()
            print(f"  FAILED: {title} — {e}")
            failed.append(title)

    # rows already up to date, for the summary count
    cursor.execute("SELECT COUNT(*) FROM visa_knowledge WHERE embedding IS NOT NULL")
    total_embedded = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    print(f"\nDone. Embedded this run: {embedded} | Skipped (no text): {skipped} | Failed: {len(failed)}")
    print(f"Total rows with embeddings now: {total_embedded}")
    if failed:
        print(f"Failed titles: {failed}")


if __name__ == "__main__":
    embed_all(force_rebuild=FORCE_REBUILD)