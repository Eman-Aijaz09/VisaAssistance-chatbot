"""
extract_visa_data.py

Stage 1 of the ingestion pipeline: reads cleaned .txt files and uses
a local LLM (via Ollama) to extract structured visa knowledge entities
as JSON. One input file can produce 0, 1, or multiple entities.

country and source_url are NOT extracted by the LLM — they're known
with certainty from the folder structure and filename, so injecting
them post-hoc avoids any risk of the model hallucinating a plausible
but wrong value for something we already know.

Usage:
    python extract_visa_data.py --input_dir "DATA_INGESTION/new_approach/cleaned_text" --output_dir "DATA_INGESTION/new_approach/extracted_json"
"""

import argparse
import json
import re
from pathlib import Path
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b-instruct"

EXTRACTION_PROMPT = """
You are an expert information extraction system specializing in immigration and visa information.

Your task is to extract ALL immigration-related knowledge entities from the provided webpage.

IMPORTANT RULES:

1. Return ONLY valid JSON.
2. Do NOT include explanations.
3. Do NOT wrap the JSON in markdown.
4. If multiple visa types or immigration topics exist, return multiple entities.
5. If information is missing, use null or [].
6. Never invent information.
7. Preserve wording whenever possible.
8. Summaries should be concise (2-3 sentences maximum).
9. If this page does not describe any specific visa or immigration program at all
   (e.g. it is a general contact page, a bilateral-relations announcement, a site
   navigation page), return an EMPTY "entities" list. Do not force an entity out
   of irrelevant content.
   9A. PAGE SCOPE RULE:
A webpage may contain information about multiple visas, partial information
about a visa, or a mixture of visa-related and general immigration content.
Extract each distinct visa/topic only when the page contains identifiable
information about it. Do not assume that the page contains the complete
information for that visa. Extract only facts explicitly present on this page.
A visa entity may therefore contain many null fields.
9B. PARTIAL INFORMATION RULE:
Do not reject an entity merely because the page provides only a small
amount of information. If the page clearly identifies a specific visa and
provides at least one meaningful fact about it, extract that entity with the
available facts and leave all unsupported fields null or empty.

DO NOT extract "country" or "source_url" — these are already known and will be
filled in separately. Leave them out of your output entirely (do not include
these keys in each entity object).

VISA_KEY RULE:
10. "visa_key" is a short, canonical, machine-readable identifier for this
    specific visa, used later to match records describing the SAME visa across
    DIFFERENT pages. Format: lowercase, underscores instead of spaces, no
    country name in it (country is tracked separately). Examples: "eu_blue_card",
    "job_seeker_visa", "student_visa_type_d", "opportunity_card". If this entity
    doesn't clearly correspond to one specific named visa, leave "visa_key" null.

ENTRY_TYPE RULE:
11. "entry_type" must be exactly "detailed" if this page covers eligibility,
    documents, or application process in real depth, or "overview" if it's a
    brief summary/listing mention only.

PURPOSE FIELD RULES:
12. "purpose" MUST be exactly one of: "study", "work", "tourist", "family_reunion", "business", "permanent_residency".
13. If the page describes a purpose that doesn't clearly map to one of these, choose the closest match. Never invent a new value outside this list.

ELIGIBILITY THRESHOLD RULES (min_income_threshold, points_required):
14. If the page states a specific numeric income or salary requirement (e.g. "€50,700 per year", "PKR 500,000"), populate "min_income_threshold" as an object:
    - "threshold_type": "fixed_numeric"
    - "value": the number only (no currency symbols, no commas)
    - "unit": the currency and period, e.g. "EUR/year"
    - "verified": false
    - "source_url": null (filled in separately, not by you)
    - "effective_date": a date if the page states one, otherwise null
    - "notes": null unless there's a relevant caveat (e.g. "lower threshold for shortage occupations")

15. If the page describes a points-based system (applicant must score N points to qualify):
    - Set the TOP-LEVEL "points_required" field to that number (e.g. 65, 70).
    - Leave "min_income_threshold" null — points-based eligibility is captured entirely by "points_required", not by this field.
    - If a points system exists but this page doesn't specify the exact number, leave "points_required" null and add a note in "important_notes" instead of guessing.

16. If the page describes eligibility as employer-specific, case-by-case, institution-dependent, or "varies" (e.g. US H-1B prevailing wage, Qatar case-by-case work permits):
    - Set "min_income_threshold.threshold_type" to "case_by_case"
    - Leave "value" null
    - Use "notes" to briefly state what it depends on (e.g. "varies by occupation and region per DOL prevailing wage")

17. If there is no income/salary/points eligibility gate at all for this visa (e.g. a tourist visa), leave "min_income_threshold" entirely null and set "points_required" to null. Do not use "case_by_case" for something that simply has no such requirement — that value is reserved for gates that exist but aren't numerically fixed.

OTHER STRUCTURED FIELD RULES:
18. "min_education_level" must be exactly one of: "none", "bachelor", "master", "phd", or null if not stated.
19. "min_age" / "max_age": extract only if the page states an explicit numeric age requirement or limit. Otherwise null.
20. "required_language_test" is the test name only (e.g. "IELTS", "JLPT", "TCF"), not the score. Put the required score, as written on the page, in "min_language_score" (keep as string since scales differ, e.g. "6.0", "N2", "B2").
21. "mandatory_prerequisites" is a list of short structured tags, not sentences — e.g. ["APS_certificate"], ["mandatory_interview"]. Do not write full sentences here; longer explanation belongs in "important_notes" instead.
22. "total_estimated_cost" is a single number (visa fee plus any other explicitly stated mandatory costs on this page, e.g. required funds). If costs are only given as a range or as multiple unrelated fees, leave it null and keep the detail in "application_fee" / "important_notes" instead of estimating or summing values yourself.
23. "cost_currency" is the currency code matching "total_estimated_cost" (e.g. "EUR", "PKR", "QAR"). Null if "total_estimated_cost" is null.
24. "processing_time_days_min" / "processing_time_days_max": extract only if the page gives a numeric day/week/month range you can convert to days. Keep the original free-text description in "processing_time" as before — this field is a separate, additional extraction, not a replacement.
25. "pr_pathway_available": true/false only if the page explicitly discusses whether this visa leads to permanent residency. Null if not mentioned at all.
26. "pr_pathway_years": the number of years stated to reach PR eligibility, if explicitly given. Otherwise null.

PROVENANCE RULES:
27. "last_verified_date" is NOT extracted from the page content. Leave it null — this will be set by the pipeline afterward.

The JSON MUST follow this schema (note: "country" and "source_url" are
intentionally NOT in this schema — do not add them):

{
    "entities": [
        {
            "page_title": "",

            "purpose": "",
            "topic": "",
            "visa_type": null,
            "visa_key": null,
            "entry_type": "detailed",

            "title": "",
            "summary": "",

            "eligibility": [],
            "required_documents": [],

            "application_process": [],

            "processing_time": null,
            "application_fee": null,
            "validity": null,

            "official_links": [],
            "important_notes": [],

            "min_income_threshold": {
                "threshold_type": "",
                "value": null,
                "unit": null,
                "points_required": null,
                "verified": false,
                "source_url": null,
                "effective_date": null,
                "notes": null
            },
            "min_education_level": null,
            "min_age": null,
            "max_age": null,
            "required_language_test": null,
            "min_language_score": null,
            "points_required": null,
            "mandatory_prerequisites": [],
            "total_estimated_cost": null,
            "cost_currency": null,

            "processing_time_days_min": null,
            "processing_time_days_max": null,
            "pr_pathway_available": null,
            "pr_pathway_years": null,

            "last_verified_date": null,

            "extra_information": {}
        }
    ]
}

The webpage content begins below.

====================================================
{{CONTENT}}
====================================================
"""


