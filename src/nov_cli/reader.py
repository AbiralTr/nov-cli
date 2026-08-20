"""Renders a chapter to the terminal, paginated with $PAGER (falls back to
`less -R`, then plain stdout)."""

from __future__ import annotations

import os
import shutil
import subprocess

from rich.console import Console
from rich.text import Text

from nov_cli.sites.base import Chapter

PARAGRAPH_INDENT = "    "  # first-line indent, like a printed page


def render_chapter(chapter: Chapter) -> None:
    console = Console(width=100, highlight=False)
    with console.capture() as capture:
        console.print(Text(chapter.novel_title, style="bold cyan"))
        console.print(Text(chapter.chapter_title, style="bold"))
        console.print()
        for paragraph in chapter.paragraphs:
            console.print(PARAGRAPH_INDENT + paragraph, style="default")
            console.print()
            console.print()
    _page(capture.get())


def _page(text: str) -> None:
    pager = os.environ.get("PAGER")
    if not pager and shutil.which("less"):
        pager = "less -R"
    if not pager:
        print(text)
        return
    try:
        subprocess.run(pager, input=text.encode("utf-8"), shell=True, check=False)
    except OSError:
        print(text)
