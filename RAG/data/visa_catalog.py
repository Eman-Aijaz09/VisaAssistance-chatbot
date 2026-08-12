"""
discover_visa_catalog.py

Phase 1 of the new ingestion strategy: for each of the 6 target
countries, asks Claude (via the browser automation session, with web
search enabled) to search official sources and enumerate every real
visa/immigration category it can find — NOT from memory.

Output: visa_catalog/<Country>.json — one file per country, a list of
draft visa entries. This file is meant to be reviewed BY HAND before
phase 2 (per-visa extraction) is built from it, since a hallucinated
or omitted visa type here would silently propagate into every
downstream extraction prompt.

Usage:
    python discover_visa_catalog.py --output_dir "DATA_INGESTION/new_approach/visa_catalog"
"""

import argparse
import asyncio
import json
import re
from pathlib import Path

from browser_for_data import BrowserManager


COUNTRIES = ["Germany", "USA", "France", "Australia", "Japan", "Qatar","Canada","Turkey","Italy"]


# ============================================================
# CATALOG DISCOVERY PROMPT
# ============================================================

CATALOG_PROMPT = """
You are an expert immigration research assistant.

TASK: Use web search to find the official government or embassy
immigration website(s) for {{COUNTRY}}, and enumerate EVERY distinct
visa or immigration category that country actually offers.

CRITICAL RULES:

1. You MUST use web search for this. Do NOT list visa types from your
   own memory/training knowledge. Only include a visa type if you can
   point to an actual official source page you found via search that
   confirms it exists.

2. If you are not confident a visa type is real and currently offered
   (based on what you found via search), DO NOT include it. Omitting
   a real visa type is a much smaller problem than inventing one that
   doesn't exist — when in doubt, leave it out.

3. Cover all major purposes if they exist for this country: work,
   study, tourist, family_reunion, business, permanent_residency.
   Not every country will have a distinct visa for every purpose —
   only include what you actually found.

4. For each visa type, include the specific official source URL where
   you found it. Never guess, estimate, or reconstruct a URL — if you
   found the visa mentioned but can't pin an exact URL for it, set
   "source_url" to null and explain in "notes".

5. "visa_key" is a short, canonical, machine-readable identifier:
   lowercase, underscores instead of spaces, no country name in it.
   Examples: "eu_blue_card", "job_seeker_visa", "student_visa_type_d".

6. Return ONLY valid JSON. No markdown fences. No explanation text
   outside the JSON. Return in text, in chat, no json-code format.

JSON SCHEMA:

{
    "country": "{{COUNTRY}}",
    "search_performed": true,
    "visa_types": [
        {
            "visa_key": "",
            "visa_type_name": "",
            "purpose": "",
            "source_url": "",
            "notes": ""
        }
    ]
}

"purpose" must be exactly one of: "study", "work", "tourist",
"family_reunion", "business", "permanent_residency".

Begin your search now for {{COUNTRY}}'s official visa categories.
"""


# ============================================================
# JSON CLEANING (same approach as test.py)
# ============================================================

def clean_json_response(raw: str) -> dict:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.IGNORECASE)
    return json.loads(cleaned.strip())

def extract_json_from_text(raw: str) -> dict:
    """
    Handles plain-text (unfenced) JSON responses, which render less
    predictably than code blocks — may have stray whitespace/line
    breaks from paragraph rendering even when the content itself is
    valid JSON. Finds the outermost {...} span and parses that,
    rather than assuming the whole string is clean.
    """
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.IGNORECASE)

    # If there's leading/trailing prose around the JSON, isolate the
    # outermost brace-matched span instead of failing on the whole string.
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace == -1 or last_brace == -1 or last_brace < first_brace:
        raise json.JSONDecodeError("No JSON object found in response", cleaned, 0)

    candidate = cleaned[first_brace:last_brace + 1]
    return json.loads(candidate)

# ============================================================
# CLAUDE RESPONSE HANDLING — same pattern as test.py, reused
# directly since it's already been hardened (stability polling,
# strict-fail-on-truncation). Kept local to this file rather than
# importing from test.py to avoid coupling phase 1 and phase 2
# scripts together prematurely.
# ============================================================

