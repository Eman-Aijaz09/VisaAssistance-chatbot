"""
normalization.py

Canonicalizes user-provided values for structured recommendation
fields, regardless of which entry point they came from (form,
classifier-extracted follow-up text). Applied ONCE, right before
these values reach recommend()'s SQL filtering — never duplicated
or reimplemented per call site.
"""

EDUCATION_ALIASES = {
    "none": "none", "high school": "none", "no degree": "none",
    "bachelor": "bachelor", "bachelors": "bachelor", "bachelor's": "bachelor",
    "bachelor's degree": "bachelor", "undergraduate": "bachelor", "ba": "bachelor", "bsc": "bachelor",
    "master": "master", "masters": "master", "master's": "master",
    "master's degree": "master", "graduate": "master", "ma": "master", "msc": "master",
    "phd": "phd", "doctorate": "phd", "doctoral": "phd", "doctor of philosophy": "phd",
}

LANGUAGE_TEST_ALIASES = {
    "ielts": "IELTS",
    "toefl": "TOEFL",
    "pte": "PTE",
    "tef": "TEF",
    "jlpt": "JLPT",
    "duolingo": "Duolingo",
    "cael": "CAEL",
}

COUNTRY_ALIASES = {
    "germany": "Germany", "usa": "USA", "us": "USA", "united states": "USA",
    "united states of america": "USA", "france": "France", "japan": "Japan",
    "australia": "Australia", "qatar": "Qatar",
}

PURPOSE_ALIASES = {
    "study": "study", "studying": "study", "student": "study", "education": "study",
    "work": "work", "working": "work", "job": "work", "employment": "work",
    "tourist": "tourist", "tourism": "tourist", "travel": "tourist", "visit": "tourist",
    "family_reunion": "family_reunion", "family reunion": "family_reunion", "family": "family_reunion",
    "business": "business",
    "permanent_residency": "permanent_residency", "pr": "permanent_residency",
    "permanent residency": "permanent_residency", "immigration": "permanent_residency",
}


def normalize_education_level(value: str | None) -> str | None:
    if not value:
        return None
    return EDUCATION_ALIASES.get(value.strip().lower())


def normalize_language_test(value: str | None) -> str | None:
    if not value:
        return None
    return LANGUAGE_TEST_ALIASES.get(value.strip().lower(), value.strip().upper())


def normalize_country(value: str | None) -> str | None:
    if not value:
        return None
    return COUNTRY_ALIASES.get(value.strip().lower(), value.strip().title())


def normalize_countries(values: list | None) -> list | None:
    if not values:
        return None
    normalized = [normalize_country(v) for v in values]
    return [v for v in normalized if v] or None


def normalize_purpose(value: str | None) -> str | None:
    if not value:
        return None
    return PURPOSE_ALIASES.get(value.strip().lower())