"""
test.py

Stage 1 test of the Immigration Assistant ingestion pipeline.

Reads cleaned .txt webpages and uses Claude through the already-authenticated
browser session to extract structured immigration/visa entities as JSON.

One input file can produce:
    0 entities
    1 entity
    multiple entities

country and source_url are NOT extracted by Claude.
They are injected after extraction from the folder structure / filename.

Example:

    python test.py ^
        --input_dir "DATA_INGESTION/new_approach/cleaned_text" ^
        --output_dir "DATA_INGESTION/new_approach/extracted_json" ^
        --limit 1
"""

import argparse
import asyncio
import json
import re
from pathlib import Path
from browser_for_data import BrowserManager


# ============================================================
# EXTRACTION PROMPT
# ============================================================

EXTRACTION_PROMPT = """
You are an expert information extraction system specializing in immigration and visa information.

IMPORTANT RULES:

1. Return ONLY valid JSON, Do NOT wrap the JSON in markdown.
2. Do NOT include explanations.
3. Do NOT wrap the JSON in markdown, give answers in chat, in plain text json.
4. If multiple sources are available for a specific type, then add all sources.
5. If information is missing, use null or [].
6. Never invent information.
7. Preserve wording whenever possible.
8. Summaries should be concise (2-3 sentences maximum).

VISA_KEY RULE:
10. "visa_key" is a short, canonical, machine-readable identifier for this
specific visa, used later to match records describing the SAME visa across
DIFFERENT pages.

Format:
- lowercase
- underscores instead of spaces

Examples:
"eu_blue_card"
"job_seeker_visa"
"student_visa_type_d"
"opportunity_card"

ENTRY_TYPE RULE:
11. "entry_type" must be exactly "detailed" if this page covers eligibility,
documents, or application process in real depth, or "overview" if it's a
brief summary/listing mention only.

PURPOSE FIELD RULES:
12. "purpose" MUST be exactly one of:
"study", "work", "tourist", "family_reunion", "business", "permanent_residency".

13. If the page describes a purpose that doesn't clearly map to one of these,
choose the closest match. Never invent a new value outside this list.

ELIGIBILITY THRESHOLD RULES:

14. If the page states a specific numeric income or salary requirement,
populate "min_income_threshold" as:

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

15. If the page describes a points-based system:

- Set the TOP-LEVEL "points_required" field to that number.
- Leave "min_income_threshold" null.
- If the exact number is not specified, leave "points_required" null
  and explain the situation briefly in "important_notes".

16. If eligibility is employer-specific, case-by-case,
institution-dependent, or otherwise varies:

- Set "min_income_threshold.threshold_type" to "case_by_case".
- Leave "value" null.
- Use "notes" to briefly explain what it depends on.

17. If there is no income/salary/points eligibility gate at all,
leave "min_income_threshold" entirely null and set "points_required" null.

OTHER STRUCTURED FIELD RULES:

18. "min_education_level" must be exactly one of:
"none", "bachelor", "master", "phd", or null.

19. "min_age" / "max_age":
extract only explicit numeric age requirements or limits.

20. "required_language_test" is the test name only.
Examples: "IELTS", "JLPT", "TCF".

Put the required score in "min_language_score".

21. "mandatory_prerequisites" must contain short structured tags,
not full sentences.

22. "total_estimated_cost" is a single number only when the page explicitly
provides enough information to determine it without estimation.

If costs are a range or multiple unrelated fees, leave it null.

23. "cost_currency" is the currency code matching "total_estimated_cost".

24. "processing_time_days_min" / "processing_time_days_max":
extract only numeric day/week/month ranges that can be converted to days.

Keep the original description in "processing_time".

25. "pr_pathway_available":
true/false only if the page explicitly discusses whether this visa
leads to permanent residency.

Otherwise null.

26. "pr_pathway_years":
extract the number of years only if explicitly stated.

PROVENANCE RULE:

27. "last_verified_date" is NOT extracted from the page.
Leave it null.

IMPORTANT ANTI-HALLUCINATION RULE:

28. You must ONLY extract information explicitly supported by the
provided webpage content.

Do NOT use your general knowledge of immigration laws.

Do NOT complete missing information from memory.

Do NOT assume standard visa requirements.

If the page only gives a visa name and one fact, return that visa
with only that fact populated.

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

The webpage content begins below.

====================================================
{{CONTENT}}
====================================================
"""