async def wait_for_stable_response(page, p_locator, code_locator, old_text: str,
                                    max_wait_ms: int = 180_000,
                                    stable_polls: int = 3,
                                    poll_ms: int = 1000) -> str:
    elapsed = 0
    last_seen = old_text
    stable_count = 0

    while elapsed < max_wait_ms:
        await page.wait_for_timeout(poll_ms)
        elapsed += poll_ms

        try:
            if await code_locator.count() > 0:
                current = (await code_locator.last.text_content()).strip()
            elif await p_locator.count() > 0:
                current = (await p_locator.last.text_content()).strip()
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

    return last_seen


async def get_claude_response_via_copy(page, prompt: str, max_wait_ms: int = 300_000) -> str:
    """
    More reliable than scraping code.language-json's nested spans
    directly, AND more reliable than depending on the Stop button's
    timing — web search responses go through multiple phases (search,
    read results, synthesize), and the Stop button can disappear and
    reappear between phases, or simply not show up yet while Claude is
    still searching. Relying on "Stop button didn't appear in N sec"
    to mean "done" is wrong for search-grounded responses specifically.

    Instead: poll for a NEW code block to appear, then wait for its
    content to stop changing across several consecutive checks. That's
    the real signal generation has finished, regardless of how many
    search/generation phases happened in between.
    """
    prompt_box = page.locator(
        'div[contenteditable="true"][aria-label="Write your prompt to Claude"]'
    )
    await prompt_box.wait_for(state="visible", timeout=30000)

    code_block_group = page.locator('div[role="group"][aria-label="json code"]')
    groups_before = await code_block_group.count()

    p_locator = page.locator('p.font-claude-response-body')
    old_text = ""
    try:
        if await p_locator.count() > 0:
            old_text = (await p_locator.last.text_content()).strip()
    except Exception:
        pass

    await prompt_box.click()
    await prompt_box.evaluate("element => element.textContent = ''")
    await prompt_box.evaluate("(element, value) => { element.textContent = value; }", prompt)
    await prompt_box.dispatch_event("input", {})
    await asyncio.sleep(0.5)
    await page.keyboard.press("Enter")
    print("  ✅ Prompt sent. Waiting for Claude to respond (web search may take a while)...")

    # ----------------------------------------------------------
    # Poll loop: wait for a NEW code block to appear (could take
    # a while if Claude is mid-search), then wait for its text to
    # stabilize across consecutive checks before trusting it's done.
    # ----------------------------------------------------------
    poll_ms = 2000
    elapsed = 0
    new_group_seen = False
    stable_count = 0
    stable_polls_required = 3
    last_seen_text = None

    while elapsed < max_wait_ms:
        await page.wait_for_timeout(poll_ms)
        elapsed += poll_ms

        groups_now = await code_block_group.count()

        if groups_now > groups_before:
            new_group_seen = True
            try:
                current_text = (await code_block_group.last.text_content()).strip()
            except Exception:
                current_text = last_seen_text

            if current_text == last_seen_text and current_text:
                stable_count += 1
                if stable_count >= stable_polls_required:
                    print(f"  ✅ Code block stable after {elapsed/1000:.0f}s.")
                    break
            else:
                stable_count = 0
                last_seen_text = current_text
                print(f"  ⏳ Still generating... ({elapsed/1000:.0f}s elapsed, {len(current_text or '')} chars so far)")
        else:
            # No code block yet — Claude is likely still searching.
            # Also bail out early if a plain-text answer stabilizes
            # instead (no code block at all this time).
            if await p_locator.count() > 0:
                try:
                    current_text = (await p_locator.last.text_content()).strip()
                except Exception:
                    current_text = last_seen_text
                if current_text and current_text != old_text:
                    if current_text == last_seen_text:
                        stable_count += 1
                        if stable_count >= stable_polls_required:
                            print(f"  ✅ Plain-text response stable after {elapsed/1000:.0f}s (no code block).")
                            break
                    else:
                        stable_count = 0
                        last_seen_text = current_text
            print(f"  ⏳ Waiting (no code block yet — likely still searching)... ({elapsed/1000:.0f}s elapsed)")
    else:
        print(f"  ⚠ Reached max_wait_ms ({max_wait_ms/1000:.0f}s) without confirmed stability — proceeding with best-effort read.")

    await page.wait_for_timeout(500)

    groups_after = await code_block_group.count()

    if groups_after > groups_before:
        last_group = code_block_group.last
        copy_button = last_group.get_by_label("Copy to clipboard")
        await copy_button.wait_for(state="attached", timeout=5000)
        await copy_button.click(force=True, timeout=10000)
        print("  ✅ Clicked copy button on new JSON code block.")

        await page.wait_for_timeout(300)

        clipboard_text = await page.evaluate("navigator.clipboard.readText()")
        if not clipboard_text or not clipboard_text.strip():
            raise RuntimeError("Copy button clicked but clipboard is empty.")

        print(f"  ✅ Read {len(clipboard_text)} chars from clipboard.")
        return clipboard_text.strip()

    print("  ℹ️ No new code block detected — falling back to text-content read.")
    if await p_locator.count() == 0:
        raise RuntimeError("No response text found (neither code block nor paragraph).")

    new_text = (await p_locator.last.text_content()).strip()
    if not new_text or new_text == old_text:
        raise RuntimeError(
            "Claude did not generate a new response within the wait window "
            "(possible rate limit, or search took longer than max_wait_ms)."
        )

    return new_text
