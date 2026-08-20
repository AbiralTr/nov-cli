"""Site adapter for novelphoenix.com."""

from __future__ import annotations

import time
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from nov_cli.sites.base import Chapter, ChapterPage, ChapterRef, SearchResult, Site

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Referer": "https://novelphoenix.com/",
}


class NovelPhoenix(Site):
    name = "novelphoenix"
    base_url = "https://novelphoenix.com"

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        # requests.Session() pre-populates User-Agent/Accept/Accept-Encoding/
        # Connection itself, so `setdefault` would leave those four as
        # "python-requests/x.y" — update() so our values always win.
        self.session.headers.update(DEFAULT_HEADERS)

    def _get(self, path: str, retries: int = 3, **kwargs) -> BeautifulSoup:
        url = path if path.startswith("http") else urljoin(self.base_url, path)
        last_exc: Optional[Exception] = None
        for attempt in range(retries):
            try:
                resp = self.session.get(url, timeout=15, **kwargs)
                # Cloudflare's bot check occasionally rejects a request that
                # would succeed on retry; treat it like a transient error.
                if resp.status_code in (403, 429) and attempt < retries - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                return BeautifulSoup(resp.text, "html.parser")
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < retries - 1:
                    time.sleep(0.5 * (attempt + 1))
        raise last_exc  # type: ignore[misc]

    def search(self, query: str) -> list[SearchResult]:
        soup = self._get("/search", params={"keyword": query})
        results: list[SearchResult] = []
        for li in soup.select("ul.novel-list li.novel-item"):
            a = li.select_one("a[href]")
            if not a:
                continue
            href = a["href"]
            slug = href.rstrip("/").split("/")[-1]
            title_el = li.select_one(".novel-title")
            title = title_el.get_text(strip=True) if title_el else a.get("title", slug)
            cover_el = li.select_one("img")
            cover_url = cover_el.get("src") if cover_el else None
            if cover_url and not cover_url.startswith("http"):
                cover_url = urljoin(self.base_url, cover_url)
            results.append(
                SearchResult(
                    title=title,
                    slug=slug,
                    url=urljoin(self.base_url, href),
                    cover_url=cover_url,
                )
            )
        return results

    def list_chapters(self, slug: str) -> list[ChapterRef]:
        """Fetch the full table of contents, one site page at a time.
        For a long-running novel this can mean dozens of requests — prefer
        `list_chapters_page` when you don't need every chapter at once."""
        chapters: list[ChapterRef] = []
        page = 1
        while True:
            result = self.list_chapters_page(slug, page)
            chapters.extend(result.chapters)
            if not result.has_next:
                break
            page += 1
        chapters.sort(key=lambda c: c.number)
        return chapters

    def list_chapters_page(self, slug: str, page: int) -> ChapterPage:
        soup = self._get(f"/novel/{slug}/chapters", params={"page": page})
        chapters: list[ChapterRef] = []
        for a in soup.select("ul.chapter-list li a[href]"):
            no_el = a.select_one(".chapter-no")
            title_el = a.select_one(".chapter-title")
            no_text = no_el.get_text(strip=True) if no_el else ""
            number = int(no_text) if no_text.isdigit() else len(chapters) + 1
            title = title_el.get_text(strip=True) if title_el else a.get("title", "")
            chapters.append(
                ChapterRef(number=number, title=title, url=urljoin(self.base_url, a["href"]))
            )

        pagination = soup.select_one(".pagination")
        has_next = bool(pagination and pagination.select(f'a[href*="page={page + 1}"]'))
        last_page = None
        if pagination:
            page_numbers = [
                int(text) for a in pagination.select("a[href]")
                if (text := a.get_text(strip=True)).isdigit()
            ]
            if page_numbers:
                last_page = max(page_numbers)

        return ChapterPage(chapters=chapters, page=page, has_next=has_next, last_page=last_page)

    def get_chapter(self, slug: str, number: int) -> Chapter:
        return self.get_chapter_by_url(f"{self.base_url}/novel/{slug}/chapter-{number}")

    def get_chapter_by_url(self, url: str) -> Chapter:
        soup = self._get(url)

        novel_title_el = soup.select_one(".booktitle")
        chapter_title_el = soup.select_one(".chapter-title")
        content_el = soup.select_one("#content")
        if content_el is None:
            raise ValueError(f"Could not find chapter content at {url} (page layout may have changed)")

        paragraphs = [
            text for p in content_el.find_all("p") if (text := p.get_text(strip=True))
        ]

        prev_url = self._nav_url(soup, "a.prevchap")
        next_url = self._nav_url(soup, "a.nextchap")

        return Chapter(
            novel_title=novel_title_el.get_text(strip=True) if novel_title_el else "",
            chapter_title=chapter_title_el.get_text(strip=True) if chapter_title_el else "",
            url=url,
            paragraphs=paragraphs,
            prev_url=prev_url,
            next_url=next_url,
        )

    def _nav_url(self, soup: BeautifulSoup, selector: str) -> Optional[str]:
        a = soup.select_one(selector)
        if not a:
            return None
        classes = a.get("class") or []
        if "isDisabled" in classes:
            return None
        href = a.get("href")
        if not href or href.startswith("javascript:"):
            return None
        return urljoin(self.base_url, href)
