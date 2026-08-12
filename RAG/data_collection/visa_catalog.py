"""
visa_catalog.py

Phase 1 of the new ingestion strategy: for each of the target countries,
asks Claude or ChatGPT (via browser automation) to search official sources
and enumerate every real visa/immigration category it can find — NOT from
memory.

Output: visa_catalog/<Country>.json — one file per country, a list of
draft visa entries. This file is meant to be reviewed BY HAND before
phase 2 (per-visa extraction) is built from it.

Usage examples:

    # Claude (default)
    python visa_catalog.py --output_dir "visa_catalog"

    # ChatGPT (requires manual web‑search enabled)
    python visa_catalog.py --service chatgpt --profile chatgpt --output_dir "visa_catalog_chatgpt"

    # Specific countries with a different Claude profile
    python visa_catalog.py --countries Germany USA --profile claude2 --output_dir "visa_catalog"
"""

import argparse
import asyncio
import json
import re
from pathlib import Path

from browser_for_data import BrowserManager


COUNTRIES = ["Germany", "USA", "France", "Australia", "Japan","Finland"]
BASE_PROFILE_DIR = Path(r"D:\ImmigrationAssistant\browser_profiles")

# ============================================================
# CATALOG DISCOVERY PROMPT
# ============================================================

CATALOG_PROMPT = """
You are an expert immigration research assistant. Your audience is
Pakistani citizens / residents who want to apply for visas to {{COUNTRY}}.

TASK: Use web search to find ONLY official government or embassy
immigration websites for {{COUNTRY}} (domains like .gov, .gob,
.mofa.go.jp, .admin.ch, .diplo.de, .usa.gov, etc.). From those
official sources, enumerate EVERY distinct visa subclass, category,
or immigration pathway that {{COUNTRY}} offers — no matter how
specialised or obscure — and list them all.

CRITICAL RULES:

1. YOU MUST USE WEB SEARCH. Do NOT list anything from your own
   training data unless you can back it up with a real, official
   web page you found right now. If you cannot find an official
   page for a visa, do NOT include it.

2. STRICT SOURCE REQUIREMENTS:
   - ONLY official government/embassy websites. Examples:
     * .gov / .gob
     * .diplo.de
     * .mofa.go.jp
     * .homeaffairs.gov.au
     * travel.state.gov
     * canada.ca
     * qatar.embassy.gov
     * etc.
   - EXCLUDE COMPLETELY: Wikipedia, blogs, forums, commercial
     visa agencies, travel guides, news articles, unofficial
     summaries. If the URL is not clearly official, set
     "source_url" to null and explain in "notes".

3. EXHAUSTIVE COVERAGE: For the USA, list every visa class
   A-1, A-2, B-1, B-2, C-1, D, E-1, E-2, F-1, F-2, G-1, etc.
   For other countries, list every distinct visa type they have
   (e.g. work, study, visitor, family, investor, talent,
   holiday‑working, etc.). Do NOT group them into broad headings
   — treat each separate visa subclass as its own entry.

4. FOR PAKISTANI APPLICANTS: If there are any special conditions,
   additional documents, or restrictions that apply specifically
   to Pakistani nationals, note them in the "notes" field for that
   visa. Otherwise leave notes empty.

5. "visa_key" must be a short, lowercase, underscore‑separated
   machine‑readable identifier. Do NOT include the country name
   in the key unless necessary to avoid ambiguity (e.g.
   "eu_blue_card" is fine; for US A-1, use "a1_visa").

6. Return ONLY valid JSON. No markdown fences. No explanations
   outside the JSON.

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
"family_reunion", "business", "permanent_residency". If a visa
doesn't clearly fit, pick the closest match.

Begin your search now for {{COUNTRY}}'s complete official visa
catalogue from the perspective of a Pakistani applicant.
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

async def get_chatgpt_response_via_copy(page, prompt: str, max_wait_ms: int = 240_000) -> str:
    """
    Sends a prompt to ChatGPT and extracts the response.
    Does NOT depend on the Copy button or clipboard.
    Waits for the assistant message text to stabilise, then reads:
      1. code viewer text (if JSON code block exists)
      2. whole assistant message text (fallback)
    """
    # 1. Prompt box
    prompt_box = page.locator(
        'div[contenteditable="true"][aria-label="Chat with ChatGPT"]'
    )
    await prompt_box.wait_for(state="visible", timeout=30000)

    # 2. State before sending
    assistant_msg_locator = page.locator('div[data-message-author-role="assistant"]')
    msg_count_before = await assistant_msg_locator.count()
    old_text = ""
    if msg_count_before > 0:
        try:
            old_text = (await assistant_msg_locator.last.text_content()).strip()
        except Exception:
            pass

    # 3. Insert prompt via clipboard paste
    await prompt_box.click()
    await prompt_box.evaluate("el => el.textContent = ''")
    try:
        await page.evaluate("async text => await navigator.clipboard.writeText(text)", prompt)
        await page.keyboard.press("Control+V")
    except Exception:
        await prompt_box.evaluate("(el, val) => el.textContent = val", prompt)
        await prompt_box.dispatch_event("input", {})
    await asyncio.sleep(0.5)

    # 4. Send
    await page.keyboard.press("Enter")
    print("  ✅ Prompt sent. Waiting for ChatGPT to respond...")

    # 5. Wait for a new assistant message to appear
    try:
        await assistant_msg_locator.nth(msg_count_before).wait_for(state="attached", timeout=30000)
        print("  ✅ New assistant message detected.")
    except Exception:
        raise RuntimeError("New assistant message never appeared (possible rate limit).")

    # 6. Poll until the text stops changing
    last_assistant = assistant_msg_locator.last
    last_text = old_text
    stable_count = 0
    stable_required = 3
    poll_ms = 2000
    elapsed = 0

    while elapsed < max_wait_ms:
        await asyncio.sleep(poll_ms / 1000)
        elapsed += poll_ms

        try:
            current_text = (await last_assistant.text_content()).strip()
        except Exception:
            current_text = ""

        if current_text == last_text and current_text != old_text:
            stable_count += 1
            if stable_count >= stable_required:
                print(f"  ✅ Response stable after {elapsed/1000:.0f}s.")
                break
        else:
            stable_count = 0
            last_text = current_text
            print(f"  ⏳ Still generating... ({elapsed/1000:.0f}s, {len(current_text)} chars)")
    else:
        print(f"  ⚠ Timed out after {max_wait_ms/1000:.0f}s – using best available text.")

    # 7. Extract text
    raw_text = ""

    # 7a. Try code block (most reliable for JSON)
    code_viewer = last_assistant.locator('div[id="code-block-viewer"]')
    if await code_viewer.count() > 0:
        raw_text = (await code_viewer.text_content()).strip()
        print("  ✅ Extracted JSON from code block.")
        return raw_text

    # 7b. Try <pre><code>
    pre_code = last_assistant.locator('pre code')
    if await pre_code.count() > 0:
        raw_text = (await pre_code.last.text_content()).strip()
        print("  ✅ Extracted from <pre><code>.")
        return raw_text

    # 7c. Fallback: whole message text
    raw_text = (await last_assistant.text_content()).strip()
    if raw_text and raw_text != old_text:
        print("  ⚠ Using full assistant message text (plain text response).")
        return raw_text

    raise RuntimeError("Could not extract any response from ChatGPT.")

# ============================================================
# PROCESS ONE COUNTRY
# ============================================================

async def process_country(country: str, output_dir: Path, page, response_handler) -> bool:
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
        raw_response = await response_handler(page, prompt)
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
    parser.add_argument(
    "--profile",
    default="claude",
    help="Browser profile name (folder under browser_profiles). Default: claude"
)
    parser.add_argument(
    "--service",
    default="claude",
    choices=["claude", "chatgpt"],
    help="Which LLM service to use. Default: claude"
)
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

    browser = BrowserManager(service=args.service)   # not just BrowserManager()
    # page = await browser.start()
    profile_dir = str(BASE_PROFILE_DIR / args.profile)
    page = await browser.start(profile_dir=profile_dir)
    succeeded, failed = 0, 0

    # Determine the new‑chat URL and response handler based on service
    if args.service == "claude":
        new_chat_url = "https://claude.ai/new"
        response_handler = get_claude_response_via_copy
        prompt_box_locator = 'div[contenteditable="true"][aria-label="Write your prompt to Claude"]'
    else:  # chatgpt
        new_chat_url = "https://chat.openai.com"
        response_handler = get_chatgpt_response_via_copy
        prompt_box_locator = 'div[contenteditable="true"][aria-label="Chat with ChatGPT"]'

    for country in countries_to_run:
        await browser.goto(new_chat_url)
        print(f"\n{args.service.title()} opened for {country}.")

        prompt_box = page.locator(prompt_box_locator)
        try:
            await prompt_box.wait_for(state="visible", timeout=30000)
        except Exception:
            print(f"\nERROR: {args.service} prompt box was not found. Check login/session.")
            return

        ok = await process_country(country, output_dir, page, response_handler)
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