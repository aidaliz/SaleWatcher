#!/usr/bin/env python
"""
Manual login script for Milled.com.

Opens a browser window for you to log in manually (including Google OAuth).
After you log in, the session cookies are saved for the scraper to use.

Usage:
    python scripts/login_milled.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright

COOKIES_PATH = Path(__file__).parent.parent / "src" / "scraper" / ".cookies.json"


async def main():
    print("Opening browser for Milled.com login...")
    print("Please log in with your Google account.")
    print("After logging in successfully, close the browser window.\n")

    async with async_playwright() as p:
        # Launch visible browser
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Go to Milled.com login page
        await page.goto("https://milled.com/sign-in")

        print("Waiting for you to log in...")
        print("(The script will detect when you reach the account page)\n")

        # Wait for successful login (user lands on account or home page)
        try:
            # Wait up to 5 minutes for login
            await page.wait_for_url(
                lambda url: "/account" in url or url == "https://milled.com/",
                timeout=300000
            )
            print("Login detected! Saving session...")

            # Save cookies
            await context.storage_state(path=str(COOKIES_PATH))
            print(f"\nSession saved to: {COOKIES_PATH}")
            print("You can now run the scraper!")

        except Exception as e:
            print(f"\nLogin timed out or failed: {e}")
            print("Please try again.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
