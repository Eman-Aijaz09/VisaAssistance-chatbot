from seleniumbase import cdp_driver
from playwright.async_api import async_playwright

class BrowserManager:
    """
    Starts a SeleniumBase stealth browser and exposes
    a Playwright page connected through CDP.

    Usage:
        # Claude
        browser = BrowserManager(service="claude")
        page = await browser.start()

        # ChatGPT
        browser = BrowserManager(service="chatgpt")
        page = await browser.start()
    """

    # ------------------------------------------------------------------
    # Default profile folders and clipboard origins for each service
    # ------------------------------------------------------------------
    SERVICE_CONFIG = {
        "claude": {
            "default_profile": r"D:\ImmigrationAssistant\browser_profiles\claude",
            "clipboard_origin": "https://claude.ai",
        },
        "chatgpt": {
            "default_profile": r"D:\ImmigrationAssistant\browser_profiles\chatgpt",
            "clipboard_origin": "https://chat.openai.com",
        },
    }

    def __init__(self, service: str = "claude"):
        """
        service : 'claude' or 'chatgpt'
        """
        if service not in self.SERVICE_CONFIG:
            raise ValueError(f"Unknown service: {service}. Choose 'claude' or 'chatgpt'.")
        self.service = service
        self.driver = None
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def start(self, profile_dir: str = None):
        config = self.SERVICE_CONFIG[self.service]

        if profile_dir is None:
            profile_dir = config["default_profile"]

        # Launch SeleniumBase browser with persistent profile
        self.driver = await cdp_driver.start_async(user_data_dir=profile_dir)

        # Connect Playwright through CDP
        endpoint = self.driver.get_endpoint_url()
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.connect_over_cdp(endpoint)

        self.context = self.browser.contexts[0]

        # Grant clipboard permissions for the appropriate origin
        await self.context.grant_permissions(
            ["clipboard-read", "clipboard-write"],
            origin=config["clipboard_origin"],
        )

        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()

        return self.page

    async def goto(self, url):
        self.context = self.browser.contexts[0]
        self.page = self.context.pages[-1]

        print(f"\nNavigating to: {url}")
        print(f"Contexts: {len(self.browser.contexts)}")
        print(f"Pages: {len(self.context.pages)}")

        response = await self.page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000,
        )
        await self.page.wait_for_timeout(5000)
        return response

    async def stop(self):
        if self.playwright:
            await self.playwright.stop()
        if self.driver:
            await self.driver.sleep(1)

# class BrowserManager:
#     """
#     Starts a SeleniumBase stealth browser and exposes
#     a Playwright page connected through CDP.
#     """

#     def __init__(self):
#         self.driver = None
#         self.playwright = None
#         self.browser = None
#         self.context = None
#         self.page = None

#     # async def start(self):
#         # profile_dir = r"D:\ImmigrationAssistant\browser_profiles\claude"

#         # # Launch SeleniumBase browser with persistent profile
#         # self.driver = await cdp_driver.start_async(
#         #     user_data_dir=profile_dir
#         # )
#     async def start(self, profile_dir: str = None):
#         if profile_dir is None:
#             profile_dir = r"D:\ImmigrationAssistant\browser_profiles\claude"
#         self.driver = await cdp_driver.start_async(user_data_dir=profile_dir)
        

#         # Connect Playwright through CDP
#         endpoint = self.driver.get_endpoint_url()

#         self.playwright = await async_playwright().start()

#         self.browser = await self.playwright.chromium.connect_over_cdp(
#             endpoint
#         )

#         self.context = self.browser.contexts[0]

#         await self.context.grant_permissions(['clipboard-read', 'clipboard-write'], origin="https://claude.ai")

#         if self.context.pages:
#             self.page = self.context.pages[0]
#         else:
#             self.page = await self.context.new_page()

#         return self.page

#     async def goto(self, url):
#         self.context = self.browser.contexts[0]
#         self.page = self.context.pages[-1]

#         print(f"\nNavigating to: {url}")
#         print(f"Contexts: {len(self.browser.contexts)}")
#         print(f"Pages: {len(self.context.pages)}")

#         # Use domcontentloaded instead of networkidle
#         response = await self.page.goto(
#             url,
#             wait_until="domcontentloaded",   # <-- changed here
#             timeout=60000,
#         )
#         # Wait a bit extra for dynamic content to start loading
#         await self.page.wait_for_timeout(5000)   # increased to 5s for safety
#         return response
    
#     async def stop(self):
#         if self.playwright:
#             await self.playwright.stop()

#         if self.driver:
#             await self.driver.sleep(1)