import asyncio
import logging
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from src.config import settings

logger = logging.getLogger(__name__)

# Path to store session cookies
COOKIES_PATH = Path(__file__).parent / ".cookies.json"


class MilledAuth:
    """Handles Milled.com authentication with session persistence."""

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def setup(self) -> None:
        """Initialize browser and authenticate."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)

        # Try to load existing session
        if COOKIES_PATH.exists():
            logger.info("Loading existing session...")
            self.context = await self.browser.new_context(
                storage_state=str(COOKIES_PATH)
            )
        else:
            self.context = await self.browser.new_context()

        self.page = await self.context.new_page()

        # Check if we're logged in
        if not await self._is_logged_in():
            await self._login()

    async def _is_logged_in(self) -> bool:
        """Check if current session is authenticated."""
        await self.page.goto("https://milled.com/account", wait_until="networkidle")

        # If we're redirected to login, we're not authenticated
        if "/sign-in" in self.page.url or "/login" in self.page.url:
            return False

        # Check for account page elements
        try:
            await self.page.wait_for_selector("text=Account Settings", timeout=3000)
            logger.info("Already logged in")
            return True
        except:
            return False

    async def _login(self) -> None:
        """Perform login to Milled.com."""
        logger.info("Logging in to Milled.com...")

        # Check if we should use manual login (no credentials set)
        if not settings.milled_email or not settings.milled_password:
            raise ValueError(
                "Not logged in and no credentials set.\n"
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
        if self.browser:
            await self.browser.close()
