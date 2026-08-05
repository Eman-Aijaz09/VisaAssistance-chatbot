import sqlite3
import pandas as pd

DATABASE_NAME = "visa_assistant.db"
CSV_PATH = "data/dummy_data.csv"


def import_csv():

    df = pd.read_csv(CSV_PATH)

    # NEW: convert pr_pathway_available from "TRUE"/"FALSE" strings to
    # proper booleans before writing to SQLite. Don't rely on Python's
    # bool(str) — bool("FALSE") is True, since any non-empty string is
    # truthy. Explicit string comparison instead.
    if "pr_pathway_available" in df.columns:
        df["pr_pathway_available"] = (
            df["pr_pathway_available"]
            .astype(str)
            .str.strip()
            .str.upper()
            .map({"TRUE": True, "FALSE": False})
        )

    conn = sqlite3.connect(DATABASE_NAME)

    df.to_sql(
        "visa_knowledge",
        conn,
        if_exists="append",
        index=False,
    )

    conn.close()

    print(f"Imported {len(df)} rows successfully.")


if __name__ == "__main__":
    import_csv()