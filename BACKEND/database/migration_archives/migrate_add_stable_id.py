"""
migrate_add_stable_id.py

One-time migration: adds stable_id column, backfills it for existing
rows using compute_stable_id, then enforces uniqueness at the DB level.

Run this ONCE, before switching the embed script over to stable_id.
Safe to re-run (idempotent) — skips rows that already have a stable_id.
"""

import sqlite3
from BACKEND.database.id_utils import compute_stable_id

DATABASE_NAME = "visa_assistant.db"


def migrate():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Step 1: add the column if it doesn't exist yet
    cursor.execute("PRAGMA table_info(visa_knowledge)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    if "stable_id" not in existing_columns:
        cursor.execute("ALTER TABLE visa_knowledge ADD COLUMN stable_id TEXT")
        print("Added stable_id column.")
    else:
        print("stable_id column already exists — skipping ALTER TABLE.")

    # Step 2: backfill stable_id for rows that don't have one yet
    cursor.execute("SELECT * FROM visa_knowledge WHERE stable_id IS NULL")
    rows = cursor.fetchall()
    print(f"Backfilling stable_id for {len(rows)} rows...")

    seen_ids = {}   # detect collisions DURING backfill, before the unique index catches them
    collisions = []

    for row in rows:
        sid = compute_stable_id(row)

        if sid in seen_ids:
            collisions.append((row["id"], seen_ids[sid], sid))
            print(f"  COLLISION: row id={row['id']} ('{row['title']}') "
                  f"collides with row id={seen_ids[sid]} — same stable_id {sid}")
            continue   # don't write a duplicate stable_id, surface it instead

        seen_ids[sid] = row["id"]
        cursor.execute(
            "UPDATE visa_knowledge SET stable_id = ? WHERE id = ?",
            (sid, row["id"]),
        )

    conn.commit()

    if collisions:
        print(f"\n{len(collisions)} COLLISION(S) FOUND — these rows were NOT backfilled.")
        print("Resolve manually (check if they're true duplicates or need a more specific key)"
              " before proceeding to Step 3.")
        conn.close()
        return False   # stop here — don't add the unique index over broken data

    # Step 3: enforce uniqueness at the DB level, now that backfill is clean
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_visa_stable_id ON visa_knowledge(stable_id)"
    )
    conn.commit()
    conn.close()

    print("Migration complete. stable_id backfilled and uniquely indexed.")
    return True


if __name__ == "__main__":
    migrate()