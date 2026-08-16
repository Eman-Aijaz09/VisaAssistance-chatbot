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