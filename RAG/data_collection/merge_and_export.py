"""
merge_and_export_csv.py

Reads all *_knowledge.json files from a folder, merges their
"entities" lists into one flat file, and exports a CSV compatible
with load_csv_to_supabase.py.

Usage:
    python merge_and_export_csv.py \
        --knowledge_dir "data/visa_knowledge" \
        --output_json "data/merged_knowledge.json" \
        --output_csv "data/merged_knowledge.csv"
"""

import argparse
import csv
import json
from pathlib import Path


def load_entities(knowledge_dir: Path) -> list:
    """
    Load every *_knowledge.json file and return a flat list of entity dicts.
    """
    all_entities = []
    for file in sorted(knowledge_dir.glob("*_knowledge.json")):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ⚠ Skipping {file.name}: {e}")
            continue

        entities = data.get("entities", [])
        if not isinstance(entities, list):
            print(f"  ⚠ Skipping {file.name}: 'entities' is not a list.")
            continue

        for ent in entities:
            if isinstance(ent, dict):
                all_entities.append(ent)

    return all_entities


def convert_complex_fields(entity: dict) -> dict:
    """
    Convert lists/dicts to JSON strings so they fit cleanly in CSV cells.
    Scalars (str, int, float, bool, None) remain as-is.
    """
    clean = {}
    for key, value in entity.items():
        if isinstance(value, (dict, list)):
            clean[key] = json.dumps(value, ensure_ascii=False)
        elif value is None:
            clean[key] = ""
        else:
            clean[key] = value
    return clean


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--knowledge_dir", required=True)
    parser.add_argument("--output_json", required=True)
    parser.add_argument("--output_csv", required=True)
    args = parser.parse_args()

    knowledge_dir = Path(args.knowledge_dir)
    if not knowledge_dir.exists():
        print(f"Knowledge directory not found: {knowledge_dir}")
        return

    entities = load_entities(knowledge_dir)
    if not entities:
        print("No entities found. Nothing to export.")
        return

    print(f"Loaded {len(entities)} entities from {knowledge_dir}")

    # Convert nested structures to JSON strings for CSV
    csv_entities = [convert_complex_fields(e) for e in entities]

    # Save merged JSON (with original nested structures)
    output_json = Path(args.output_json)
    output_json.write_text(
        json.dumps({"entities": entities}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Saved merged JSON: {output_json}")

    # Determine CSV columns in a stable, human-friendly order
    preferred = [
        "country", "visa_key", "visa_type", "purpose", "entry_type",
        "page_title", "title", "topic", "summary",
        "eligibility", "required_documents", "application_process",
        "processing_time", "application_fee", "validity",
        "official_links", "important_notes",
        "min_income_threshold", "min_education_level",
        "min_age", "max_age", "required_language_test",
        "min_language_score", "points_required",
        "mandatory_prerequisites", "total_estimated_cost",
        "cost_currency", "processing_time_days_min",
        "processing_time_days_max", "pr_pathway_available",
        "pr_pathway_years", "last_verified_date", "extra_information",
        "source_url",
    ]

    columns = preferred[:]
    # Add any columns not already in preferred, preserving first-seen order
    for ent in csv_entities:
        for key in ent:
            if key not in columns:
                columns.append(key)

    # Write CSV
    output_csv = Path(args.output_csv)
    with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for ent in csv_entities:
            row = {col: ent.get(col, "") for col in columns}
            writer.writerow(row)

    print(f"Saved CSV: {output_csv}")
    print(f"Columns: {len(columns)}")


if __name__ == "__main__":
    main()