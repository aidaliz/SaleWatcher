#!/usr/bin/env python
"""
Manual login script for Milled.com.

Opens a browser window for you to log in manually (including Google OAuth).
After you log in, the session cookies are saved for the scraper to use.

Uses stealth techniques to bypass Cloudflare detection.

Usage:
    python scripts/login_milled.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright

COOKIES_PATH = Path(__file__).parent.parent / "src" / "scraper" / ".cookies.json"
USER_DATA_DIR = Path(__file__).parent.parent / ".browser_data"


async def main():
    print("Opening browser for Milled.com login...")
    print("Please log in with your Google account.")
    print("After logging in successfully, the script will save your session.\n")

    async with async_playwright() as p:
        # Use persistent context with user data dir (more like a real browser)
        # This helps bypass Cloudflare detection
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=False,
            channel="chrome",  # Use real Chrome if installed
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            ignore_default_args=["--enable-automation"],
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        page = context.pages[0] if context.pages else await context.new_page()

        # Navigate to Milled.com
        print("Navigating to Milled.com...")
        await page.goto("https://milled.com/sign-in", wait_until="domcontentloaded")

        print("\n" + "="*60)
        print("INSTRUCTIONS:")
        print("1. Complete the Cloudflare checkbox if it appears")
        print("2. Log in with your Google account")
        print("3. Once you see your account page, press ENTER here")
        print("="*60 + "\n")

        # Wait for user to press Enter
        input("Press ENTER after you've logged in successfully...")

        # Check if logged in
        current_url = page.url
        print(f"\nCurrent URL: {current_url}")

        # Save cookies regardless of URL (user confirmed they logged in)
        await context.storage_state(path=str(COOKIES_PATH))
        print(f"\nSession saved to: {COOKIES_PATH}")
        print("You can now run the scraper!")

        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
