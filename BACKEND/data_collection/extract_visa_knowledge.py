"""
extract_visa_knowledge.py

Phase 2: For each visa type found in visa_catalog/<Country>.json,
send a prompt to Claude or ChatGPT asking for detailed immigration
knowledge. Save results to visa_knowledge/<Country>.json.

Resume logic: skip visas already present in the output file.
Start a fresh chat every N visas to avoid context overflow.

Usage:
    python extract_visa_knowledge.py 
        --catalog_dir "DATA_INGESTION/new_approach/visa_catalog" 
        --output_dir "DATA_INGESTION/new_approach/visa_knowledge" 
        --service claude 
        --profile claude 
        --limit 5   # optional: process only N visas total
"""

import argparse
import asyncio
import json
import re
from pathlib import Path
from datetime import date

from browser_for_data import BrowserManager
# Import the response handlers from your catalog script
from visa_catalog import (
    get_claude_response_via_copy,
    get_chatgpt_response_via_copy,
    clean_json_response,
    extract_json_from_text,
)

# The prompt above
VISA_EXTRACTION_PROMPT = """
You are an expert immigration information extraction system.
You will be given a specific visa type for a country, along with its
official source URL from the government/embassy website.

TASK: Extract detailed, accurate, structured information about this visa.
Use WEB SEARCH to visit the official source URL and any related official
pages you find. If web search is unavailable, you may use your own
knowledge, but you must be extremely careful not to invent facts.

If you cannot find a piece of information, use null or []. If you are
unsure about a specific number (income threshold, fee, processing time),
set it to null rather than guessing.

CRITICAL RULES:

1. Return ONLY valid JSON. Do NOT wrap the JSON in markdown.
2. Do NOT include explanations outside the JSON.
3. If multiple official sources are available for this visa, list all URLs in "official_links".
4. If the visa type does not actually exist or you cannot find any reliable
   information, return an empty "entities" list.
5. FOR PAKISTANI APPLICANTS:
   If there are any special conditions, additional documents, or
   restrictions that apply specifically to Pakistani nationals, note
   them in "important_notes" or "extra_information". Otherwise leave
   those fields empty.

SCOPE RULE:

You MUST return EXACTLY ONE entity in "entities" — the single visa
specified by Visa Key: <<VISA_KEY>> above. Do NOT include other visa
types you encounter during research, even closely related ones on the
same page. If you find information about a different visa, ignore it;
it will be handled in its own separate request.

VISA DATA PROVIDED:
Country: <<COUNTRY>>
Visa Name: <<VISA_NAME>>
Visa Key: <<VISA_KEY>>
Purpose: <<PURPOSE>>
Official Source URL: <<SOURCE_URL>>
Notes from catalog: <<NOTES>>

JSON SCHEMA:

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

Fill in "page_title", "topic", "title", "visa_key", "visa_type" using the provided data.
"purpose" must be exactly one of: "study", "work", "tourist",
"family_reunion", "business", "permanent_residency". If the provided
purpose is one of these, use it. If the page describes a purpose that
doesn't clearly map to one of these, choose the closest match.
Never invent a new value outside this list.

FIELD RULES:

1. "entry_type" must be exactly "detailed" if the source covers eligibility,
   documents, or application process in depth; otherwise use "overview".

2. "official_links" must contain absolute URL strings only. No page titles,
   plain text, or markdown links.

3. "visa_key" is provided; do not change it.

4. "visa_type" and "title" should match the provided visa name.

5. If the page states a specific numeric income or salary requirement,
   set "min_income_threshold" as:
   {
       "threshold_type": "fixed_numeric",
       "value": number_only,
       "unit": "currency/period",
       "verified": false,
       "source_url": null,
       "effective_date": null,
       "notes": null
   }
   Do not include currency symbols or commas in "value".

6. If the page describes a points-based system:
   - Set the TOP-LEVEL "points_required" field to that number.
   - Leave "min_income_threshold" null.
   - If the exact number is not specified, leave "points_required" null
     and explain briefly in "important_notes".

7. If eligibility is employer-specific, case-by-case, institution-dependent,
   or otherwise varies:
   - Set "min_income_threshold.threshold_type" to "case_by_case".
   - Leave "value" null.
   - Use "notes" to briefly explain what it depends on.

8. If there is no income/salary/points eligibility gate at all,
   leave "min_income_threshold" entirely null and set "points_required" null.

9. "min_education_level" must be exactly one of:
   "none", "bachelor", "master", "phd", or null.
   Use null if no education requirement is mentioned or not applicable.
   Use "none" ONLY if the source explicitly states no formal education is required.

10. "min_age" / "max_age": extract only explicit numeric age requirements or limits.

11. "required_language_test" is the test name only (e.g. "IELTS", "JLPT", "TCF").
    Put the required score in "min_language_score".

12. "mandatory_prerequisites" must contain short, lowercase, underscore-separated
    structured tags, not full sentences.

13. FEE FIELD RULES:
    - "application_fee" is ALWAYS a string — the full fee description exactly
      as stated, including any variants (e.g. "EUR 90 for adults, EUR 45 for
      children aged 6-12"). Never a bare number.
    - "total_estimated_cost" is a number — specifically the BASE/STANDARD adult
      fee, extracted as a plain number, whenever "application_fee" states one
      unambiguous primary figure, even if secondary variants exist.
      Only leave "total_estimated_cost" null if there is genuinely no single
      primary figure to extract (e.g. cost is described only as "varies by
      category" with no headline number at all).
    - "cost_currency" must be non-null whenever "total_estimated_cost" is
      non-null, and null whenever "total_estimated_cost" is null. These two
      fields are always populated together, never one without the other.

14. "processing_time_days_min" / "processing_time_days_max":
    extract only numeric day/week/month ranges that can be converted to days.
    Keep the original description in "processing_time".

15. "validity": For short-stay Schengen visas, include the 90/180-day rule
    if the source states it. Otherwise describe the validity period exactly
    as stated, or leave null if not given.

16. "pr_pathway_available": true/false only if the page explicitly discusses
    whether this visa leads to permanent residency. Otherwise null.

17. "pr_pathway_years": extract the number of years only if explicitly stated.

18. "last_verified_date": DO NOT set this field. It will be filled in
    separately by the pipeline after extraction. Leave it null in your JSON.

19. STRICT CLEANLINESS:
    Do NOT append source labels like "German Mission in Pakistan" or
    "German Mission in Pakistan+1" to individual field values. Write clean
    content only. Source information belongs only in "official_links".

20. Extract only what is explicitly found on official sources or, if web
    search is unavailable, what you are highly confident about.
    When in doubt, leave the field null.
"""

