import sqlite3
import chromadb
from sentence_transformers import SentenceTransformer

def sync_deletions(cursor, collection):
    """
    Remove Chroma vectors for records no longer present in SQLite.
    Without this, deleted/re-scraped visa records stay served from
    Chroma forever even after they're gone from the source of truth.
    """
    cursor.execute("SELECT stable_id FROM visa_knowledge")
    current_ids = {row["stable_id"] for row in cursor.fetchall()}

    existing = collection.get(include=[])  # ids only, cheap call
    chroma_ids = set(existing["ids"])

    stale_ids = list(chroma_ids - current_ids)

    if stale_ids:
        collection.delete(ids=stale_ids)
        print(f"Deleted {len(stale_ids)} stale vector(s) no longer in SQLite: {stale_ids}")
    else:
        print("No stale vectors — Chroma is in sync with SQLite.")

def full_rebuild(collection):
    """
    Deliberately wipe and rebuild the entire collection — use this
    when EMBEDDING_MODEL changes, instead of relying on per-row
    mismatch detection to re-embed everything one row at a time.
    """
    confirm = input(
        f"This will DELETE all vectors in '{COLLECTION_NAME}' and re-embed "
        f"from scratch with {EMBEDDING_MODEL}. Type 'yes' to confirm: "
    )
    if confirm.strip().lower() != "yes":
        print("Aborted.")
        return False

    existing = collection.get(include=[])
    if existing["ids"]:
        collection.delete(ids=existing["ids"])
        print(f"Deleted {len(existing['ids'])} existing vectors.")
    return True

# -----------------------------
# Configuration
# -----------------------------

DATABASE_NAME = "visa_assistant.db"

CHROMA_PATH = "embeddings/chroma_db"

COLLECTION_NAME = "visa_knowledge"

EMBEDDING_MODEL =  "BAAI/bge-base-en-v1.5"

FORCE_REBUILD = False
# -----------------------------
# Load embedding model
# -----------------------------

print("Loading embedding model...")

model = SentenceTransformer(EMBEDDING_MODEL)

print("Embedding model loaded.")


# -----------------------------
# Connect SQLite
# -----------------------------

conn = sqlite3.connect(DATABASE_NAME)
conn.row_factory = sqlite3.Row

cursor = conn.cursor()

cursor.execute("""SELECT * FROM visa_knowledge""")

rows = cursor.fetchall()

print(f"Loaded {len(rows)} records from SQLite.")

# -----------------------------
# Connect ChromaDB
# -----------------------------

client = chromadb.PersistentClient(path=CHROMA_PATH)

collection = client.get_or_create_collection(name=COLLECTION_NAME)


# -----------------------------
# Generate embeddings
# -----------------------------

if FORCE_REBUILD:
    full_rebuild(collection)

for row in rows:

    embedding_text = row["embedding_text"]
    content = row["content"]
    new_hash = row["content_hash"]

    # NEW: check if this row's content already exists in Chroma with the same hash
    existing = collection.get(ids=[str(row["stable_id"])], include=["metadatas"])

    if existing["ids"]:
        existing_meta = existing["metadatas"][0]
        existing_hash = existing_meta.get("content_hash")
        existing_model = existing_meta.get("embedding_model")

        if existing_hash == new_hash and existing_model == EMBEDDING_MODEL:
            print(f"Skipping (unchanged): {row['title']}")
            continue   # content AND model both match, safe to skip
        elif existing_hash == new_hash and existing_model != EMBEDDING_MODEL:
            print(f"Re-embedding (model changed {existing_model} -> {EMBEDDING_MODEL}): {row['title']}")


    embedding = model.encode(
        embedding_text,
        normalize_embeddings=True
    ).tolist()

    metadata = {
        "stable_id": row["stable_id"],
        "embedding_model": EMBEDDING_MODEL,
        "country": row["country"],
        "visa_type": row["visa_type"] or "",
        "purpose": row["purpose"] or "", 
        "title": row["title"],
        "source_url": row["source_url"],
        "entry_type": row["entry_type"] or "",   # also fixing the earlier gap
        "topic": row["topic"] or "",
        "content_hash": new_hash,
        "last_verified_date": row["last_verified_date"] or "",
    }

    collection.upsert(
        ids=[str(row["stable_id"])],
        documents=[content],       # full detail, for answering later
        embeddings=[embedding],    # concentrated, for matching
        metadatas=[metadata],
    )

    print(f"Embedded: {row['title']}")

sync_deletions(cursor, collection)
print("\nFinished embedding all documents.")