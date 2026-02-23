"""
Unit tests for SalesGazerClient.find_store_ids() Playwright integration.

All Playwright internals are mocked so no real browser is launched.
playwright_stealth.stealth_async is also patched out.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.salesgazer.client import SalesGazerClient


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_row(store_id: str, domain_text: str, is_checked: bool = False) -> AsyncMock:
    """Return a mock Playwright ElementHandle for a single <tr store-id=...> row."""
    checkbox = AsyncMock()
    checkbox.is_checked = AsyncMock(return_value=is_checked)

    tds = []
    for text in ["1", "Store Name", "Category", domain_text]:
        td = AsyncMock()
        td.inner_text = AsyncMock(return_value=text)
        tds.append(td)

    row = AsyncMock()
    row.get_attribute = AsyncMock(return_value=store_id)
    row.query_selector_all = AsyncMock(return_value=tds)
    row.query_selector = AsyncMock(return_value=checkbox)
    return row


def _build_playwright_mock(rows: list, *, login_url_pattern: str = "**/mailbox/**"):
    """
    Build a complete mock async_playwright() context manager that
    presents *rows* on the settings page.

    Returns (mock_async_playwright, mock_page) so callers can inspect
    page calls if needed.
    """
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.fill = AsyncMock()
    mock_page.click = AsyncMock()
    mock_page.wait_for_url = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.query_selector_all = AsyncMock(return_value=rows)
    mock_page.query_selector = AsyncMock(return_value=None)  # no csrf input

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.cookies = AsyncMock(return_value=[])

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()

    mock_chromium = AsyncMock()
    mock_chromium.launch = AsyncMock(return_value=mock_browser)

    mock_pw = AsyncMock()
    mock_pw.chromium = mock_chromium
    mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
    mock_pw.__aexit__ = AsyncMock(return_value=False)

    mock_async_playwright = MagicMock(return_value=mock_pw)

    return mock_async_playwright, mock_page


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    return SalesGazerClient()


# ─── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_find_store_ids_returns_matching_store(client, monkeypatch):
    """find_store_ids() returns stores whose domain matches the query."""
    monkeypatch.setattr(
        "src.salesgazer.client.settings.salesgazer_email", "test@example.com"
    )
    monkeypatch.setattr(
        "src.salesgazer.client.settings.salesgazer_password", "s3cr3t"
    )

    row = _make_row("123", "example.com", is_checked=True)
    mock_async_playwright, _ = _build_playwright_mock([row])

    with patch("src.salesgazer.client.async_playwright", mock_async_playwright):
        with patch("src.salesgazer.client.stealth_async", AsyncMock()):
            results = await client.find_store_ids("example.com")

    assert len(results) == 1
    assert results[0] == {
        "store_id": "123",
        "domain": "example.com",
        "is_subscribed": True,
    }
    # Side-effect: client should now be marked as logged in
    assert client._logged_in is True


@pytest.mark.asyncio
async def test_find_store_ids_partial_domain_match(client, monkeypatch):
    """A partial domain match (subdomain or prefix) is accepted."""
    monkeypatch.setattr(
        "src.salesgazer.client.settings.salesgazer_email", "test@example.com"
    )
    monkeypatch.setattr(
        "src.salesgazer.client.settings.salesgazer_password", "s3cr3t"
    )

    # store domain "shop.acme.com" contains query "acme.com"
    row = _make_row("999", "shop.acme.com", is_checked=False)
    mock_async_playwright, _ = _build_playwright_mock([row])

    with patch("src.salesgazer.client.async_playwright", mock_async_playwright):
        with patch("src.salesgazer.client.stealth_async", AsyncMock()):
            results = await client.find_store_ids("acme.com")

    assert len(results) == 1
    assert results[0]["store_id"] == "999"
    assert results[0]["is_subscribed"] is False


@pytest.mark.asyncio
async def test_find_store_ids_no_match_returns_empty(client, monkeypatch):
    """find_store_ids() returns [] when no rows match the domain."""
    monkeypatch.setattr(
        "src.salesgazer.client.settings.salesgazer_email", "test@example.com"
    )
    monkeypatch.setattr(
        "src.salesgazer.client.settings.salesgazer_password", "s3cr3t"
    )

    row = _make_row("456", "otherdomain.com", is_checked=False)
    mock_async_playwright, _ = _build_playwright_mock([row])

    with patch("src.salesgazer.client.async_playwright", mock_async_playwright):
        with patch("src.salesgazer.client.stealth_async", AsyncMock()):
            results = await client.find_store_ids("example.com")

    assert results == []


@pytest.mark.asyncio
async def test_find_store_ids_multiple_rows_filters_correctly(client, monkeypatch):
    """With multiple rows, only matching rows are returned."""
    monkeypatch.setattr(
        "src.salesgazer.client.settings.salesgazer_email", "test@example.com"
    )
    monkeypatch.setattr(
        "src.salesgazer.client.settings.salesgazer_password", "s3cr3t"
    )

    rows = [
        _make_row("1", "example.com", is_checked=True),
        _make_row("2", "unrelated.org", is_checked=False),
        _make_row("3", "example.com.au", is_checked=False),
    ]
    mock_async_playwright, _ = _build_playwright_mock(rows)

    with patch("src.salesgazer.client.async_playwright", mock_async_playwright):
        with patch("src.salesgazer.client.stealth_async", AsyncMock()):
            results = await client.find_store_ids("example.com")

    # "example.com" and "example.com.au" both match; "unrelated.org" does not
    store_ids = {r["store_id"] for r in results}
    assert "1" in store_ids
    assert "3" in store_ids
    assert "2" not in store_ids


@pytest.mark.asyncio
async def test_find_store_ids_no_rows_returns_empty(client, monkeypatch):
    """find_store_ids() returns [] gracefully when wait_for_selector times out."""
    monkeypatch.setattr(
        "src.salesgazer.client.settings.salesgazer_email", "test@example.com"
    )
    monkeypatch.setattr(
        "src.salesgazer.client.settings.salesgazer_password", "s3cr3t"
    )

    # Selector times out → no store rows rendered
    mock_async_playwright, mock_page = _build_playwright_mock([])
    mock_page.wait_for_selector = AsyncMock(
        side_effect=Exception("Timeout waiting for tr[store-id]")
    )

    with patch("src.salesgazer.client.async_playwright", mock_async_playwright):
        with patch("src.salesgazer.client.stealth_async", AsyncMock()):
            results = await client.find_store_ids("example.com")

    assert results == []


@pytest.mark.asyncio
async def test_find_store_ids_syncs_cookies_to_httpx(client, monkeypatch):
    """Playwright cookies are synced to the httpx client after scraping."""
    monkeypatch.setattr(
        "src.salesgazer.client.settings.salesgazer_email", "test@example.com"
    )
    monkeypatch.setattr(
        "src.salesgazer.client.settings.salesgazer_password", "s3cr3t"
    )

    row = _make_row("77", "example.com")
    mock_async_playwright, _ = _build_playwright_mock([row])

    # Override cookies() to return one session cookie
    pw_instance = mock_async_playwright.return_value
    pw_instance.chromium.launch.return_value.new_context.return_value.cookies = (
        AsyncMock(return_value=[{"name": "sessionid", "value": "abc123"}])
    )

    with patch("src.salesgazer.client.async_playwright", mock_async_playwright):
        with patch("src.salesgazer.client.stealth_async", AsyncMock()):
            await client.find_store_ids("example.com")

    httpx_client = await client._get_client()
    assert httpx_client.cookies.get("sessionid") == "abc123"


@pytest.mark.asyncio
async def test_find_store_ids_raises_without_credentials(client, monkeypatch):
    """find_store_ids() raises ValueError when credentials are missing."""
    monkeypatch.setattr(
        "src.salesgazer.client.settings.salesgazer_email", ""
    )
    monkeypatch.setattr(
        "src.salesgazer.client.settings.salesgazer_password", ""
    )

    with pytest.raises(ValueError, match="SALESGAZER_EMAIL"):
        await client.find_store_ids("example.com")
