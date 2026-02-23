"""
SalesGazer client for fetching retail promotional emails.

Uses httpx with cookie-based session auth, rate limiting (1 req/sec),
and retry logic (3 attempts).

The settings page (/mailbox/settings/) is JavaScript-rendered, so
find_store_ids() uses Playwright (headless Chromium) for that single
page while keeping all other requests on httpx.
"""
import asyncio
import logging
import re
from typing import Optional

import httpx
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://salesgazer.com"


class SalesGazerClient:
    """Async HTTP client for SalesGazer with session auth."""

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._csrf_token: Optional[str] = None
        self._logged_in: bool = False
        self._last_request_at: float = 0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=BASE_URL,
                follow_redirects=True,
                timeout=httpx.Timeout(30.0),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                },
            )
        return self._client

    async def _rate_limit(self) -> None:
        """Enforce 1 request per second."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_at
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        self._last_request_at = asyncio.get_event_loop().time()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _get(self, path: str) -> httpx.Response:
        """Rate-limited GET with retry."""
        await self._rate_limit()
        client = await self._get_client()
        resp = await client.get(path)
        resp.raise_for_status()
        return resp

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _post(self, path: str, data: dict) -> httpx.Response:
        """Rate-limited POST with retry."""
        await self._rate_limit()
        client = await self._get_client()
        resp = await client.post(
            path,
            data=data,
            headers={"Referer": f"{BASE_URL}{path}"},
        )
        resp.raise_for_status()
        return resp

    def _extract_csrf(self, html: str) -> str:
        """Parse csrfmiddlewaretoken from an HTML form."""
        match = re.search(
            r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)["\']',
            html,
        )
        if not match:
            raise ValueError("Could not find CSRF token in page")
        return match.group(1)

    async def login(self) -> bool:
        """
        Authenticate with SalesGazer using credentials from env.

        Returns True on success, raises on failure.
        """
        email = settings.salesgazer_email
        password = settings.salesgazer_password
        if not email or not password:
            raise ValueError("SALESGAZER_EMAIL and SALESGAZER_PASSWORD must be set")

        # Step 1: GET login page to obtain CSRF token
        resp = await self._get("/customer/login/")
        self._csrf_token = self._extract_csrf(resp.text)

        # Step 2: POST credentials
        client = await self._get_client()
        await self._rate_limit()
        login_resp = await client.post(
            "/customer/login/",
            data={
                "csrfmiddlewaretoken": self._csrf_token,
                "username": email,
                "password": password,
                "remember": "on",
            },
            headers={"Referer": f"{BASE_URL}/customer/login/"},
        )

        # Success = redirect to /mailbox/ (follows automatically)
        if "/mailbox/" in str(login_resp.url):
            self._logged_in = True
            logger.info("SalesGazer login successful")
            return True

        # Check if we landed on mailbox page content
        if "mailbox" in login_resp.text.lower() and login_resp.status_code == 200:
            self._logged_in = True
            logger.info("SalesGazer login successful")
            return True

        raise ConnectionError(
            f"SalesGazer login failed — landed on {login_resp.url} "
            f"(status {login_resp.status_code})"
        )

    async def _find_store_ids_with_playwright(self, domain: str) -> list[dict]:
        """
        Use Playwright (headless Chromium) to load the JS-rendered
        /mailbox/settings/ page and extract store rows matching *domain*.

        Strategy: use the proven httpx login first, then transfer session
        cookies into Playwright so we don't re-implement auth in the browser.

        Returns list of dicts: [{store_id, domain, is_subscribed}]
        """
        # Ensure httpx session is logged in first (proven to work)
        if not self._logged_in:
            await self.login()

        # Collect cookies from the httpx client to pass to Playwright
        httpx_client = await self._get_client()
        httpx_cookies = [
            {
                "name": c.name,
                "value": c.value,
                # Strip leading dot — Playwright requires clean domain (not .salesgazer.com)
                "domain": (c.domain or "salesgazer.com").lstrip("."),
                "path": c.path or "/",
            }
            for c in httpx_client.cookies.jar
        ]

        results: list[dict] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            # Inject the httpx session cookies so Playwright is already logged in
            if httpx_cookies:
                await context.add_cookies(httpx_cookies)
                logger.info(f"Injected {len(httpx_cookies)} cookies from httpx session into Playwright")

            page = await context.new_page()
            await stealth_async(page)

            try:
                # ── Settings page ──────────────────────────────────────
                await page.goto(
                    f"{BASE_URL}/mailbox/settings/", wait_until="domcontentloaded"
                )

                # If redirected to login, cookies didn't work — fall back to form login
                if "/login" in page.url or "/customer" in page.url:
                    logger.warning("Cookie injection didn't keep session — falling back to form login")
                    email = settings.salesgazer_email
                    password = settings.salesgazer_password
                    await page.fill('input[name="username"]', email)
                    await page.fill('input[name="password"]', password)
                    await page.locator('button[type="submit"], input[type="submit"]').first.click()
                    await page.wait_for_load_state("domcontentloaded", timeout=20000)
                    if "/mailbox" not in page.url:
                        logger.error(f"Playwright fallback login failed — url={page.url}")
                        return results
                    await page.goto(f"{BASE_URL}/mailbox/settings/", wait_until="domcontentloaded")

                logger.info(f"On settings page, url={page.url}")

                # Try to use the search/filter input to narrow rows before waiting
                try:
                    search_input = await page.query_selector(
                        'input[type="search"], input[name="search"], input[placeholder*="search" i], input[placeholder*="filter" i]'
                    )
                    if search_input:
                        await search_input.fill(domain)
                        await page.wait_for_timeout(1500)
                        logger.info(f"Used settings search filter for '{domain}'")
                except Exception:
                    pass

                # Wait for JS-rendered store rows (up to 30s — large page)
                try:
                    await page.wait_for_selector("tr[store-id]", timeout=30000)
                except Exception:
                    # Log page HTML snippet to help diagnose selector mismatch
                    try:
                        html_snippet = await page.content()
                        logger.warning(
                            f"No tr[store-id] found on settings page (url={page.url}). "
                            f"HTML snippet (first 3000 chars): {html_snippet[:3000]}"
                        )
                    except Exception:
                        logger.warning(
                            "No tr[store-id] elements found — page may not have rendered"
                        )
                    return results

                # ── Extract rows ───────────────────────────────────────
                rows = await page.query_selector_all("tr[store-id]")
                logger.info(f"Found {len(rows)} tr[store-id] rows on settings page")
                for row in rows:
                    store_id = await row.get_attribute("store-id")
                    if not store_id:
                        continue

                    tds = await row.query_selector_all("td")
                    if len(tds) < 4:
                        continue

                    row_domain = (await tds[3].inner_text()).strip().lower()

                    # Subscription checkbox (handle both spellings of the name)
                    checkbox = await row.query_selector(
                        'input[name="user_subscription"], '
                        'input[name="user_susbcription"]'
                    )
                    is_subscribed = bool(checkbox and await checkbox.is_checked())

                    if domain.lower() in row_domain or row_domain in domain.lower():
                        results.append(
                            {
                                "store_id": store_id,
                                "domain": row_domain,
                                "is_subscribed": is_subscribed,
                            }
                        )

                # ── Sync any new cookies back to httpx ─────────────────
                try:
                    csrf_input = await page.query_selector(
                        'input[name="csrfmiddlewaretoken"]'
                    )
                    if csrf_input:
                        self._csrf_token = await csrf_input.get_attribute("value")
                except Exception:
                    pass

                pw_cookies = await context.cookies()
                client = await self._get_client()
                for cookie in pw_cookies:
                    client.cookies.set(cookie["name"], cookie["value"])

            finally:
                await browser.close()

        logger.info(
            f"Playwright: found {len(results)} stores matching '{domain}'"
        )
        return results

    async def find_store_ids(self, domain: str) -> list[dict]:
        """
        Search the settings page for stores matching a domain.

        The /mailbox/settings/ page is JavaScript-rendered, so this
        method delegates to _find_store_ids_with_playwright() which
        launches a headless Chromium browser to obtain the real DOM.

        Returns list of dicts: [{store_id, domain, is_subscribed}]
        """
        results = await self._find_store_ids_with_playwright(domain)

        # Playwright handled the full login flow; mark session as active
        # so subsequent httpx calls skip the login step.
        if not self._logged_in and results is not None:
            self._logged_in = True

        return results

    async def subscribe_to_store(self, store_id: str) -> bool:
        """
        Subscribe to a store by toggling the subscription.

        Returns True on success.
        """
        if not self._logged_in:
            await self.login()

        # Ensure we have a fresh CSRF token
        if not self._csrf_token:
            resp = await self._get("/mailbox/settings/")
            self._csrf_token = self._extract_csrf(resp.text)

        client = await self._get_client()
        await self._rate_limit()
        resp = await client.post(
            f"/mailing_core/user_subscribe_store/{store_id}/",
            data={"csrfmiddlewaretoken": self._csrf_token},
            headers={
                "Referer": f"{BASE_URL}/mailbox/settings/",
                "X-CSRFToken": self._csrf_token,
                "X-Requested-With": "XMLHttpRequest",
            },
        )

        if resp.status_code in (200, 201, 204, 302):
            logger.info(f"Subscribed to store {store_id}")
            return True

        logger.warning(
            f"Subscribe to store {store_id} returned status {resp.status_code}"
        )
        return False

    async def get_store_email_ids(
        self, store_id: str, max_pages: int = 50
    ) -> list[str]:
        """
        Paginate store inbox to collect all email IDs.

        Returns list of email ID strings.
        """
        if not self._logged_in:
            await self.login()

        email_ids: list[str] = []
        email_pattern = re.compile(r'/mailbox/mail_content/(\d+)/inbox/')

        for page in range(1, max_pages + 1):
            url = f"/mailbox/store_inbox/{store_id}/"
            if page > 1:
                url += f"?page={page}"

            resp = await self._get(url)
            found = email_pattern.findall(resp.text)

            if not found:
                logger.info(
                    f"Store {store_id}: page {page} returned 0 emails, stopping"
                )
                break

            email_ids.extend(found)
            logger.debug(
                f"Store {store_id}: page {page} — {len(found)} emails"
            )

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for eid in email_ids:
            if eid not in seen:
                seen.add(eid)
                unique.append(eid)

        logger.info(f"Store {store_id}: found {len(unique)} unique emails")
        return unique

    async def get_email_html(self, email_id: str) -> str:
        """
        Fetch the full HTML content of a single email.

        Returns the raw HTML string.
        """
        if not self._logged_in:
            await self.login()

        resp = await self._get(f"/mailbox/mail_content/{email_id}/inbox/")
        return resp.text

    async def get_all_store_emails(
        self, store_id: str, max_pages: int = 50
    ) -> list[dict]:
        """
        Fetch all emails for a store: IDs + full HTML content.

        Returns list of dicts: [{email_id, html}]
        """
        email_ids = await self.get_store_email_ids(store_id, max_pages)

        emails: list[dict] = []
        for i, eid in enumerate(email_ids, 1):
            html = await self.get_email_html(eid)
            emails.append({"email_id": eid, "html": html})
            if i % 25 == 0:
                logger.info(f"Fetched {i}/{len(email_ids)} emails for store {store_id}")

        logger.info(f"Fetched all {len(emails)} emails for store {store_id}")
        return emails

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            self._logged_in = False

    async def __aenter__(self) -> "SalesGazerClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()
