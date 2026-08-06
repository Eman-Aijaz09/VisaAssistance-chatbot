import csv
import json
from models.visa_knowledge import VisaKnowledge
from enum import Enum

from difflib import SequenceMatcher

TITLE_SIMILARITY_THRESHOLD = 0.45


def _titles_similar(a: str, b: str) -> bool:
    a = (a or "").lower()
    b = (b or "").lower()
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= TITLE_SIMILARITY_THRESHOLD


def _cluster_by_title(group: list) -> list:
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
    Completeness score used to pick the primary entity when merging
    duplicates. Now also rewards presence of the structured
    hard-filter/soft-scoring fields — these feed the scoring engine
    directly, so an entity that has them should be strongly preferred
    over one that doesn't, even if the other has slightly longer
    prose lists.
    """
    score = 0
    score += len(entity.get("eligibility") or [])
    score += len(entity.get("required_documents") or [])
    score += len(entity.get("application_process") or [])
    score += len(entity.get("important_notes") or [])
    score += len(entity.get("official_links") or [])
    score += len(entity.get("mandatory_prerequisites") or [])
    score += 1 if entity.get("processing_time") else 0
    score += 1 if entity.get("application_fee") else 0
    score += 1 if entity.get("validity") else 0
    score += 1 if entity.get("extra_information") else 0

    # Hard-filter / scoring fields weighted higher (x3) — these are the
    # fields the scoring engine actually depends on, so an entity that
    # has them should outrank one that only has richer prose.
    scoring_fields = [
        "min_income_threshold", "min_education_level", "min_age", "max_age",
        "required_language_test", "min_language_score", "points_required",
        "total_estimated_cost", "cost_currency",
        "processing_time_days_min", "processing_time_days_max",
        "pr_pathway_available", "pr_pathway_years",
    ]
    for field in scoring_fields:
        if entity.get(field) is not None:
            score += 3

    return score


def _merge_list_field(primary: list, other: list) -> list:
    merged = list(primary or [])
    for item in (other or []):
        if item not in merged:
            merged.append(item)
    return merged


def merge_duplicate_entities(entities: list) -> list:
    """
    Collapses duplicate entities describing the same visa_type from
    different pages. Now merges ALL structured fields, not just the
    original prose ones — a field missing on the primary entity but
    present on a duplicate gets pulled in, instead of silently lost.
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
                primary["mandatory_prerequisites"] = _merge_list_field(primary.get("mandatory_prerequisites"), dup.get("mandatory_prerequisites"))

                # Scalar prose fields — fall back to duplicate's value if primary is missing it
                for field in ("processing_time", "application_fee", "validity", "purpose", "topic"):
                    if not primary.get(field) and dup.get(field):
                        primary[field] = dup.get(field)

                # Scalar structured fields — same fallback logic, now covering
                # every hard-filter/soft-scoring field so nothing silently drops
                for field in (
                    "min_income_threshold", "min_education_level", "min_age", "max_age",
                    "required_language_test", "min_language_score", "points_required",
                    "total_estimated_cost", "cost_currency",
                    "processing_time_days_min", "processing_time_days_max",
                    "pr_pathway_available", "pr_pathway_years",
                    "last_verified_date",
                ):
                    if primary.get(field) is None and dup.get(field) is not None:
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

            if isinstance(entity, VisaKnowledge):
                entity = entity.model_dump()

            row = {}

            for field in fieldnames:
                value = entity.get(field)

                # Enums (e.g. purpose) can render as "VisaPurpose.STUDY"
                # instead of "study" depending on Python version, since
                # Enum.__str__ can override the plain str value even on
                # a (str, Enum) mixin. Always take .value explicitly.
                if isinstance(value, Enum):
                    row[field] = value.value

                elif isinstance(value, (list, dict)):
                    row[field] = json.dumps(value, ensure_ascii=False)

                else:
                    row[field] = value

            writer.writerow(row)

    print(f"Saved {len(entities)} knowledge entities to '{filename}'.")