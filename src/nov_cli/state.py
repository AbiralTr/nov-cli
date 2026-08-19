"""Reading history: remembers the last chapter you read per novel, so
`nov -c` can pick up where you left off — mirrors ani-cli's watch history.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, TypedDict


def _state_dir() -> Path:
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    return base / "nov-cli"


def _state_file() -> Path:
    return _state_dir() / "history.json"


class HistoryEntry(TypedDict):
    site: str
    slug: str
    novel_title: str
    chapter_number: Optional[int]
    chapter_title: str
    url: str


def load_history() -> dict[str, HistoryEntry]:
    path = _state_file()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_progress(
    site: str,
    slug: str,
    novel_title: str,
    chapter_title: str,
    url: str,
    chapter_number: Optional[int] = None,
) -> None:
    history = load_history()
    key = f"{site}:{slug}"
    history[key] = {
        "site": site,
        "slug": slug,
        "novel_title": novel_title,
        "chapter_number": chapter_number,
        "chapter_title": chapter_title,
        "url": url,
    }
    path = _state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2), encoding="utf-8")


def get_progress(site: str, slug: str) -> Optional[HistoryEntry]:
    return load_history().get(f"{site}:{slug}")


def most_recent() -> Optional[HistoryEntry]:
    history = load_history()
    if not history:
        return None
    # dicts preserve insertion order; last inserted == most recently saved
    return next(reversed(history.values()), None)
