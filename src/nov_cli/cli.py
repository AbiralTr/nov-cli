"""nov-cli entry point: search, pick, and read webnovels from the terminal."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Union

import questionary
import requests
from rich.console import Console
from rich.table import Table

from nov_cli import state
from nov_cli.reader import render_chapter
from nov_cli.sites import DEFAULT_SITE, SITES
from nov_cli.sites.base import Chapter, ChapterRef, SearchResult, Site

CHAPTERS_PER_PAGE = 30

console = Console()
err_console = Console(stderr=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nov-cli",
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
            _resume(site)
            return

        if args.query:
            # One-shot mode: `nov shadow slave [-e N]` — read once, then exit.
            _search_flow(site, " ".join(args.query), chapter_number=args.chapter)
            return

        _repl(site)
    except requests.RequestException as exc:
        _print_network_error(exc)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        console.print()


def _repl(site: Site) -> None:
    """Interactive front door: `nov` with no arguments drops you into a
    prompt where you can search repeatedly without re-invoking the command."""
    console.print("[bold cyan]nov-cli[/bold cyan] — type a novel title to search.")
    console.print("[dim]Commands: c = continue last read, history, q = quit[/dim]")
    while True:
        raw = console.input("\n[bold]search>[/bold] ").strip()
        cmd = raw.lower()
        if cmd in ("q", "quit", "exit", ""):
            break
        elif cmd in ("c", "continue"):
            _resume(site, quiet_if_missing=True)
        elif cmd in ("h", "history"):
            _print_history()
        else:
            try:
                _search_flow(site, raw)
            except requests.RequestException as exc:
                _print_network_error(exc)


def _resume(site: Site, quiet_if_missing: bool = False) -> None:
    entry = state.most_recent()
    if not entry:
        if quiet_if_missing:
            console.print("[yellow]No reading history yet.[/yellow]")
            return
        err_console.print("[yellow]No reading history yet.[/yellow]")
        sys.exit(1)
    chapter = site.get_chapter_by_url(entry["url"])
    _read_session(site, entry["slug"], chapter)


def _search_flow(site: Site, query: str, chapter_number: Optional[int] = None) -> None:
    results = site.search(query)

    if not results:
        console.print(f"[yellow]No results for[/yellow] '{query}'")
        return

    result = _pick_result(results)
    slug = result.slug

    if chapter_number:
        chapter = site.get_chapter(slug, chapter_number)
    else:
        chapter = _pick_starting_chapter(site, slug)

    if chapter is None:
        console.print("[dim]Cancelled.[/dim]")
        return

    _read_session(site, slug, chapter)


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


def _pick_starting_chapter(site: Site, slug: str) -> Optional[Chapter]:
    existing = state.get_progress(site.name, slug)
    if existing:
        console.print(
            f"[cyan]Resuming[/cyan] {existing['novel_title']} — {existing['chapter_title']}"
        )
        return site.get_chapter_by_url(existing["url"])

    choice = _prompt_chapter_choice(site, slug)
    if choice is None:
        return None
    return _resolve_chapter_choice(site, slug, choice)


def _resolve_chapter_choice(site: Site, slug: str, choice: Union[int, ChapterRef]) -> Chapter:
    if isinstance(choice, int):
        return site.get_chapter(slug, choice)
    return site.get_chapter_by_url(choice.url)


def _prompt_chapter_choice(site: Site, slug: str) -> Optional[Union[int, ChapterRef]]:
    """Where to start reading. Nothing gets fetched until the user picks
    an option — "browse" is the only path that needs the chapter list,
    and it's paged 30 at a time instead of pulling the whole thing up
    front (a long-running novel's table of contents can be 30+ requests).
    Returns None if the user backs out (Ctrl-C/Esc or explicit Cancel)."""
    answer = questionary.select(
        "Where do you want to start?",
        choices=[
            questionary.Choice("Start from chapter 1", value="first"),
            questionary.Choice("Jump to latest chapter", value="latest"),
            questionary.Choice("Pick a chapter number", value="number"),
            questionary.Choice("Browse chapters", value="browse"),
        ],
    ).ask()

    if answer is None:
        return None
    if answer == "first":
        return 1
    if answer == "number":
        return _prompt_chapter_number()
    if answer == "latest":
        ref = _latest_chapter_ref(site, slug)
        return ref if ref is not None else 1
    return _browse_chapters(site, slug)


def _prompt_chapter_number() -> int:
    raw = console.input("Chapter number: ").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 1


def _latest_chapter_ref(site: Site, slug: str) -> Optional[ChapterRef]:
    """Jump straight to the last page of the table of contents instead of
    paging through every one before it."""
    first = site.list_chapters_page(slug, 1)
    if not first.has_next or not first.last_page or first.last_page == 1:
        return first.chapters[-1] if first.chapters else None
    last = site.list_chapters_page(slug, first.last_page)
    return last.chapters[-1] if last.chapters else (first.chapters[-1] if first.chapters else None)


def _browse_chapters(site: Site, slug: str) -> Optional[Union[int, ChapterRef]]:
    """An arrow-key menu over the table of contents, fetched lazily and
    shown 30 chapters at a time, so browsing a 3000-chapter novel doesn't
    mean waiting on 30+ requests before you see anything."""
    cache: list[ChapterRef] = []
    next_site_page = 1
    exhausted = False
    last_page_hint: Optional[int] = None

    def ensure(count: int) -> None:
        nonlocal next_site_page, exhausted, last_page_hint
        while len(cache) < count and not exhausted:
            result = site.list_chapters_page(slug, next_site_page)
            cache.extend(result.chapters)
            last_page_hint = result.last_page or last_page_hint
            next_site_page += 1
            if not result.has_next:
                exhausted = True

    console.print("[dim]Fetching chapters...[/dim]")
    ensure(CHAPTERS_PER_PAGE)
    if not cache:
        console.print("[yellow]No chapter list available — starting from chapter 1.[/yellow]")
        return 1

    start = 0
    while True:
        ensure(start + CHAPTERS_PER_PAGE)
        window = cache[start : start + CHAPTERS_PER_PAGE]

        choices = []
        if start > 0:
            choices.append(questionary.Choice("◂ Previous 30", value="__prev__"))
        for ref in window:
            choices.append(questionary.Choice(f"{ref.number}. {ref.title}", value=ref))
        if start + CHAPTERS_PER_PAGE < len(cache) or not exhausted:
            choices.append(questionary.Choice("▸ Next 30", value="__next__"))
        choices.append(questionary.Choice("Jump to latest", value="__latest__"))
        choices.append(questionary.Choice("Pick a chapter number", value="__number__"))
        choices.append(questionary.Choice("Cancel", value="__cancel__"))

        known = f"{len(cache)}+" if not exhausted else str(len(cache))
        title = f"Chapters {start + 1}-{start + len(window)} of {known}"
        answer = questionary.select(title, choices=choices).ask()

        if answer in (None, "__cancel__"):
            return None
        if answer == "__next__":
            start += CHAPTERS_PER_PAGE
            continue
        if answer == "__prev__":
            start = max(0, start - CHAPTERS_PER_PAGE)
            continue
        if answer == "__latest__":
            return _latest_chapter_ref(site, slug)
        if answer == "__number__":
            return _prompt_chapter_number()
        return answer  # a ChapterRef the user picked directly


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
        options.append("[cyan]b[/cyan]rowse chapters")
        options.append("[cyan]q[/cyan]uit")
        console.print(" · ".join(options))

        choice = console.input("[bold]> [/bold]").strip().lower()
        if choice in ("n", "next") and chapter.next_url:
            chapter = _fetch_or_retry(site, chapter.next_url)
        elif choice in ("p", "prev") and chapter.prev_url:
            chapter = _fetch_or_retry(site, chapter.prev_url)
        elif choice in ("b", "browse"):
            chapter = _browse_or_stay(site, slug, chapter)
        elif choice in ("q", "quit", ""):
            break
        else:
            console.print("[yellow]Unrecognized choice.[/yellow]")


def _browse_or_stay(site: Site, slug: str, current: Chapter) -> Chapter:
    """Reopen the chapter browser from inside a reading session. Picking a
    chapter jumps there; cancelling (or a network hiccup) keeps you on the
    chapter you were already reading instead of losing the session."""
    try:
        picked = _browse_chapters(site, slug)
        if picked is None:
            return current
        return _resolve_chapter_choice(site, slug, picked)
    except requests.RequestException as exc:
        _print_network_error(exc)
        return current


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