# ============================================================
# JSON CLEANING
# ============================================================

def clean_json_response(raw: str) -> dict:
    """
    Attempts to turn Claude's response into a Python dictionary.

    Claude should return pure JSON, but this also handles accidental
    markdown code fences.
    """

    cleaned = raw.strip()

    # Remove markdown code fences if Claude accidentally adds them.
    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = cleaned.strip()

    return json.loads(cleaned)

# ============================================================
# COUNTRY
# ============================================================

def infer_country_from_path(
    txt_path: Path,
    input_root: Path,
) -> str:
    """
    Country is the folder directly under input_root.

    Example:

    cleaned_text/
        Germany/
            German Embassy Pakistan/
                page.txt

    -> Germany
    """

    try:
        relative = txt_path.relative_to(input_root)
        return relative.parts[0]
    except (ValueError, IndexError):
        return "Unknown"

# ============================================================
# CLAUDE RESPONSE EXTRACTION

async def wait_for_stable_response(page, p_locator,code_locator, old_text: str,
                                    max_wait_ms: int = 180_000,
                                    stable_polls: int = 3,
                                    poll_ms: int = 1000) -> str:
    """
    Polls the last assistant message's text until it stops changing
    for `stable_polls` consecutive checks. This is the real proof that
    generation has finished — Stop-button/h2 count only hint at it.
    """
    elapsed = 0
    last_seen = old_text
    stable_count = 0

    while elapsed < max_wait_ms:
        await page.wait_for_timeout(poll_ms)
        elapsed += poll_ms

        try:
            if await code_locator.count() > 0:
                current = (
                    await code_locator.last.text_content()
                ).strip()

            elif await p_locator.count() > 0:
                current = (
                    await p_locator.last.text_content()
                ).strip()

            else:
                current = ""
        except Exception:
            current = last_seen

        if current != last_seen:
            last_seen = current
            stable_count = 0
            continue

        if current != old_text:
            stable_count += 1
            if stable_count >= stable_polls:
                return current
        # current == old_text -> nothing new yet, keep polling

    return last_seen  # timed out, return best-effort text

async def get_claude_response(page, prompt: str) -> str:
    """
    Sends a prompt, confirms a new message started (h2 count + Stop button),
    then waits for the response text to genuinely stabilize before returning.
    Raises RuntimeError if no new response is detected, or if the final text
    is not valid JSON (no partial/truncated recovery — fail loudly instead).
    """
    # 1. Prompt box
    prompt_box = page.locator(
        'div[contenteditable="true"][aria-label="Write your prompt to Claude"]'
    )
    await prompt_box.wait_for(state="visible", timeout=30000)
    print("  ✅ Claude prompt box found.")

    # 2. Save state BEFORE sending
    h2_locator = page.locator('h2:has-text("Claude responded:")')
    p_locator = page.locator('p.font-claude-response-body')
    code_locator = page.locator('code.language-json')    
    h2_before = await h2_locator.count()
    old_text = ""
    try:
        if await p_locator.count() > 0:
            old_text = (await p_locator.last.text_content()).strip()
        elif await code_locator.count() > 0:
            old_text = (await code_locator.last.text_content()).strip()
    except Exception:
        pass
    print(f"  Assistant messages before: {h2_before}")

    # 3. Insert the prompt
    await prompt_box.click()
    await prompt_box.evaluate("element => element.textContent = ''")
    await prompt_box.evaluate(
        "(element, value) => { element.textContent = value; }",
        prompt
    )
    await prompt_box.dispatch_event("input", {})
    await asyncio.sleep(0.5)
    print("  ✅ Prompt inserted.")

    # 4. Send
    await page.keyboard.press("Enter")
    print("  ✅ Prompt sent. Waiting for Claude to respond...")

    # 5. Confirm a new message actually started (h2 count increase)
    try:
        await h2_locator.nth(h2_before).wait_for(state="attached", timeout=15000)
        print("  ✅ New assistant message started (h2 count increased).")
    except Exception:
        raise RuntimeError("New assistant message never started (possible rate limit).")

    # 6. Stop button as a fast-path hint (not the final proof)
    stop_button = page.locator('button[aria-label="Stop"]')
    try:
        await stop_button.wait_for(state="visible", timeout=5000)
        print("  ⏳ Stop button appeared – Claude is generating...")
        try:
            await stop_button.wait_for(state="detached", timeout=180_000)
            print("  ✅ Stop button gone – generation likely finished.")
        except Exception:
            print("  ⚠ Stop button still present after timeout – will rely on text stability.")
    except Exception:
        print("  ℹ️ Stop button did not appear – relying on text stability check.")

    # 7. Real proof of completion: poll until text stops changing
    new_text = await wait_for_stable_response(page, p_locator ,code_locator, old_text)

    if not new_text or new_text == old_text:
        raise RuntimeError(
            "Claude did not generate a new response "
            "(text unchanged/empty – likely rate limited or context full)."
        )

    print(f"\n--- FULL RAW RESPONSE ({len(new_text)} chars) ---")
    print(new_text[:10000])
    if len(new_text) > 10000:
        print("... (truncated for display)")
    print("--- END RESPONSE ---\n")

    # 8. Strict JSON parse — no partial/truncated recovery.
    #    A truncated response must FAIL, not be silently saved as partial data.
    cleaned = new_text
    code_fence = re.search(r'```(?:json)?\s*(\{.*\})\s*```', cleaned, re.DOTALL)
    if code_fence:
        cleaned = code_fence.group(1)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Response is not valid JSON (likely truncated): {e}")

    if not isinstance(parsed, dict) or "entities" not in parsed:
        raise RuntimeError("Parsed JSON missing 'entities' key.")

    print(f"  ✅ Valid JSON extracted with {len(parsed['entities'])} entities.")
    return json.dumps(parsed, ensure_ascii=False)

