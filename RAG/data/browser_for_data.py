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

    # async def start(self):
    #     # Launch SeleniumBase browser
    #     self.driver = await cdp_driver.start_async()

    #     # Connect Playwright
    #     endpoint = self.driver.get_endpoint_url()

    #     self.playwright = await async_playwright().start()

    #     self.browser = await self.playwright.chromium.connect_over_cdp(
    #         endpoint
    #     )

    #     self.context = self.browser.contexts[0]
    #     self.page = self.context.pages[0]

    #     return self.page
    async def start(self):
        profile_dir = r"D:\ImmigrationAssistant\browser_profiles\claude"

        # Launch SeleniumBase browser with persistent profile
        self.driver = await cdp_driver.start_async(
            user_data_dir=profile_dir
        )

        # Connect Playwright through CDP
        endpoint = self.driver.get_endpoint_url()

        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.connect_over_cdp(
            endpoint
        )

        self.context = self.browser.contexts[0]

        await self.context.grant_permissions(['clipboard-read', 'clipboard-write'], origin="https://claude.ai")

        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()

        return self.page

    # async def goto(self, url):

    #     self.context = self.browser.contexts[0]
    #     self.page = self.context.pages[-1]

    #     print(f"\nNavigating to: {url}")
    #     print(f"Contexts: {len(self.browser.contexts)}")
    #     print(f"Pages: {len(self.context.pages)}")

    #     response = await self.page.goto(
    #         url,
    #         wait_until="networkidle",
    #         timeout=60000,
    #     )

    #     await self.page.wait_for_timeout(3000)

    #     return response

    async def goto(self, url):
        self.context = self.browser.contexts[0]
        self.page = self.context.pages[-1]

        print(f"\nNavigating to: {url}")
        print(f"Contexts: {len(self.browser.contexts)}")
        print(f"Pages: {len(self.context.pages)}")

        # Use domcontentloaded instead of networkidle
        response = await self.page.goto(
            url,
            wait_until="domcontentloaded",   # <-- changed here
            timeout=60000,
        )

        # Wait a bit extra for dynamic content to start loading
        await self.page.wait_for_timeout(5000)   # increased to 5s for safety
        return response
    
    async def stop(self):
        if self.playwright:
            await self.playwright.stop()

        if self.driver:
            await self.driver.sleep(1)