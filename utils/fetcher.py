from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

logger = logging.getLogger(__name__)

# A realistic desktop Chrome identity. Many news sites reject the default
# Playwright/headless user-agent outright (403 / challenge pages), which is why
# major outlets returned nothing on a bare browser.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
EXTRA_HEADERS = {
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
}


@dataclass(slots=True)
class FetchResult:
    url: str
    html: str
    final_url: str


async def fetch_text(url: str, timeout_ms: int = 25000) -> FetchResult:
    """Fetch a URL as raw text over plain HTTP.

    Used for RSS/Atom feeds: fetching a feed through a browser makes Chrome
    render it in its XML viewer, so page.content() returns an HTML wrapper
    instead of the raw <item> elements. A plain HTTP GET returns the real XML.
    """
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, **EXTRA_HEADERS},
        follow_redirects=True,
        timeout=timeout_ms / 1000,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return FetchResult(url=url, html=response.text, final_url=str(response.url))


class BrowserFetcher:
    def __init__(
        self,
        timeout_ms: int = 30000,
        retries: int = 3,
        retry_delay_seconds: float = 2.0,
        headless: bool = True,
        cdp_url: str | None = None,
    ) -> None:
        self.timeout_ms = timeout_ms
        self.retries = retries
        self.retry_delay_seconds = retry_delay_seconds
        self.headless = headless
        # When set (e.g. http://localhost:9222), fetch through an already-running
        # Chrome via the DevTools protocol instead of launching a fresh browser.
        # This uses the real browser's fingerprint/cookies, which is the only
        # way to reach a few bot-sensitive, JS-rendered sources.
        self.cdp_url = cdp_url
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._owns_browser = True
        self._owns_context = True

    async def __aenter__(self) -> "BrowserFetcher":
        self._playwright = await async_playwright().start()
        if self.cdp_url:
            self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_url)
            self._owns_browser = False  # the user's browser — never close it
            if self._browser.contexts:
                self._context = self._browser.contexts[0]
                self._owns_context = False
            else:
                self._context = await self._browser.new_context()
                self._owns_context = True
        else:
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            self._context = await self._browser.new_context(
                user_agent=USER_AGENT,
                locale="ar-LY",
                viewport={"width": 1366, "height": 900},
                extra_http_headers=EXTRA_HEADERS,
            )
        return self

    async def __aexit__(self, *_args: object) -> None:
        if self._context and self._owns_context:
            await self._context.close()
        if self._browser and self._owns_browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def fetch(
        self,
        url: str,
        wait_for_selector: str | None = None,
        settle: bool = True,
    ) -> FetchResult:
        if not self._context:
            raise RuntimeError("BrowserFetcher must be used as an async context manager")

        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            page: Page | None = None
            try:
                page = await self._context.new_page()
                page.set_default_timeout(self.timeout_ms)
                await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                if wait_for_selector:
                    await page.wait_for_selector(wait_for_selector, timeout=self.timeout_ms)
                # Many listing pages render client-side, so the configured
                # selector is often a generic tag (e.g. `li`) that already exists
                # in the static shell; the wait above can resolve before the list
                # populates. Give the network a short, best-effort chance to
                # settle. `settle=False` skips this for article pages, whose
                # metadata (publish date) is in the initial server-rendered HTML.
                if settle:
                    try:
                        await page.wait_for_load_state("networkidle", timeout=min(self.timeout_ms, 8000))
                    except Exception:
                        pass
                html = await page.content()
                return FetchResult(url=url, html=html, final_url=page.url)
            except Exception as exc:  # Playwright raises several transport-specific subclasses.
                last_error = exc
                logger.warning("Fetch failed for %s on attempt %s/%s: %s", url, attempt, self.retries, exc)
                if attempt < self.retries:
                    await asyncio.sleep(self.retry_delay_seconds * attempt)
            finally:
                if page:
                    await page.close()

        raise RuntimeError(f"Failed to fetch {url} after {self.retries} attempts") from last_error