# ============================================================
# PROCESS ONE FILE
# ============================================================

async def process_file(
    txt_path: Path,
    input_root: Path,
    output_dir: Path,
    page,
) -> bool:

    raw_text = txt_path.read_text(encoding="utf-8",errors="ignore",)

    country = infer_country_from_path(txt_path,input_root,)

    # Create country subdirectory under output_dir
    country_dir = output_dir / country
    country_dir.mkdir(parents=True, exist_ok=True)

    # JSON output path
    output_path = country_dir / f"{txt_path.stem}.json"

    # Error log (can stay in the same country folder or a flat _errors folder – up to you)
    error_path = country_dir / f"{txt_path.stem}_FAILED.txt"

    if error_path.exists():
        error_path.unlink()
        print(f"  Cleaned up old error file: {error_path}")

    # Filename without extension is the source identifier.
    source_url = txt_path.stem

    prompt = EXTRACTION_PROMPT.replace(
        "{{CONTENT}}",
        raw_text,
    )

    print()
    print("=" * 70)
    print(f"Processing: {txt_path.name}")
    print(f"Characters: {len(raw_text):,}")
    print(f"Country: {country}")
    print("=" * 70)

    try:

        raw_response = await get_claude_response(
            page,
            prompt,
        )

        print()
        print("--- RAW CLAUDE RESPONSE ---")
        print(raw_response)
        print("--- END RESPONSE ---")
        print()

        parsed = clean_json_response(
            raw_response
        )

    except (
        json.JSONDecodeError,
        RuntimeError,
    ) as e:

        print(f"  FAILED: {e}")

        error_path.write_text(
            "ERROR:\n"
            + str(e)
            + "\n\n"
            + "--- RAW RESPONSE ---\n"
            + locals().get(
                "raw_response",
                "NO RESPONSE",
            ),
            encoding="utf-8",
        )

        return False

    # ========================================================
    # VALIDATE TOP LEVEL
    # ========================================================

    if not isinstance(parsed, dict):

        print("  FAILED: Claude response is not a JSON object.")

        return False

    entities = parsed.get(
        "entities",
        [],
    )

    if not isinstance(entities, list):

        print("  FAILED: 'entities' is not a list.")

        return False

    # ========================================================
    # INJECT TRUSTED METADATA
    # ========================================================

    for entity in entities:

        if not isinstance(entity, dict):
            continue

        # These values come from our pipeline,
        # NOT from the LLM.
        entity["country"] = country
        entity["source_url"] = source_url

        # Keep nested threshold source_url synchronized.
        threshold = entity.get(
            "min_income_threshold"
        )

        if isinstance(threshold, dict):

            threshold["source_url"] = source_url

    # ========================================================
    # SAVE
    # ========================================================

    
    output_path.write_text(
        json.dumps(
            {
                "entities": entities
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        f"  Saved: {output_path.name} "
        f"({len(entities)} entities)"
    )

    return True

# ------------------------------------------------
# RESUME LOGIC
# -----------------------------------------------

def is_already_processed(txt_path: Path, input_root: Path, output_dir: Path) -> bool:
    """
    A file is considered done only if its .json output exists.
    Failed files (*_FAILED.txt) are NOT considered done — they'll be retried.
    """
    country = infer_country_from_path(txt_path, input_root)
    output_path = output_dir / country / f"{txt_path.stem}.json"
    return output_path.exists()

# ============================================================
# MAIN
# ============================================================

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--limit", type=int, default=None, help="Process only first N files.")
    args = parser.parse_args()

    input_root = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------
    # Collect all .txt files and apply resume logic
    # --------------------------------------------------------
    all_txt_files = sorted(input_root.rglob("*.txt"))
    print(f"Total .txt files found: {len(all_txt_files)}")

    # Single pass: filter out already‑processed files, clean up old error logs
    to_process = []
    skipped = 0
    for txt_path in all_txt_files:
        country = infer_country_from_path(txt_path, input_root)
        json_path = output_dir / country / f"{txt_path.stem}.json"
        error_path = output_dir / country / f"{txt_path.stem}_FAILED.txt"

        if json_path.exists():
            # File already successfully processed – clean up any leftover error file
            if error_path.exists():
                error_path.unlink()
                print(f"  Cleaned up old error file: {error_path}")
            skipped += 1
        else:
            to_process.append(txt_path)

    if skipped:
        print(f"Skipping {skipped} already-processed files (resume mode).")

    # Apply --limit AFTER filtering
    if args.limit and len(to_process) > args.limit:
        to_process = to_process[:args.limit]

    print(f"Files to process: {len(to_process)}")

    if not to_process:
        print("No files left to process.")
        return

    # --------------------------------------------------------
    # Start browser
    # --------------------------------------------------------
    messages_in_current_chat = 0
    MESSAGES_PER_CHAT = 3

    succeeded = 0
    failed = 0
    total_entities = 0

    browser = BrowserManager()
    page = await browser.start()


    for txt_path in to_process:
        if messages_in_current_chat == 0:
            await browser.goto("https://claude.ai/new")

            print("\nClaude opened.")
            print("Current URL:", page.url)
            print("Title:", await page.title())



            prompt_box = page.locator(
                'div[contenteditable="true"][aria-label="Write your prompt to Claude"]'
            )

            try:
                await prompt_box.wait_for(state="visible", timeout=30000)
            except Exception:
                print("\nERROR: Claude prompt box was not found.")
                print("Make sure you are logged into Claude in the browser profile.")
                return
            
            print("Claude login/session verified.\n")
            
            

        ok = await process_file(
            txt_path=txt_path,
            input_root=input_root,
            output_dir=output_dir,
            page=page,
        )

        messages_in_current_chat += 1
        if messages_in_current_chat >= MESSAGES_PER_CHAT:
            messages_in_current_chat = 0

        if ok:
            succeeded += 1
            country = infer_country_from_path(txt_path, input_root)
            output_path = output_dir / country / f"{txt_path.stem}.json"
            try:
                result = json.loads(output_path.read_text(encoding="utf-8"))
                total_entities += len(result.get("entities", []))
            except Exception:
                pass

        else:
            failed += 1

        await page.wait_for_timeout(2000)
    

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------
    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)
    print(f"Succeeded: {succeeded}")
    print(f"Failed:    {failed}")
    print(f"Entities:  {total_entities}")

    if failed:
        print("\nCheck *_FAILED.txt files in:")
        # Show the root output dir (they may be in country subfolders)
        print(output_dir)
        for country in set(infer_country_from_path(p, input_root) for p in to_process):
            print(f"  {output_dir / country}")

    print("\nProcessing finished. Browser will remain open for inspection.")
    await page.wait_for_timeout(30000)


if __name__ == "__main__":

    asyncio.run(
        main()
    )