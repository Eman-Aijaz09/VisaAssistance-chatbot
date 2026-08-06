# # retrieval/shared_resources.py

# """
# Single shared SentenceTransformer + Chroma collection instance,
# used by ALL retrieval modules — prevents each retrieval_*.py file
# from loading its own separate copy of the same model.
# """

# import chromadb
# from sentence_transformers import SentenceTransformer

# CHROMA_PATH = "embeddings/chroma_db"
# COLLECTION_NAME = "visa_knowledge"
# EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"

# _model = None
# _collection = None


# def get_model():
#     global _model
#     if _model is None:
#         _model = SentenceTransformer(EMBEDDING_MODEL)
#     return _model


# def get_collection():
#     global _collection
#     if _collection is None:
#         client = chromadb.PersistentClient(path=CHROMA_PATH)
#         _collection = client.get_collection(COLLECTION_NAME)
#     return _collection

"""
shared_resource.py

Single shared SentenceTransformer + Postgres connection, used by ALL
retrieval modules. Replaces the old Chroma client — vector search now
happens directly in Postgres via pgvector, in the same table as
structured data, so there's no second store to keep in sync.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_DB_URL")
EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"

_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def get_connection():
    """
    Returns a fresh psycopg2 connection with RealDictCursor, so rows
    come back as dicts (row["title"]) instead of tuples — matches the
    sqlite3.Row-style access the rest of the codebase already expects.
    """
    return psycopg2.connect(SUPABASE_URL, cursor_factory=RealDictCursor)