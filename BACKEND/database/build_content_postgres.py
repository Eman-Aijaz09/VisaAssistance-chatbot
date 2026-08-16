"""
build_content_postgres.py

Postgres version of the old build_content.py — populates content,
embedding_text, and content_hash for rows that don't have them yet
(or whose source fields changed since last build).
"""

import json
import hashlib
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_DB_URL")


def compute_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def format_list(value):
    if not value:
        return ""
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value)
    return str(value)


def format_extra_info(value):
    if not value:
        return "None"
    try:
        return json.dumps(value, indent=2)
    except (TypeError, ValueError) as e:
        print(f"  WARNING: malformed extra_information — using raw value. Error: {e}")
        return str(value)


def build_document(row: dict) -> str:
    document = f"""
        Title:
        {row["title"]}

        Country:
        {row["country"]}

        Purpose:
        {row["purpose"]}

        Topic:
        {row["topic"]}

        Visa Type:
        {row["visa_type"]}

        Entry Type:
        {row["entry_type"]}

        Summary:
        {row["summary"]}

        Eligibility:
        {format_list(row["eligibility"])}

        Required Documents:
        {format_list(row["required_documents"])}

        Application Process:
        {format_list(row["application_process"])}

        Processing Time:
        {row["processing_time"] or "Not specified"}

        Application Fee:
        {row["application_fee"] or "Not specified"}

        Total Estimated Cost:
        {f'{row["total_estimated_cost"]} {row["cost_currency"]}' if row["total_estimated_cost"] else "Not specified"}

        Validity:
        {row["validity"] or "Not specified"}

        Important Notes:
        {format_list(row["important_notes"])}

        Official Links:
        {format_list(row["official_links"])}

        Extra Information:
        {format_extra_info(row["extra_information"])}
    """
    return document.strip()


def build_embedding_text(row: dict) -> str:
    parts = [
        row["title"] or "",
        row["purpose"] or "",
        row["topic"] or "",
        row["visa_type"] or "",
        row["summary"] or "",
    ]
    return " | ".join(p.strip() for p in parts if p and p.strip())


def build_content():
    conn = psycopg2.connect(SUPABASE_URL)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, country, purpose, topic, visa_type, entry_type,
               summary, eligibility, required_documents, application_process,
               processing_time, application_fee, total_estimated_cost,
               cost_currency, validity, important_notes, official_links,
               extra_information
        FROM visa_knowledge
    """)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    print(f"Found {len(rows)} records.")

    failed = []
    updated = 0

    for row_values in rows:
        row = dict(zip(columns, row_values))
        try:
            content = build_document(row)
            embedding_text = build_embedding_text(row)
            new_hash = compute_content_hash(content)

            cursor.execute("""
                UPDATE visa_knowledge
                SET content = %s, embedding_text = %s, content_hash = %s
                WHERE id = %s
            """, (content, embedding_text, new_hash, row["id"]))
            conn.commit()
            updated += 1
        except Exception as e:
            conn.rollback()
            print(f"  ERROR building content for '{row.get('title')}': {e}")
            failed.append(row.get("title"))

    cursor.close()
    conn.close()

    print(f"\nContent built for {updated}/{len(rows)} rows.")
    if failed:
        print(f"Failed: {failed}")


if __name__ == "__main__":
    build_content()