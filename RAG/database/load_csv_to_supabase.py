"""
load_csv_to_supabase.py

Loads a scraped CSV into visa_knowledge, with validation against the
same rules from the ingestion spec (vocabulary checks, stable_id
generation, USD conversion, JSON validity). Rows that fail validation
are reported and SKIPPED, not silently inserted broken.
"""

import csv
import json
import os
import sys
from pathlib import Path
import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv

# ---- FIX: make RAG importable from any working directory ----
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from RAG.database.id_utils import compute_stable_id
from RAG.database.exchange_rates import convert_to_usd
from RAG.retrieval.normalization import (
    EDUCATION_ALIASES,
    LANGUAGE_TEST_ALIASES,
    PURPOSE_ALIASES,
)

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_DB_URL")

JSON_COLUMNS = {
    "eligibility", "required_documents", "application_process",
    "official_links", "important_notes", "mandatory_prerequisites",
    "min_income_threshold", "extra_information",
}

VALID_PURPOSE = set(PURPOSE_ALIASES.values())
VALID_EDUCATION = set(EDUCATION_ALIASES.values())
VALID_LANGUAGE_TEST = set(LANGUAGE_TEST_ALIASES.values())
VALID_ENTRY_TYPE = {"detailed", "overview"}


def validate_row(row: dict, row_num: int) -> list:
    """Returns a list of error strings; empty list means the row is clean."""
    errors = []

    if not row.get("title", "").strip():
        errors.append("missing title")
    if not row.get("country", "").strip():
        errors.append("missing country")
    if not row.get("source_url", "").strip():
        errors.append("missing source_url")

    # NEW — visa_key is now the primary component of stable_id.
    # A missing visa_key means compute_stable_id() silently falls back
    # to the old, less stable key — better to catch this loudly at
    # validation time than have it happen invisibly at hash time.
    if not row.get("visa_key", "").strip():
        errors.append("missing visa_key")

    entry_type = (row.get("entry_type") or "").strip().lower()
    if entry_type not in VALID_ENTRY_TYPE:
        errors.append(f"entry_type '{row.get('entry_type')}' not in {VALID_ENTRY_TYPE}")

    purpose = (row.get("purpose") or "").strip().lower()
    if purpose and purpose not in VALID_PURPOSE:
        errors.append(f"purpose '{row.get('purpose')}' not recognized")

    edu = (row.get("min_education_level") or "").strip().lower()
    if edu and edu not in VALID_EDUCATION:
        errors.append(f"min_education_level '{row.get('min_education_level')}' not recognized")

    lang_test = (row.get("required_language_test") or "").strip().upper()
    if lang_test and lang_test not in VALID_LANGUAGE_TEST:
        errors.append(f"required_language_test '{row.get('required_language_test')}' not recognized")

    cost = row.get("total_estimated_cost")
    currency = row.get("cost_currency")
    if cost and not currency:
        errors.append("total_estimated_cost set but cost_currency missing")
    if currency and convert_to_usd(1.0, currency) is None:
        errors.append(f"cost_currency '{currency}' has no known USD rate")

    for col in JSON_COLUMNS:
        val = row.get(col)
        if val:
            try:
                json.loads(val)
            except (json.JSONDecodeError, TypeError):
                errors.append(f"{col} is not valid JSON")

    return errors


