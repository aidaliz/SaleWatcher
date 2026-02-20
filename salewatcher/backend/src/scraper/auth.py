import asyncio
import logging
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# Handle different versions of playwright-stealth
async def stealth_async(page):
    """Apply stealth settings to bypass bot detection."""
    try:
        from playwright_stealth import stealth_async as _stealth
        await _stealth(page)
    except ImportError:
        try:
            from playwright_stealth import Stealth
            stealth = Stealth()
            if hasattr(stealth, 'apply_stealth'):
                await stealth.apply_stealth(page)
            elif callable(stealth):
                await stealth(page)
        except Exception:
            pass  # Continue without stealth

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

        # Launch browser with headless mode (required for Railway/Docker)
        browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )

        # Load saved cookies if they exist (session persistence via file)
        if COOKIES_PATH.exists():
            logger.info("Loading saved Milled session from cookies...")
            try:
                import json as _json
                with open(COOKIES_PATH) as f:
                    storage_state = _json.load(f)
                self.context = await browser.new_context(
                    storage_state=storage_state,
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
            except Exception as e:
                logger.warning(f"Failed to load saved session: {e}. Starting fresh login.")
                self.context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
        else:
            logger.info("No saved session — will login with credentials.")
            self.context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )

        self.page = await self.context.new_page()

        # Apply stealth to bypass bot detection
        await stealth_async(self.page)

        # Attempt login with credentials (best-effort — brand pages are public anyway)
        if not COOKIES_PATH.exists():
            await self._login()

    async def _login(self) -> None:
        """Perform login to Milled.com (best-effort — brand pages are public)."""
        logger.info("Attempting Milled.com login...")

        if not settings.effective_milled_email or not settings.milled_password:
            logger.warning("No Milled credentials set — proceeding without login (public pages only).")
            return

        try:
            await self.page.goto("https://milled.com/sign-in", wait_until="domcontentloaded", timeout=20000)

            await self.page.fill('input[name="email"]', settings.effective_milled_email, timeout=10000)
            await self.page.fill('input[name="password"]', settings.milled_password, timeout=5000)
            await self.page.click('button[type="submit"]')

            try:
                await self.page.wait_for_url("**/account**", timeout=10000)
                logger.info("Milled login successful — session saved.")
                await self.context.storage_state(path=str(COOKIES_PATH))
            except Exception:
                logger.warning("Login redirect not detected — may still be authenticated. Continuing.")

        except Exception as e:
            logger.warning(f"Milled login failed ({e}) — will scrape public pages without auth.")

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
