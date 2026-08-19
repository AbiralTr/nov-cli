"""nov-cli entry point: search, pick, and read webnovels from the terminal."""

from __future__ import annotations

import argparse
import sys
from typing import Optional

import requests
from rich.console import Console
from rich.table import Table

from nov_cli import state
from nov_cli.reader import render_chapter
from nov_cli.sites import DEFAULT_SITE, SITES
from nov_cli.sites.base import Chapter, ChapterRef, SearchResult, Site

console = Console()
err_console = Console(stderr=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nov",
        description="Search, browse, and read webnovels from your terminal.",
    )
    parser.add_argument("query", nargs="*", help="Novel title to search for")
    parser.add_argument(
        "-e", "--chapter", type=int, metavar="N", help="Jump straight to chapter N"
    )
    parser.add_argument(
        "-c", "--continue", dest="cont", action="store_true",
        help="Continue the most recently read novel",
    )
    parser.add_argument(
        "--history", action="store_true", help="List your reading history and exit"
    )
    parser.add_argument(
        "--site", default=DEFAULT_SITE, choices=sorted(SITES), help="Site to use"
    )
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.history:
        _print_history()
        return

    site: Site = SITES[args.site]()

    try:
        if args.cont:
            entry = state.most_recent()
            if not entry:
                err_console.print("[yellow]No reading history yet.[/yellow]")
                sys.exit(1)
            chapter = site.get_chapter_by_url(entry["url"])
            _read_session(site, entry["slug"], chapter)
            return

        if not args.query:
            err_console.print("[yellow]Usage:[/yellow] nov <novel title>   (or: nov -c / nov --history)")
            sys.exit(1)

        query = " ".join(args.query)
        results = site.search(query)

        if not results:
            err_console.print(f"[yellow]No results for[/yellow] '{query}'")
            sys.exit(1)

        result = _pick_result(results)
        slug = result.slug

        if args.chapter:
            chapter = site.get_chapter(slug, args.chapter)
        else:
            chapter = _pick_starting_chapter(site, slug)

        _read_session(site, slug, chapter)
    except requests.RequestException as exc:
        _print_network_error(exc)
        sys.exit(1)


def _pick_result(results: list[SearchResult]) -> SearchResult:
    if len(results) == 1:
        console.print(f"[cyan]Found:[/cyan] {results[0].title}")
        return results[0]

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right")
    table.add_column("Title")
    for i, r in enumerate(results, start=1):
        table.add_row(str(i), r.title)
    console.print(table)

    return results[_prompt_index("Pick a novel", len(results))]


def _pick_starting_chapter(site: Site, slug: str) -> Chapter:
    existing = state.get_progress(site.name, slug)
    if existing:
        console.print(
            f"[cyan]Resuming[/cyan] {existing['novel_title']} — {existing['chapter_title']}"
        )
        return site.get_chapter_by_url(existing["url"])

    console.print("[dim]Fetching chapter list...[/dim]")
    try:
        chapters = site.list_chapters(slug)
    except Exception:  # noqa: BLE001
        chapters = []

    if not chapters:
        return site.get_chapter(slug, 1)

    console.print(f"[dim]{len(chapters)} chapters found.[/dim]")
    idx = _prompt_chapter_choice(chapters)
    return site.get_chapter_by_url(chapters[idx].url)


def _prompt_chapter_choice(chapters: list[ChapterRef]) -> int:
    console.print("[cyan]1[/cyan]) Start from chapter 1")
    console.print(f"[cyan]2[/cyan]) Jump to latest ({chapters[-1].title})")
    console.print("[cyan]3[/cyan]) Pick a chapter number")
    choice = console.input("[bold]> [/bold]").strip()
    if choice == "2":
        return len(chapters) - 1
    if choice == "3":
        n = console.input(f"Chapter number (1-{len(chapters)}): ").strip()
        try:
            n_int = int(n)
        except ValueError:
            n_int = 1
        n_int = max(1, min(n_int, len(chapters)))
        return n_int - 1
    return 0


def _prompt_index(prompt: str, count: int) -> int:
    while True:
        raw = console.input(f"[bold]{prompt} (1-{count}):[/bold] ").strip()
        if raw.isdigit() and 1 <= int(raw) <= count:
            return int(raw) - 1
        console.print("[yellow]Invalid choice, try again.[/yellow]")


def _read_session(site: Site, slug: str, chapter: Chapter) -> None:
    while True:
        render_chapter(chapter)
        state.save_progress(
            site=site.name,
            slug=slug,
            novel_title=chapter.novel_title,
            chapter_title=chapter.chapter_title,
            url=chapter.url,
        )

        console.print()
        options = []
        if chapter.next_url:
            options.append("[cyan]n[/cyan]ext")
        if chapter.prev_url:
            options.append("[cyan]p[/cyan]rev")
        options.append("[cyan]q[/cyan]uit")
        console.print(" · ".join(options))

        choice = console.input("[bold]> [/bold]").strip().lower()
        if choice in ("n", "next") and chapter.next_url:
            chapter = _fetch_or_retry(site, chapter.next_url)
        elif choice in ("p", "prev") and chapter.prev_url:
            chapter = _fetch_or_retry(site, chapter.prev_url)
        elif choice in ("q", "quit", ""):
            break
        else:
            console.print("[yellow]Unrecognized choice.[/yellow]")


def _fetch_or_retry(site: Site, url: str) -> Chapter:
    """Fetch a chapter, letting the user retry in place if it fails
    instead of losing their reading session."""
    while True:
        try:
            return site.get_chapter_by_url(url)
        except requests.RequestException as exc:
            _print_network_error(exc)
            if console.input("[bold]Retry? (Y/n) [/bold]").strip().lower() == "n":
                raise


def _print_network_error(exc: requests.RequestException) -> None:
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status in (403, 429):
        err_console.print(
            f"[red]Request blocked (HTTP {status}).[/red] The site's bot protection "
            "may be rate-limiting you — wait a moment before trying again."
        )
    else:
        err_console.print(f"[red]Network error:[/red] {exc}")


def _print_history() -> None:
    history = state.load_history()
    if not history:
        console.print("[yellow]No reading history yet.[/yellow]")
        return
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Novel")
    table.add_column("Last chapter")
    table.add_column("Site")
    for entry in history.values():
        table.add_row(entry["novel_title"], entry["chapter_title"], entry["site"])
    console.print(table)


if __name__ == "__main__":
    main()
