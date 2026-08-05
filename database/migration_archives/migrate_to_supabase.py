"""
migrate_to_supabase.py

One-time migration: copies all rows from local SQLite visa_knowledge
into the new Supabase Postgres table. Structured fields only —
embeddings are populated separately afterward by the Postgres-native
embedder script, since we're re-embedding fresh rather than trying
to carry vectors over from Chroma.
"""

import sqlite3
import json
import os
import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv

load_dotenv()

SQLITE_DB = "visa_assistant.db"
SUPABASE_URL = os.getenv("SUPABASE_DB_URL")  # the pooled connection string

# Columns that are JSON in SQLite (stored as TEXT) and need to become
# real Python objects for JSONB insertion — everything else is a
# straight passthrough.
JSON_COLUMNS = {
    "eligibility", "required_documents", "application_process",
    "official_links", "important_notes", "mandatory_prerequisites",
    "min_income_threshold", "extra_information",
}

BOOLEAN_COLUMNS = {"pr_pathway_available"}


def safe_json(value):
    """Parse JSON text safely; return None on missing/invalid input."""
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        print(f"  WARNING: could not parse JSON value, storing as null: {value[:80]}")
        return None


def migrate():
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()

    sqlite_cursor.execute("SELECT * FROM visa_knowledge")
    rows = sqlite_cursor.fetchall()
    print(f"Read {len(rows)} rows from SQLite.")

    pg_conn = psycopg2.connect(SUPABASE_URL)
    pg_cursor = pg_conn.cursor()

    columns = [desc[0] for desc in sqlite_cursor.description if desc[0] != "id"]
    # id is SERIAL in Postgres — let it auto-generate, don't carry over SQLite's

    inserted = 0
    failed = []

    for row in rows:
        row_dict = dict(row)
        row_dict.pop("id", None)

        values = []
        for col in columns:
            val = row_dict.get(col)
            if col in JSON_COLUMNS:
                values.append(Json(safe_json(val)) if val else None)
            elif col in BOOLEAN_COLUMNS:
                values.append(bool(val) if val is not None else None)
            else:
                values.append(val)

        placeholders = ", ".join(["%s"] * len(columns))
        col_names = ", ".join(columns)

        try:
            pg_cursor.execute(
                f"INSERT INTO visa_knowledge ({col_names}) VALUES ({placeholders})",
                values,
            )
            inserted += 1
        except Exception as e:
            print(f"  FAILED on row title='{row_dict.get('title')}': {e}")
            pg_conn.rollback()
            failed.append(row_dict.get("title"))
            continue

    pg_conn.commit()
    pg_cursor.close()
    pg_conn.close()
    sqlite_conn.close()

    print(f"\nInserted {inserted}/{len(rows)} rows into Supabase.")
    if failed:
        print(f"Failed rows: {failed}")


if __name__ == "__main__":
    migrate()