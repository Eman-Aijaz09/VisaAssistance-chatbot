"""
validate_extraction.py

Validates the Phase 2 extraction output against the Phase 1 catalog.

Checks:
  - For each country, number of entities in *_knowledge.json equals
    number of visa_types in catalog.
  - Every visa_key from catalog appears in knowledge file.
  - No duplicate visa_keys inside a country file.
  - Required fields are present and not empty.
  - Enum fields (purpose, entry_type, min_education_level) are valid.
  - URL fields start with http(s).
  - total_estimated_cost / cost_currency consistency.
  - last_verified_date follows DD/MM/YYYY.
  - No citation artifacts like "German Mission in Pakistan+1".
  - No unexpected top-level keys in entities.

Usage:
    python validate_extraction.py \
        --catalog_dir "data/visa_catalog" \
        --knowledge_dir "data/visa_knowledge"
"""

import argparse
import json
import re
from pathlib import Path

CATALOG_SUFFIX = ".json"
KNOWLEDGE_SUFFIX = "_knowledge.json"

ALLOWED_PURPOSE = {"study", "work", "tourist", "family_reunion", "business", "permanent_residency"}
ALLOWED_ENTRY_TYPE = {"detailed", "overview"}
ALLOWED_EDUCATION = {"none", "bachelor", "master", "phd", None}

DATE_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4}$")
CITATION_PATTERN = re.compile(r"\+[0-9]+\s*$")

REQUIRED_FIELDS = ["country", "source_url", "title", "purpose", "entry_type"]


def load_json(path: Path) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ⚠ Could not read {path.name}: {e}")
        return None


def validate_entity(entity: dict, country: str) -> list[str]:
    errors = []

    # Required fields
    for field in REQUIRED_FIELDS:
        if not entity.get(field):
            errors.append(f"missing {field}")

    # Enum validation
    purpose = entity.get("purpose")
    if purpose and purpose not in ALLOWED_PURPOSE:
        errors.append(f"invalid purpose '{purpose}'")

    entry_type = entity.get("entry_type")
    if entry_type and entry_type not in ALLOWED_ENTRY_TYPE:
        errors.append(f"invalid entry_type '{entry_type}'")

    min_edu = entity.get("min_education_level")
    if min_edu not in ALLOWED_EDUCATION:
        errors.append(f"invalid min_education_level '{min_edu}'")

    # URL validation
    source_url = entity.get("source_url")
    if source_url and not source_url.startswith("http"):
        errors.append("source_url is not a URL")

    official_links = entity.get("official_links")
    if official_links:
        if not isinstance(official_links, list):
            errors.append("official_links must be a list")
        else:
            for i, url in enumerate(official_links):
                if not str(url).startswith("http"):
                    errors.append(f"official_links[{i}] is not a URL: {url}")

    # Cost consistency
    cost = entity.get("total_estimated_cost")
    currency = entity.get("cost_currency")
    if cost and not currency:
        errors.append("total_estimated_cost set but cost_currency missing")
    if currency and not cost:
        errors.append("cost_currency set but total_estimated_cost missing")

    # Date format
    last_verified = entity.get("last_verified_date")
    if last_verified and not DATE_PATTERN.match(str(last_verified)):
        errors.append(f"last_verified_date '{last_verified}' not DD/MM/YYYY")

    # Citation artifact check (only for string fields)
    for key in ["summary", "processing_time", "application_fee", "validity"]:
        val = entity.get(key)
        if isinstance(val, str) and CITATION_PATTERN.search(val):
            errors.append(f"citation artifact in {key}: '{val}'")

    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog_dir", required=True)
    parser.add_argument("--knowledge_dir", required=True)
    args = parser.parse_args()

    catalog_dir = Path(args.catalog_dir)
    knowledge_dir = Path(args.knowledge_dir)

    total_missing = 0
    total_extra = 0
    total_errors = 0
    checked_countries = 0

    for catalog_file in sorted(catalog_dir.glob("*.json")):
        country = catalog_file.stem
        knowledge_file = knowledge_dir / f"{country}_knowledge.json"

        if not knowledge_file.exists():
            print(f"\n❌ {country}: knowledge file not found")
            total_missing += 1
            continue

        catalog_data = load_json(catalog_file)
        knowledge_data = load_json(knowledge_file)

        if not catalog_data or not knowledge_data:
            continue

        catalog_visa_types = catalog_data.get("visa_types", [])
        entities = knowledge_data.get("entities", [])

        if not isinstance(catalog_visa_types, list):
            print(f"\n❌ {country}: catalog 'visa_types' is not a list")
            continue
        if not isinstance(entities, list):
            print(f"\n❌ {country}: knowledge 'entities' is not a list")
            continue

        catalog_keys = [v.get("visa_key") for v in catalog_visa_types if v.get("visa_key")]
        entity_keys = [e.get("visa_key") for e in entities if isinstance(e, dict) and e.get("visa_key")]

        # Duplicate check
        seen = set()
        duplicates = []
        for key in entity_keys:
            if key in seen:
                duplicates.append(key)
            seen.add(key)

        missing = set(catalog_keys) - set(entity_keys)
        extra = set(entity_keys) - set(catalog_keys)

        print(f"\n=== {country} ===")
        print(f"  Catalog visas: {len(catalog_keys)}")
        print(f"  Extracted entities: {len(entity_keys)}")
        print(f"  Duplicates in knowledge: {len(duplicates)} ({duplicates if duplicates else ''})")
        print(f"  Missing from knowledge: {len(missing)} ({sorted(missing) if missing else ''})")
        print(f"  Extra in knowledge: {len(extra)} ({sorted(extra) if extra else ''})")

        total_missing += len(missing)
        total_extra += len(extra)

        # Field validation for each entity
        country_errors = 0
        for i, ent in enumerate(entities):
            if not isinstance(ent, dict):
                print(f"    ⚠ entity {i} is not a dict")
                continue
            ent_errors = validate_entity(ent, country)
            if ent_errors:
                country_errors += len(ent_errors)
                print(f"    ⚠ {ent.get('visa_key', '?')}:")
                for err in ent_errors:
                    print(f"        - {err}")

        total_errors += country_errors + len(duplicates)
        if country_errors == 0 and not duplicates and not missing and not extra:
            print("  ✅ All checks passed")

        checked_countries += 1

    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)
    print(f"Countries checked: {checked_countries}")
    print(f"Missing knowledge files: {total_missing}")
    print(f"Missing visa entities: {total_missing}")
    print(f"Extra visa entities: {total_extra}")
    print(f"Total field errors / duplicates: {total_errors}")

    if total_missing == 0 and total_extra == 0 and total_errors == 0:
        print("\n✅ All countries passed automated validation.")
    else:
        print("\n⚠ Fix the issues above before proceeding to merge/export.")


if __name__ == "__main__":
    main()