def call_ollama(prompt: str) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0},
        },
        timeout=300,
    )
    response.raise_for_status()
    return response.json()["response"]


def clean_json_response(raw: str) -> dict:
    cleaned = re.sub(r"^```json\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    return json.loads(cleaned)


def infer_country_from_path(txt_path: Path, input_root: Path) -> str:
    """
    country = the folder directly under input_root, e.g.
    cleaned_text/Germany/German Embassy Pakistan/file.txt -> "Germany"
    """
    try:
        relative = txt_path.relative_to(input_root)
        return relative.parts[0]
    except (ValueError, IndexError):
        return "Unknown"


def process_file(txt_path: Path, input_root: Path, output_dir: Path):
    raw_text = txt_path.read_text(encoding="utf-8", errors="ignore")
    country = infer_country_from_path(txt_path, input_root)
    # filename (without extension) IS the source identifier, per your setup
    source_url = txt_path.stem

    prompt = EXTRACTION_PROMPT.replace("{{CONTENT}}", raw_text)

    print(f"Processing: {txt_path.name} ({len(raw_text)} chars, country={country})...")

    try:
        raw_response = call_ollama(prompt)
        parsed = clean_json_response(raw_response)
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"  FAILED: {e}")
        error_path = output_dir / f"{txt_path.stem}_FAILED.txt"
        error_path.write_text(
            f"ERROR: {e}\n\n---RAW RESPONSE---\n{locals().get('raw_response', 'NO RESPONSE')}",
            encoding="utf-8",
        )
        return False

    entities = parsed.get("entities", [])

    # Inject country + source_url into every extracted entity —
    # never trust the LLM to have gotten these right, since we already
    # know them with certainty from the file path.
    for entity in entities:
        entity["country"] = country
        entity["source_url"] = source_url
        if entity.get("min_income_threshold"):
            entity["min_income_threshold"]["source_url"] = source_url

    output_path = output_dir / f"{txt_path.stem}.json"
    output_path.write_text(
        json.dumps({"entities": entities}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  Saved: {output_path.name} ({len(entities)} entities)")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--limit", type=int, default=None, help="Process only first N files (for testing)")
    args = parser.parse_args()

    input_root = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    txt_files = sorted(input_root.rglob("*.txt"))
    if args.limit:
        txt_files = txt_files[: args.limit]

    print(f"Found {len(txt_files)} .txt files to process.\n")

    succeeded, failed, total_entities = 0, 0, 0
    for txt_path in txt_files:
        ok = process_file(txt_path, input_root, output_dir)
        succeeded += int(ok)
        failed += int(not ok)

    print(f"\nDone. Succeeded: {succeeded} | Failed: {failed}")
    if failed:
        print("Check *_FAILED.txt files in the output directory for details.")


if __name__ == "__main__":
    main()