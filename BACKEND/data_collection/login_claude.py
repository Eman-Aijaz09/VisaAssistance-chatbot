"""
login_claude.py

Opens a Claude.ai browser window with a specific profile so you can
manually log in. The session is then saved automatically for future
automated runs with the same profile name.

Usage examples:
    python login_claude.py
        (uses default profile "claude")

    python login_claude.py --profile claude2
        (uses profile "claude2" – for a second account)

    python login_claude.py --profile claude3 --headless
        (show available options; note: login requires visible browser)
"""

import argparse
import asyncio
from pathlib import Path
from browser_for_data import BrowserManager

BASE_PROFILE_DIR = Path(r"D:\ImmigrationAssistant\browser_profiles")

async def main():
    parser = argparse.ArgumentParser(description="Manual login to Claude.ai with a chosen profile.")
    parser.add_argument(
        "--profile",
        default="claude",
        help="Profile name (folder under browser_profiles). Default: claude"
    )
    args = parser.parse_args()

    profile_dir = str(BASE_PROFILE_DIR / args.profile)
    print(f"Launching browser with profile: {profile_dir}")
    print("A new window will open. Please log into your Claude account.")
    print("After login, you can close the browser (or press Ctrl+C here).")

    browser = BrowserManager()
    page = await browser.start(profile_dir=profile_dir)
    await browser.goto("https://claude.ai/new")

    print("Browser is now open. Log in, then press Ctrl+C to exit gracefully.")
    # Keep the script alive until the user interrupts
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down. The session will be saved for next time.")

    # Optional cleanup (won't delete the profile, just closes Playwright)
    await browser.stop()

if __name__ == "__main__":
    asyncio.run(main())