# ============================================================
# PROCESS ONE COUNTRY
# ============================================================

async def process_country(country: str, output_dir: Path, page) -> bool:
    output_path = output_dir / f"{country}.json"
    error_path = output_dir / f"{country}_FAILED.txt"

    if error_path.exists():
        error_path.unlink()

    prompt = CATALOG_PROMPT.replace("{{COUNTRY}}", country)

    print()
    print("=" * 70)
    print(f"Discovering visa catalog for: {country}")
    print("=" * 70)

    try:
        raw_response = await get_claude_response_via_copy(page, prompt)
        try:
            parsed = clean_json_response(raw_response)
        except json.JSONDecodeError:
            parsed = extract_json_from_text(raw_response)
    except (json.JSONDecodeError, RuntimeError) as e:
        print(f"  FAILED: {e}")
        error_path.write_text(
            f"ERROR:\n{e}\n\n--- RAW RESPONSE ---\n{locals().get('raw_response', 'NO RESPONSE')}",
            encoding="utf-8",
        )
        return False

    visa_types = parsed.get("visa_types", [])
    if not isinstance(visa_types, list):
        print("  FAILED: 'visa_types' is not a list.")
        return False

    output_path.write_text(
        json.dumps({"country": country, "visa_types": visa_types}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  Saved: {output_path.name} ({len(visa_types)} visa types found)")

    # Flag anything missing a source_url right in the console output,
    # so it's visible during your manual review pass, not just buried
    # in the JSON.
    missing_source = [v.get("visa_type_name", "?") for v in visa_types if not v.get("source_url")]
    if missing_source:
        print(f"  ⚠ {len(missing_source)} visa type(s) with NO source_url — review these closely: {missing_source}")

    return True


# ============================================================
# MAIN
# ============================================================

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--countries", nargs="*", default=COUNTRIES,
                         help="Override the default 6-country list, e.g. --countries Germany USA")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    countries_to_run = []
    for country in args.countries:
        output_path = output_dir / f"{country}.json"
        if output_path.exists():
            print(f"Skipping {country} — already saved ({output_path.name} exists).")
            continue
        countries_to_run.append(country)
    
    if not countries_to_run:
        print("Nothing to do — all countries already have saved catalogs.")
        return

    browser = BrowserManager()
    page = await browser.start()

    succeeded, failed = 0, 0

    for country in countries_to_run:
        # One fresh chat per country — catalog discovery for one
        # country shouldn't be influenced by context from another.
        await browser.goto("https://claude.ai/new")
        print(f"\nClaude opened for {country}.")

        prompt_box = page.locator(
            'div[contenteditable="true"][aria-label="Write your prompt to Claude"]'
        )
        try:
            await prompt_box.wait_for(state="visible", timeout=30000)
        except Exception:
            print("\nERROR: Claude prompt box was not found. Check login/session.")
            return

        # Reminder: confirm web search is toggled ON in this browser
        # profile/session before running for real — this script does
        # not (and reliably cannot) toggle it via DOM injection.
        ok = await process_country(country, output_dir, page)
        succeeded += int(ok)
        failed += int(not ok)

        await page.wait_for_timeout(3000)

    print("\n" + "=" * 70)
    print("CATALOG DISCOVERY DONE")
    print("=" * 70)
    print(f"Succeeded: {succeeded}/{len(args.countries)}")
    print(f"Failed:    {failed}/{len(args.countries)}")
    print(f"\nOutput: {output_dir}")
    print("REVIEW EACH FILE BY HAND before building phase 2 prompts from it.")

    await page.wait_for_timeout(15000)


if __name__ == "__main__":
    asyncio.run(main())