COUNTRIES = [ "Germany", "USA", "France", "Australia", "Japan", "Finland"]
BASE_PROFILE_DIR = Path(r"D:\ImmigrationAssistant\browser_profiles")


def load_catalog(catalog_path: Path) -> dict:
    with open(catalog_path, encoding="utf-8") as f:
        return json.load(f)


def load_existing_knowledge(knowledge_path: Path) -> dict:
    """
    Loads an existing knowledge file if it is valid JSON.
    Returns {"entities": []} if the file doesn't exist, is empty,
    or contains malformed JSON (so the pipeline can rebuild it).
    """
    if not knowledge_path.exists():
        return {"entities": []}

    try:
        with open(knowledge_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        # Empty or corrupted file – start fresh
        print(f"  ⚠ Could not read {knowledge_path.name} (empty/corrupt). Starting fresh.")
        return {"entities": []}

    # Ensure the expected key exists
    if "entities" not in data:
        data["entities"] = []
    return data


def visa_already_extracted(knowledge_data: dict, visa_key: str) -> bool:
    for entity in knowledge_data.get("entities", []):
        if entity.get("visa_key") == visa_key:
            return True
    return False

# ------------------------------------------------------------
# SANITISATION & POST-PROCESSING
# ------------------------------------------------------------

CITATION_SUFFIX_PATTERN = re.compile(r"\s+[A-Z][\w\s]*\+\d+\s*$")

def strip_citation_artifacts(value):
    """
    Recursively strip citation-chip markers from strings.
    Applies to every string field and every string inside lists/dicts.
    """
    if isinstance(value, str):
        return CITATION_SUFFIX_PATTERN.sub("", value).strip()
    if isinstance(value, list):
        return [strip_citation_artifacts(v) for v in value]
    if isinstance(value, dict):
        return {k: strip_citation_artifacts(v) for k, v in value.items()}
    return value


ALLOWED_ENTITY_KEYS = [
    "page_title", "purpose", "topic", "visa_type", "visa_key",
    "entry_type", "title", "summary", "eligibility",
    "required_documents", "application_process", "processing_time",
    "application_fee", "validity", "official_links", "important_notes",
    "min_income_threshold", "min_education_level", "min_age", "max_age",
    "required_language_test", "min_language_score", "points_required",
    "mandatory_prerequisites", "total_estimated_cost", "cost_currency",
    "processing_time_days_min", "processing_time_days_max",
    "pr_pathway_available", "pr_pathway_years", "last_verified_date",
    "extra_information"
]

def sanitize_entity(entity: dict, country: str, visa_key: str, source_url: str) -> dict:
    """
    Apply all safety nets:
      1. Whitelist allowed keys.
      2. Force-override pipeline metadata (country, source_url, visa_key).
      3. Inject last_verified_date in DD/MM/YYYY format.
      4. Strip citation artifacts from all string fields.
      5. Derive title if missing.
    """
    # 1. Whitelist only allowed keys
    clean = {k: entity.get(k) for k in ALLOWED_ENTITY_KEYS if k in entity}

    # Set defaults for critical fields if absent
    clean.setdefault("page_title", "")
    clean.setdefault("purpose", "")
    clean.setdefault("topic", "")
    clean.setdefault("visa_type", None)
    clean.setdefault("visa_key", visa_key)
    clean.setdefault("entry_type", "detailed")
    clean.setdefault("title", "")
    clean.setdefault("summary", "")
    clean.setdefault("eligibility", [])
    clean.setdefault("required_documents", [])
    clean.setdefault("application_process", [])
    clean.setdefault("processing_time", None)
    clean.setdefault("application_fee", None)
    clean.setdefault("validity", None)
    clean.setdefault("official_links", [])
    clean.setdefault("important_notes", [])
    clean.setdefault("min_income_threshold", None)
    clean.setdefault("min_education_level", None)
    clean.setdefault("min_age", None)
    clean.setdefault("max_age", None)
    clean.setdefault("required_language_test", None)
    clean.setdefault("min_language_score", None)
    clean.setdefault("points_required", None)
    clean.setdefault("mandatory_prerequisites", [])
    clean.setdefault("total_estimated_cost", None)
    clean.setdefault("cost_currency", None)
    clean.setdefault("processing_time_days_min", None)
    clean.setdefault("processing_time_days_max", None)
    clean.setdefault("pr_pathway_available", None)
    clean.setdefault("pr_pathway_years", None)
    clean.setdefault("last_verified_date", None)
    clean.setdefault("extra_information", {})

    # 2. Force-override pipeline metadata
    clean["country"] = country
    clean["source_url"] = source_url
    clean["visa_key"] = visa_key

    # 3. Inject last_verified_date in DD/MM/YYYY format
    clean["last_verified_date"] = date.today().strftime("%d/%m/%Y")

    # 4. Strip citation artifacts recursively (except metadata)
    for key in list(clean.keys()):
        if key in ("country", "source_url", "visa_key", "last_verified_date"):
            continue
        clean[key] = strip_citation_artifacts(clean[key])

    # 5. Derive title fallback if missing
    if not clean.get("title"):
        clean["title"] = clean.get("visa_type") or visa_key

    return clean

async def process_visa(
    country: str,
    visa: dict,
    output_dir: Path,
    page,
    response_handler,
) -> bool:
    """
    Send one visa extraction prompt and update the country's knowledge file.
    """
    visa_key = visa.get("visa_key")
    visa_name = visa.get("visa_type_name", visa_key)
    purpose = visa.get("purpose", "")
    source_url = visa.get("source_url", "")
    notes = visa.get("notes", "")

    prompt = (VISA_EXTRACTION_PROMPT
          .replace("<<COUNTRY>>", country)
          .replace("<<VISA_NAME>>", visa_name)
          .replace("<<VISA_KEY>>", visa_key)
          .replace("<<PURPOSE>>", purpose)
          .replace("<<SOURCE_URL>>", source_url or "")
          .replace("<<NOTES>>", notes or ""))

    print(f"\n--- Extracting: {country} / {visa_name} ---")
    entities = []
    try:
        raw_response = await response_handler(page, prompt)
        try:
            parsed = clean_json_response(raw_response)
        except json.JSONDecodeError:
            parsed = extract_json_from_text(raw_response)

        entities = parsed.get("entities", [])

    except Exception as e:
        print(f"  FAILED: {e}")
        # Write failure marker (not a full file, just a note)
        error_file = output_dir / f"{country}_ERRORS.txt"
        with open(error_file, "a", encoding="utf-8") as ef:
            ef.write(f"{visa_key}\t{visa_name}\t{str(e)}\n")
        return False

    if not isinstance(entities, list) or len(entities) == 0:
        print("  FAILED: no entities returned.")
        return False


    # Enforce single-entity scope: keep first, warn if more
    if len(entities) > 1:
        print(f"  ⚠ Model returned {len(entities)} entities for single visa. Keeping only the first.")
        entities = entities[:1]

    # Sanitise each entity before saving
    clean_entities = []
    for ent in entities:
        if isinstance(ent, dict):
            clean_entities.append(sanitize_entity(ent, country, visa_key, source_url))

    if not clean_entities:
        print("  FAILED: sanitised entity list is empty.")
        return False

    # Load existing knowledge file, append/update entities
    country_file = output_dir / f"{country}_knowledge.json"
    knowledge_data = load_existing_knowledge(country_file)
    knowledge_data.setdefault("entities", [])

    # Remove previous entities for this visa_key, then add the new ones
    knowledge_data["entities"] = [
        e for e in knowledge_data["entities"] if e.get("visa_key") != visa_key
    ]
    knowledge_data["entities"].extend(clean_entities)

    country_file.write_text(
        json.dumps(knowledge_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  Saved {len(clean_entities)} entity(ies) for {visa_key}.")
    return True


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog_dir", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--countries", nargs="*", default=COUNTRIES)
    parser.add_argument("--service", default="claude", choices=["claude", "chatgpt"])
    parser.add_argument("--profile", default="claude")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max number of visas to process total (optional)")
    args = parser.parse_args()

    catalog_dir = Path(args.catalog_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Select response handler and new chat URL
    if args.service == "claude":
        response_handler = get_claude_response_via_copy
        new_chat_url = "https://claude.ai/new"
        prompt_box_locator = 'div[contenteditable="true"][aria-label="Write your prompt to Claude"]'
    else:
        response_handler = get_chatgpt_response_via_copy
        new_chat_url = "https://chat.openai.com"
        prompt_box_locator = 'div[contenteditable="true"][aria-label="Chat with ChatGPT"]'

    browser = BrowserManager(service=args.service)
    profile_dir = str(BASE_PROFILE_DIR / args.profile)
    page = await browser.start(profile_dir=profile_dir)

    processed_count = 0
    chat_message_count = 0
    CHAT_RESET_EVERY = 3  # start a fresh chat every N visas

    for country in args.countries:
        catalog_file = catalog_dir / f"{country}.json"
        if not catalog_file.exists():
            print(f"Catalog for {country} not found: {catalog_file}")
            continue

        catalog = load_catalog(catalog_file)
        visa_types = catalog.get("visa_types", [])
        if not visa_types:
            print(f"No visas in catalog for {country}.")
            continue

        print(f"\n{'='*70}\nProcessing country: {country} ({len(visa_types)} visas)\n{'='*70}")

        for visa in visa_types:
            if args.limit and processed_count >= args.limit:
                print("Reached --limit. Stopping.")
                await browser.stop()
                return

            visa_key = visa.get("visa_key")
            if not visa_key:
                print("  Skipping visa with no visa_key:", visa)
                continue

            # Check if already extracted
            knowledge_file = output_dir / f"{country}_knowledge.json"
            knowledge_data = load_existing_knowledge(knowledge_file)
            if visa_already_extracted(knowledge_data, visa_key):
                print(f"  Already extracted: {visa_key} – skipping.")
                continue

            # Open a fresh chat if needed
            if chat_message_count == 0:
                await browser.goto(new_chat_url)
                print(f"\nOpened new chat for {args.service}.")
                prompt_box = page.locator(prompt_box_locator)
                try:
                    await prompt_box.wait_for(state="visible", timeout=30000)
                except Exception:
                    print("ERROR: Prompt box not found. Check login/session.")
                    await browser.stop()
                    return
                print("Session verified.\n")

            # Process the visa
            ok = await process_visa(
                country=country,
                visa=visa,
                output_dir=output_dir,
                page=page,
                response_handler=response_handler,
            )

            if ok:
                processed_count += 1
                chat_message_count += 1
                if chat_message_count >= CHAT_RESET_EVERY:
                    print("  Resetting chat to keep context fresh.")
                    chat_message_count = 0
            else:
                # If extraction failed, force a fresh chat to avoid contamination
                print("  Forcing fresh chat after failure.")
                chat_message_count = 0

            await page.wait_for_timeout(2000)

    print("\n" + "="*70)
    print("EXTRACTION DONE")
    print("="*70)
    print(f"Total visas processed successfully: {processed_count}")
    print(f"Output directory: {output_dir}")
    await browser.stop()


if __name__ == "__main__":
    asyncio.run(main())