def load_csv(csv_path: str):
    conn = psycopg2.connect(SUPABASE_URL)
    cursor = conn.cursor()

    inserted, skipped, duplicate, already_existed = 0, 0, 0, 0
    seen_stable_ids_this_run = set()

    # with open(csv_path, newline="", encoding="utf-8") as f:
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row_num, row in enumerate(reader, start=2):  # row 1 = header
            errors = validate_row(row, row_num)
            if errors:
                print(f"  ROW {row_num} SKIPPED ('{row.get('title', '?')}'): {'; '.join(errors)}")
                skipped += 1
                continue

            stable_id = compute_stable_id(row)

            if stable_id in seen_stable_ids_this_run:
                print(f"  ROW {row_num} DUPLICATE within this CSV: '{row.get('title')}' — skipped")
                duplicate += 1
                continue
            seen_stable_ids_this_run.add(stable_id)

            usd_cost = None
            if row.get("total_estimated_cost") and row.get("cost_currency"):
                usd_cost = convert_to_usd(float(row["total_estimated_cost"]), row["cost_currency"])

            values = {
                "stable_id": stable_id,
                "country": row["country"].strip(),
                "visa_key": (row.get("visa_key") or "").strip().lower(),  # NEW
                "source_url": row["source_url"].strip(),
                "page_title": row.get("page_title"),
                "purpose": (row.get("purpose") or "").strip().lower() or None,
                "topic": row.get("topic"),
                "visa_type": row.get("visa_type"),
                "entry_type": (row.get("entry_type") or "").strip().lower(),
                "title": row["title"].strip(),
                "summary": row.get("summary"),
                "eligibility": Json(json.loads(row["eligibility"])) if row.get("eligibility") else None,
                "required_documents": Json(json.loads(row["required_documents"])) if row.get("required_documents") else None,
                "application_process": Json(json.loads(row["application_process"])) if row.get("application_process") else None,
                "official_links": Json(json.loads(row["official_links"])) if row.get("official_links") else None,
                "important_notes": Json(json.loads(row["important_notes"])) if row.get("important_notes") else None,
                "mandatory_prerequisites": Json(json.loads(row["mandatory_prerequisites"])) if row.get("mandatory_prerequisites") else None,
                "min_income_threshold": Json(json.loads(row["min_income_threshold"])) if row.get("min_income_threshold") else None,
                "extra_information": Json(json.loads(row["extra_information"])) if row.get("extra_information") else Json({}),
                "min_education_level": (row.get("min_education_level") or "").strip().lower() or None,
                "min_age": int(row["min_age"]) if row.get("min_age") else None,
                "max_age": int(row["max_age"]) if row.get("max_age") else None,
                "required_language_test": (row.get("required_language_test") or "").strip().upper() or None,
                "min_language_score": row.get("min_language_score"),
                "points_required": int(row["points_required"]) if row.get("points_required") else None,
                "total_estimated_cost": float(row["total_estimated_cost"]) if row.get("total_estimated_cost") else None,
                "cost_currency": row.get("cost_currency"),
                "total_estimated_cost_usd": usd_cost,
                "processing_time_days_min": int(row["processing_time_days_min"]) if row.get("processing_time_days_min") else None,
                "processing_time_days_max": int(row["processing_time_days_max"]) if row.get("processing_time_days_max") else None,
                "pr_pathway_available": row.get("pr_pathway_available", "").strip().upper() == "TRUE" if row.get("pr_pathway_available") else None,
                "pr_pathway_years": int(row["pr_pathway_years"]) if row.get("pr_pathway_years") else None,
                "last_verified_date": row.get("last_verified_date"),
                "processing_time": row.get("processing_time"),
                "application_fee": row.get("application_fee"),
                "validity": row.get("validity"),
            }

            cols = ", ".join(values.keys())
            placeholders = ", ".join(["%s"] * len(values))

            try:
                cursor.execute(
                    f"""INSERT INTO visa_knowledge ({cols}) VALUES ({placeholders})
                        ON CONFLICT (stable_id) DO NOTHING
                        RETURNING id""",
                    list(values.values()),
                )
                result = cursor.fetchone()
                conn.commit()
                if result:
                    inserted += 1
                else:
                    print(f"  ROW {row_num} ALREADY EXISTS in DB: '{row.get('title')}' — skipped")
                    already_existed += 1
            except Exception as e:
                conn.rollback()
                print(f"  ROW {row_num} DB ERROR ('{row.get('title')}'): {e}")
                skipped += 1

    cursor.close()
    conn.close()

    print(f"\nDone. Inserted: {inserted} | Already in DB: {already_existed} | Skipped (validation/DB errors): {skipped} | Duplicate in file: {duplicate}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python load_csv_to_supabase.py path/to/scraped.csv")
        sys.exit(1)
    load_csv(sys.argv[1])