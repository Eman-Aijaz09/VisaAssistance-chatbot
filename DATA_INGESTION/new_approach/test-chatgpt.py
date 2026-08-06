# import asyncio

# from crawler.browser import BrowserManager


# async def main():

#     browser = BrowserManager()

#     page = await browser.start()

#     # Open ChatGPT
#     await browser.goto("https://chatgpt.com")

#     print("Waiting for ChatGPT to load...")

#     # Wait until the prompt box exists
#     await page.wait_for_selector("div[contenteditable='true']", timeout=120000)

#     prompt = """
# What is the capital of Germany?
# Reply in one sentence only.
# """

#     textbox = page.locator("div[contenteditable='true']").last

#     await textbox.click()

#     await textbox.fill(prompt)

#     # Press Enter
#     await textbox.press("Enter")

#     print("Prompt sent.")

#     # Wait until assistant finishes generating
#     await page.wait_for_timeout(12000)

#     responses = await page.locator("article").all_inner_texts()

#     print("\n====================")
#     print("LAST RESPONSE")
#     print("====================\n")

#     print(responses[-1])


# if __name__ == "__main__":
#     asyncio.run(main())

import asyncio
from DATA_INGESTION.new_approach.crawler.browser import BrowserManager


async def main():

    browser = BrowserManager()

    page = await browser.start()

    # Open ChatGPT
    await browser.goto("https://chatgpt.com")

    print("ChatGPT opened.")

    # Wait until the prompt input appears
    await page.wait_for_selector(
        "div[contenteditable='true']",
        timeout=60000,
    )

    print("Prompt box found.")

    prompt = "reply with only: hi hackers!."

    # Focus prompt box
    await page.locator(
        "div[contenteditable='true']"
    ).last.click()

    # Type prompt
    await page.keyboard.type(prompt)

    print("Prompt typed.")

    # Send
    await page.keyboard.press("Enter")

    print("Prompt sent.")

    # Keep browser open for inspection
    await page.wait_for_timeout(30000)


asyncio.run(main())