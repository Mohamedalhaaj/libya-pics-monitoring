from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import requests
from playwright.async_api import Browser, Page, async_playwright

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
}


@dataclass(slots=True)
class FetchResult:
    url: str
    html: str
    final_url: str
    status_code: int | None = None


class BrowserFetcher:
    def __init__(
        self,
        timeout_ms: int = 30000,
        retries: int = 3,
        retry_delay_seconds: float = 2.0,
        headless: bool = True,
    ) -> None:
        self.timeout_ms = timeout_ms
        self.retries = retries
        self.retry_delay_seconds = retry_delay_seconds
        self.headless = headless
        self._playwright = None
        self._browser: Browser | None = None

    async def __aenter__(self) -> "BrowserFetcher":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        return self

    async def __aexit__(self, *_args: object) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def fetch(self, url: str, wait_for_selector: str | None = None) -> FetchResult:
        try:
            return await self.fetch_with_playwright(url, wait_for_selector)
        except Exception as playwright_exc:
            logger.warning("Playwright fetch failed for %s, trying requests fallback: %s", url, playwright_exc)
            try:
                return await asyncio.to_thread(self.fetch_with_requests, url)
            except Exception as requests_exc:
                raise RuntimeError(
                    f"Playwright and requests fetch failed for {url}; "
                    f"playwright={playwright_exc}; requests={requests_exc}"
                ) from requests_exc

    async def fetch_with_playwright(self, url: str, wait_for_selector: str | None = None) -> FetchResult:
        if not self._browser:
            raise RuntimeError("BrowserFetcher must be used as an async context manager")

        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            page: Page | None = None
            try:
                page = await self._browser.new_page()
                await page.set_extra_http_headers(DEFAULT_HEADERS)
                page.set_default_timeout(self.timeout_ms)
                response = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                if wait_for_selector:
                    await page.wait_for_selector(wait_for_selector, timeout=self.timeout_ms)
                html = await page.content()
                return FetchResult(
                    url=url,
                    html=html,
                    final_url=page.url,
                    status_code=response.status if response else None,
                )
            except Exception as exc:  # Playwright raises several transport-specific subclasses.
                last_error = exc
                logger.warning("Fetch failed for %s on attempt %s/%s: %s", url, attempt, self.retries, exc)
                if attempt < self.retries:
                    await asyncio.sleep(self.retry_delay_seconds * attempt)
            finally:
                if page:
                    await page.close()

        raise RuntimeError(f"Failed to fetch {url} after {self.retries} attempts") from last_error

    def fetch_with_requests(self, url: str) -> FetchResult:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=max(10, int(self.timeout_ms / 1000)),
            allow_redirects=True,
        )
        response.raise_for_status()
        return FetchResult(url=url, html=response.text, final_url=response.url, status_code=response.status_code)
