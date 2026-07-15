import csv
import json
from models.visa_knowledge import VisaKnowledge

# utils/data_utils.py
from difflib import SequenceMatcher

TITLE_SIMILARITY_THRESHOLD = 0.45


def _titles_similar(a: str, b: str) -> bool:
    a = (a or "").lower()
    b = (b or "").lower()
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= TITLE_SIMILARITY_THRESHOLD


def _cluster_by_title(group: list) -> list:
    """
    Within a (country, visa_type) group, further splits entities into
    sub-clusters by title similarity. Prevents false merges when the
    LLM assigns a generic visa_type (e.g. "Employment Visa") to
    genuinely different visa categories.
    """
    clusters = []
    for entity in group:
        placed = False
        for cluster in clusters:
            if any(_titles_similar(entity.get("title"), member.get("title")) for member in cluster):
                cluster.append(entity)
                placed = True
                break
        if not placed:
            clusters.append([entity])
    return clusters

def classify_entry_type(entity: dict) -> str:
    """
    Tags an entity as "overview" (routing/hub content — good for broad,
    vague questions) or "detailed" (has concrete actionable content —
    good for specific questions).

    An entity is "overview" only if it has a real summary but is missing
    ALL of the structured, actionable fields. If it has even one of
    eligibility/required_documents/application_process, it's detailed.
    """

    summary = entity.get("summary", "")
    has_summary = bool(summary and summary.strip())

    has_eligibility = bool(entity.get("eligibility"))
    has_documents = bool(entity.get("required_documents"))
    has_process = bool(entity.get("application_process"))

    if has_summary and not (has_eligibility or has_documents or has_process):
        return "overview"

    return "detailed"


def _score_entity(entity: dict) -> int:
    """
    Rough completeness score used to pick the primary entity when
    merging duplicates. Higher = richer / more actionable content.
    """
    score = 0
    score += len(entity.get("eligibility") or [])
    score += len(entity.get("required_documents") or [])
    score += len(entity.get("application_process") or [])
    score += len(entity.get("important_notes") or [])
    score += len(entity.get("official_links") or [])
    score += 1 if entity.get("processing_time") else 0
    score += 1 if entity.get("application_fee") else 0
    score += 1 if entity.get("validity") else 0
    score += 1 if entity.get("extra_information") else 0
    return score


def _merge_list_field(primary: list, other: list) -> list:
    merged = list(primary or [])
    for item in (other or []):
        if item not in merged:
            merged.append(item)
    return merged


def merge_duplicate_entities(entities: list) -> list:
    """
    Collapses duplicate entities that describe the SAME visa_type but were
    extracted from different pages (e.g. a hub page briefly mentioning
    "EU Blue Card", and its own dedicated detail page). Grouping is done
    on (country, visa_type) since visa_type is the most reliable shared
    identifier the LLM assigns consistently across pages.

    Entities with no visa_type are left untouched -- they're usually
    either genuine overview/routing pages or one-off unique pages, and
    fuzzy-matching on title alone risks merging unrelated topics.
    """

    groups = {}
    untouched = []

    for entity in entities:
        visa_type = entity.get("visa_type")
        country = entity.get("country")

        if not visa_type or not visa_type.strip():
            untouched.append(entity)
            continue

        key = (country, visa_type.strip().lower())
        groups.setdefault(key, []).append(entity)

    merged_entities = []

    for key, group in groups.items():

        for cluster in _cluster_by_title(group):

            if len(cluster) == 1:
                merged_entities.append(cluster[0])
                continue

            group_sorted = sorted(cluster, key=_score_entity, reverse=True)
            primary = dict(group_sorted[0])
            duplicates = group_sorted[1:]

            source_urls = [primary.get("source_url")]

            for dup in duplicates:
                primary["eligibility"] = _merge_list_field(primary.get("eligibility"), dup.get("eligibility"))
                primary["required_documents"] = _merge_list_field(primary.get("required_documents"), dup.get("required_documents"))
                primary["application_process"] = _merge_list_field(primary.get("application_process"), dup.get("application_process"))
                primary["official_links"] = _merge_list_field(primary.get("official_links"), dup.get("official_links"))
                primary["important_notes"] = _merge_list_field(primary.get("important_notes"), dup.get("important_notes"))

                for field in ("processing_time", "application_fee", "validity", "purpose", "topic"):
                    if not primary.get(field) and dup.get(field):
                        primary[field] = dup.get(field)

                merged_extra = dict(dup.get("extra_information") or {})
                merged_extra.update(primary.get("extra_information") or {})
                primary["extra_information"] = merged_extra

                if dup.get("source_url") and dup.get("source_url") not in source_urls:
                    source_urls.append(dup.get("source_url"))

            if len(source_urls) > 1:
                primary["extra_information"]["merged_from_sources"] = source_urls

            merged_entities.append(primary)

    return merged_entities + untouched


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