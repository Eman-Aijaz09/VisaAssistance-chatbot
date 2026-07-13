import csv
import json
from models.visa_knowledge import VisaKnowledge


def is_duplicate_entity(entity: dict, seen_entities: set) -> bool:
    """
    Check whether an extracted knowledge entity is a duplicate.

    Uses (country, title, visa_type) as a unique identifier.
    """

    unique_key = (
        entity.get("country", "").strip().lower(),
        entity.get("title", "").strip().lower(),
        entity.get("visa_type", "").strip().lower()
        if entity.get("visa_type")
        else "",
    )

    if unique_key in seen_entities:
        return True

    seen_entities.add(unique_key)
    return False


def is_complete_entity(entity: dict, required_keys: list) -> bool:
    """
    Check if all required fields exist and are not empty.
    """

    for key in required_keys:
        value = entity.get(key)

        if value is None:
            return False

        if isinstance(value, str) and not value.strip():
            return False

        if isinstance(value, list) and len(value) == 0:
            return False

    return True


def save_entities_to_csv(entities: list, filename: str):
    """
    Save VisaKnowledge entities to a CSV file.

    Supports both:
    - dictionaries
    - VisaKnowledge Pydantic objects
    """

    if not entities:
        print("No entities to save.")
        return

    fieldnames = list(VisaKnowledge.model_fields.keys())

    with open(filename, mode="w", newline="", encoding="utf-8") as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        writer.writeheader()

        for entity in entities:

            # Convert Pydantic model → dict
            if isinstance(entity, VisaKnowledge):
                entity = entity.model_dump()

            row = {}

            for field in fieldnames:
                value = entity.get(field)

                # Serialize lists/dictionaries to JSON
                if isinstance(value, (list, dict)):
                    row[field] = json.dumps(value, ensure_ascii=False)

                else:
                    row[field] = value

            writer.writerow(row)

    print(f"Saved {len(entities)} knowledge entities to '{filename}'.")