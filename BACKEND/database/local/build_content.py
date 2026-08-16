import sqlite3
import json
import hashlib

def compute_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

DATABASE_NAME = "visa_assistant.db"


def format_list(value):
    """
    Convert JSON string lists into readable bullet points.
    """
    if not value:
        return ""

    try:
        items = json.loads(value)

        if isinstance(items, list):
            return "\n".join(f"- {item}" for item in items)

        return str(items)

    except Exception:
        return str(value)

def format_extra_info(value):
    """
    Safely pretty-print the extra_information JSON blob. Falls back
    to the raw string (with a warning) instead of crashing the whole
    build_content() run on one malformed row.
    """
    if not value:
        return "None"

    try:
        parsed = json.loads(value)
        return json.dumps(parsed, indent=2)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"  WARNING: malformed extra_information JSON — using raw value. Error: {e}")
        return str(value)
    
def build_document(row):
    """
    Build one document for embedding.
    """

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

def build_embedding_text(row):
    """
    Short, concentrated text used ONLY for embedding — deliberately
    excludes long lists (eligibility, documents, process) and
    extra_information, since embedding those alongside the summary
    dilutes the topical signal and causes long/detailed entities to
    rank poorly against short ones for broad, vague queries.
    """

    parts = [
        row["title"] or "",
        row["purpose"] or "",
        row["topic"] or "",
        row["visa_type"] or "",
        row["summary"] or "",
    ]

    return " | ".join(p.strip() for p in parts if p and p.strip())

def build_content():

    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("SELECT * FROM visa_knowledge")
    rows = cursor.fetchall()

    print(f"Found {len(rows)} records.")

    failed_rows = []

    for row in rows:
        try:
            content = build_document(row)
            embedding_text = build_embedding_text(row)
            new_hash = compute_content_hash(content)

            cursor.execute(
                """
                UPDATE visa_knowledge
                SET content = ?, embedding_text = ?, content_hash = ?
                WHERE id = ?
                """,
                (content, embedding_text, new_hash, row["id"]),
            )
        except Exception as e:
            print(f"  ERROR building content for row id={row['id']} ('{row['title']}'): {e}")
            failed_rows.append(row["id"])

    if failed_rows:
        print(f"\n{len(failed_rows)} row(s) failed to build: {failed_rows}")

    conn.commit()
    conn.close()

    if failed_rows:
        print(f"Content column populated with {len(failed_rows)} failure(s) — see above.")
    else:
        print("Content column populated successfully.")


if __name__ == "__main__":
    build_content()