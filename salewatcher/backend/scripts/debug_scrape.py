#!/usr/bin/env python
"""
Debug script to test Milled scraping with visible browser.

Usage:
    python scripts/debug_scrape.py bath-body-works
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright

USER_DATA_DIR = Path(__file__).parent.parent / ".browser_data"


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/debug_scrape.py <brand-slug>")
        print("Example: python scripts/debug_scrape.py bath-body-works")
        sys.exit(1)

    brand_slug = sys.argv[1]
    brand_url = f"https://milled.com/{brand_slug}"

    print(f"Testing scrape for: {brand_url}")
    print(f"Using browser data from: {USER_DATA_DIR}")
    print(f"Browser data exists: {USER_DATA_DIR.exists()}")

    if USER_DATA_DIR.exists():
        files = list(USER_DATA_DIR.iterdir())
        print(f"Browser data files: {len(files)}")

    async with async_playwright() as p:
        # Use VISIBLE browser to see what's happening
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=False,  # VISIBLE for debugging
            channel="chrome",  # Use real Chrome browser
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

        print(f"\nNavigating to {brand_url}...")
        await page.goto(brand_url, wait_until="networkidle", timeout=60000)

        print(f"Current URL: {page.url}")

        # Check for Cloudflare
        content = await page.content()
        if "challenge" in content.lower() or "cloudflare" in content.lower():
            print("\n⚠️  CLOUDFLARE CHALLENGE DETECTED!")
            print("Please complete the challenge in the browser window...")
            input("Press ENTER after completing the challenge...")

            # Re-check page after challenge
            await page.wait_for_load_state("networkidle")

        # Try to find email links - links that start with /{brand_slug}/ and have content after
        all_brand_links = await page.query_selector_all(f'a[href^="/{brand_slug}/"]')
        email_links = []
        for link in all_brand_links:
            href = await link.get_attribute("href")
            if href and len(href) > len(f"/{brand_slug}/") + 5:
                email_links.append(link)
        print(f"\nFound {len(email_links)} email links with selector 'a[href^=\"/{brand_slug}/\"]'")

        if len(email_links) == 0:
            print("\nTrying alternative selectors...")

            # Try other selectors
            all_links = await page.query_selector_all('a')
            print(f"Total links on page: {len(all_links)}")

            # Look for email-like links
            email_hrefs = []
            for link in all_links[:50]:
                href = await link.get_attribute("href")
                if href and "email" in href.lower():
                    email_hrefs.append(href)

            if email_hrefs:
                print(f"Found links containing 'email': {email_hrefs[:5]}")
            else:
                print("No email-related links found")

            # Print sample of all hrefs to find pattern
            print("\nSample of all link hrefs (first 30):")
            for i, link in enumerate(all_links[:30]):
                href = await link.get_attribute("href")
                if href and href.startswith("/"):
                    print(f"  {href}")

            # Try to find newsletter/promotion links
            print("\nLooking for newsletter article links...")
            article_links = await page.query_selector_all('a[href*="/p/"]')
            print(f"Found {len(article_links)} links with '/p/' pattern")
            for link in article_links[:5]:
                href = await link.get_attribute("href")
                print(f"  {href}")

            # Save screenshot
            screenshot_path = Path(__file__).parent.parent / "debug_screenshot.png"
            await page.screenshot(path=str(screenshot_path))
            print(f"\nScreenshot saved to: {screenshot_path}")
        else:
            print("\n✅ Email links found! Scraping should work.")
            # Print first few email URLs
            for i, link in enumerate(email_links[:5]):
                href = await link.get_attribute("href")
                print(f"  {i+1}. {href}")

        print("\nBrowser will stay open for inspection.")
        print("Press ENTER to close...")
        input()

        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
