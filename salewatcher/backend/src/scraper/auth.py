import asyncio
import logging
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright_stealth import stealth_async

from src.config import settings

logger = logging.getLogger(__name__)

# Path to store session cookies
COOKIES_PATH = Path(__file__).parent / ".cookies.json"
USER_DATA_DIR = Path(__file__).parent.parent.parent / ".browser_data"


class MilledAuth:
    """Handles Milled.com authentication with session persistence."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def setup(self) -> None:
        """Initialize browser and authenticate."""
        self.playwright = await async_playwright().start()

        # Check if we have existing browser data from manual login
        has_session = USER_DATA_DIR.exists() and any(USER_DATA_DIR.iterdir())

        if has_session:
            logger.info("Using existing browser session from manual login...")
        else:
            logger.warning("No existing session found. Run 'python scripts/login_milled.py' first.")

        # Use persistent context with stealth settings to avoid Cloudflare
        # The user_data_dir stores cookies/session from the manual login
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            ignore_default_args=["--enable-automation"],
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

        # Apply stealth to bypass bot detection
        await stealth_async(self.page)

        # Skip login check if we have existing session data - just try to use it
        if not has_session:
            await self._login()

    async def _login(self) -> None:
        """Perform login to Milled.com."""
        logger.info("Logging in to Milled.com...")

        # Check if we should use manual login (no credentials set)
        if not settings.milled_email or not settings.milled_password:
            raise ValueError(
                "No session found and no credentials set.\n"
                "Please run 'python scripts/login_milled.py' first to log in manually,\n"
                "or set MILLED_EMAIL and MILLED_PASSWORD in your .env file."
            )

        await self.page.goto("https://milled.com/sign-in", wait_until="networkidle")

        # Fill login form
        await self.page.fill('input[name="email"]', settings.milled_email)
        await self.page.fill('input[name="password"]', settings.milled_password)

        # Submit
        await self.page.click('button[type="submit"]')

        # Wait for navigation
        try:
            await self.page.wait_for_url("**/account**", timeout=10000)
            logger.info("Login successful")

            # Save session
            await self.context.storage_state(path=str(COOKIES_PATH))
            logger.info("Session saved")
        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise RuntimeError(
                "Failed to login to Milled.com.\n"
                "If using Google OAuth, run 'python scripts/login_milled.py' instead."
            )

    async def get_page(self) -> Page:
        """Get authenticated page for scraping."""
        if not self.page:
            raise RuntimeError("Auth not initialized. Use 'async with MilledAuth():'")
        return self.page

    async def close(self) -> None:
        """Close browser and save session."""
        if self.context:
            try:
                await self.context.storage_state(path=str(COOKIES_PATH))
            except:
                pass
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
