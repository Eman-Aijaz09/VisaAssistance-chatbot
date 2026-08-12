"""
login_chatgpt.py

Opens a ChatGPT browser window with a specific profile so you can
manually log in. The session is then saved automatically for future
automated runs with the same profile name.

Usage:
    python login_chatgpt.py                  # default profile "chatgpt"
    python login_chatgpt.py --profile chatgpt2  # second account
    python login_chatgpt.py --profile chatgpt3  # third account
"""

import argparse
import asyncio
from pathlib import Path
from browser_for_data import BrowserManager

BASE_PROFILE_DIR = Path(r"D:\ImmigrationAssistant\browser_profiles")

async def main():
    parser = argparse.ArgumentParser(description="Manual login to ChatGPT with a chosen profile.")
    parser.add_argument(
        "--profile",
        default="chatgpt",
        help="Profile name (folder under browser_profiles). Default: chatgpt"
    )
    args = parser.parse_args()

    profile_dir = str(BASE_PROFILE_DIR / args.profile)
    print(f"Launching browser with profile: {profile_dir}")
    print("A new window will open. Please log into your ChatGPT account.")
    print("After login, you can close the browser (or press Ctrl+C here).")

    # Use the ChatGPT service
    browser = BrowserManager(service="chatgpt")
    page = await browser.start(profile_dir=profile_dir)
    await browser.goto("https://chat.openai.com")

    print("Browser is now open. Log in, then press Ctrl+C to exit gracefully.")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down. The session will be saved for next time.")

    await browser.stop()

if __name__ == "__main__":
    asyncio.run(main())