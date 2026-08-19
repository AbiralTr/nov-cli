"""Shared types and the interface every site adapter implements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SearchResult:
    """One hit from a site's search results."""

    title: str
    slug: str
    url: str
    cover_url: Optional[str] = None


@dataclass
class ChapterRef:
    """A lightweight pointer to a chapter, as seen in a table of contents."""

    number: int
    title: str
    url: str


@dataclass
class Chapter:
    """A fetched chapter, ready to read."""

    novel_title: str
    chapter_title: str
    url: str
    paragraphs: list[str]
    prev_url: Optional[str] = None
    next_url: Optional[str] = None


class Site:
    """Interface a site adapter must implement to plug into nov-cli."""

    name: str = "base"
    base_url: str = ""

    def search(self, query: str) -> list[SearchResult]:
        raise NotImplementedError

    def list_chapters(self, slug: str) -> list[ChapterRef]:
        raise NotImplementedError

    def get_chapter(self, slug: str, number: int) -> Chapter:
        raise NotImplementedError

    def get_chapter_by_url(self, url: str) -> Chapter:
        raise NotImplementedError
