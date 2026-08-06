# import asyncio

# from seleniumbase import cdp_driver
# from playwright.async_api import async_playwright


# class BrowserManager:
#     """
#     Starts a SeleniumBase stealth browser and connects
#     Playwright to it through Chrome DevTools Protocol (CDP).
#     """

#     def __init__(self):
#         self.driver = None
#         self.playwright = None
#         self.browser = None
#         self.context = None
#         self.page = None

#     async def start(self):
#         # Start SeleniumBase browser
#         self.driver = await cdp_driver.start_async()

#         # CDP endpoint exposed by Chrome
#         endpoint = self.driver.get_endpoint_url()

#         # Start Playwright
#         self.playwright = await async_playwright().start()

#         # Connect Playwright to existing Chrome
#         self.browser = await self.playwright.chromium.connect_over_cdp(endpoint)

#         self.context = self.browser.contexts[0]
#         self.page = self.context.pages[0]

#         return self.page

#     async def stop(self):
#         if self.playwright:
#             await self.playwright.stop()

#         if self.driver:
#             await self.driver.sleep(1)

from seleniumbase import cdp_driver
from playwright.async_api import async_playwright


class BrowserManager:
    """
    Starts a SeleniumBase stealth browser and exposes
    a Playwright page connected through CDP.
    """

    def __init__(self):
        self.driver = None
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def start(self):
        # Launch SeleniumBase browser
        self.driver = await cdp_driver.start_async()

        # Connect Playwright
        endpoint = self.driver.get_endpoint_url()

        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.connect_over_cdp(
            endpoint
        )

        self.context = self.browser.contexts[0]
        self.page = self.context.pages[0]

        return self.page

    async def goto(self, url):

        self.context = self.browser.contexts[0]
        self.page = self.context.pages[-1]

        print(f"\nNavigating to: {url}")
        print(f"Contexts: {len(self.browser.contexts)}")
        print(f"Pages: {len(self.context.pages)}")

        response = await self.page.goto(
            url,
            wait_until="networkidle",
            timeout=60000,
        )

        await self.page.wait_for_timeout(3000)

        return response
    async def stop(self):
        if self.playwright:
            await self.playwright.stop()

        if self.driver:
            await self.driver.sleep(1)