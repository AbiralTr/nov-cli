"""Site adapters. Each adapter implements the `Site` interface in `base.py`.

Add a new site by dropping a module in this package, implementing `Site`,
and registering it in `SITES` below.
"""

from __future__ import annotations

from nov_cli.sites.base import Chapter, ChapterRef, SearchResult, Site
from nov_cli.sites.novelphoenix import NovelPhoenix

SITES: dict[str, type[Site]] = {
    NovelPhoenix.name: NovelPhoenix,
}

DEFAULT_SITE = NovelPhoenix.name

__all__ = [
    "Chapter",
    "ChapterRef",
    "SearchResult",
    "Site",
    "SITES",
    "DEFAULT_SITE",
]
