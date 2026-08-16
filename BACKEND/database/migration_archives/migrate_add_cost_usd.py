"""
migrate_add_cost_usd.py

One-time migration: adds total_estimated_cost_usd column, backfills
it from total_estimated_cost + cost_currency using convert_to_usd().

Safe to re-run — always recomputes from the raw cost/currency fields,
so if USD_RATES changes later, re-running this refreshes every row.
"""

import sqlite3
from BACKEND.database.exchange_rates import convert_to_usd

DATABASE_NAME = "visa_assistant.db"


def migrate():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(visa_knowledge)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    if "total_estimated_cost_usd" not in existing_columns:
        cursor.execute("ALTER TABLE visa_knowledge ADD COLUMN total_estimated_cost_usd REAL")
        print("Added total_estimated_cost_usd column.")
    else:
        print("total_estimated_cost_usd column already exists — skipping ALTER TABLE.")

    cursor.execute("SELECT id, title, total_estimated_cost, cost_currency FROM visa_knowledge")
    rows = cursor.fetchall()
    print(f"Converting {len(rows)} rows to USD...")

    unconverted = []

    for row in rows:
        usd_value = convert_to_usd(row["total_estimated_cost"], row["cost_currency"])

        if usd_value is None and row["total_estimated_cost"] is not None:
            # had a cost, but couldn't convert — worth flagging, not silently NULL
            unconverted.append((row["id"], row["title"], row["cost_currency"]))

        cursor.execute(
            "UPDATE visa_knowledge SET total_estimated_cost_usd = ? WHERE id = ?",
            (usd_value, row["id"]),
        )

    conn.commit()
    conn.close()

    if unconverted:
        print(f"\n{len(unconverted)} row(s) had a cost but NO matching currency rate:")
        for rid, title, currency in unconverted:
            print(f"  id={rid} '{title}' currency='{currency}'")
        print("Add these currencies to USD_RATES in exchange_rates.py, then re-run this migration.")
    else:
        print("All rows with a cost converted successfully.")


if __name__ == "__main__":
    migrate()