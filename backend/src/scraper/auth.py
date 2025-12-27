"""Milled.com authentication and session management."""

import json
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config.settings import get_settings

# Session storage path
SESSION_FILE = Path(".milled_session.json")


class MilledAuthError(Exception):
    """Raised when authentication to Milled.com fails."""
    pass


class MilledClient:
    """Client for interacting with Milled.com."""

    def __init__(self):
        self.settings = get_settings()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._playwright = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start(self):
        """Start the browser and authenticate."""
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(
            headless=True,
        )

        # Try to restore session
        if SESSION_FILE.exists():
            try:
                storage_state = json.loads(SESSION_FILE.read_text())
                self.context = await self.browser.new_context(
                    storage_state=storage_state,
                )
                self.page = await self.context.new_page()

                # Verify session is still valid
                if await self._is_logged_in():
                    return
            except Exception:
                pass  # Session invalid, will re-authenticate

        # Create fresh context and authenticate
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()
        await self._authenticate()

    async def close(self):
        """Close the browser and save session."""
        if self.context:
            # Save session for reuse
            try:
                storage_state = await self.context.storage_state()
                SESSION_FILE.write_text(json.dumps(storage_state))
            except Exception:
                pass

        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _is_logged_in(self) -> bool:
        """Check if currently logged in to Milled.com."""
        try:
            await self.page.goto("https://milled.com/account", wait_until="networkidle")
            # If we can access account page without redirect, we're logged in
            return "account" in self.page.url and "login" not in self.page.url
        except Exception:
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10),
        retry=retry_if_exception_type((TimeoutError,)),
    )
    async def _authenticate(self):
        """Authenticate to Milled.com."""
        if not self.settings.milled_email or not self.settings.milled_password:
            raise MilledAuthError("Milled.com credentials not configured")

        # Navigate to login page
        await self.page.goto("https://milled.com/login", wait_until="networkidle")

        # Fill in credentials
        await self.page.fill('input[name="email"]', self.settings.milled_email)
        await self.page.fill('input[name="password"]', self.settings.milled_password)

        # Submit form
        await self.page.click('button[type="submit"]')

        # Wait for navigation
        await self.page.wait_for_load_state("networkidle")

        # Verify login succeeded
        if "login" in self.page.url.lower():
            # Check for error message
            error = await self.page.query_selector(".error, .alert-danger, [class*='error']")
            if error:
                error_text = await error.text_content()
                raise MilledAuthError(f"Login failed: {error_text}")
            raise MilledAuthError("Login failed: still on login page")

        # Verify we can access account
        if not await self._is_logged_in():
            raise MilledAuthError("Login appeared to succeed but session is invalid")

    async def ensure_authenticated(self):
        """Ensure we have a valid authenticated session."""
        if not await self._is_logged_in():
            await self._authenticate()
