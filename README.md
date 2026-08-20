# nov-cli

A terminal reader for webnovels. Search a site, pick a result, pick a chapter, read. Press `n` or `p` to move between chapters without leaving the terminal. It's inspired by [ani-cli](https://github.com/pystardust/ani-cli), just for text instead of video.

nov-cli doesn't host or bundle any novel content. It fetches pages on demand from a site you point it at and renders them where you're reading. Right now that's one site:

- [Novel Phoenix](https://novelphoenix.com)

## Install

```sh
git clone https://github.com/AbiralTr/nov-cli
cd nov-cli
pip install -e .
```

That gives you a `nov-cli` command, defined in `pyproject.toml`'s `[project.scripts]`. Needs Python 3.9+. If you'd rather it live outside any one project's venv, `pipx install -e .` puts it on your PATH globally.

## Usage

Run `nov-cli` with no arguments and you're dropped into a prompt:

```sh
$ nov-cli
nov-cli — type a novel title to search.
Commands: c = continue last read, history, q = quit

search> shadow slave
```

Type a title and pick a result from the arrow-key menu, then choose where to start:

- **Start from chapter 1** — no chapter list fetched, jumps straight in.
- **Jump to latest chapter** — fetches the last page of the table of contents directly, not the pages before it.
- **Pick a chapter number** — also skips the listing; goes straight to that chapter's page.
- **Browse chapters** — a menu over the table of contents, 50 chapters at a time; ←/→ jump a page back or forward directly, no need to arrow down to a "next page" entry. It only fetches enough of the listing to fill the page you're looking at, so paging through a 3,000-chapter novel doesn't mean waiting on the whole table of contents up front.

Escape backs out a level at every one of those menus — same as picking Cancel, just faster.

From there, `n`/`p` move you between chapters, `b` reopens that same browse menu without losing your place, and `q` backs out of the chapter and drops you at `search>` again, so you can look something else up without relaunching the command. `c` resumes wherever you last left off, `history` lists everything you've read, and `q` at the prompt exits for real. The screen clears between chapters and browse pages, so you're never scrolling back through everything you've already read.

If you already know what you want, skip the prompt:

```sh
nov-cli shadow slave          # search, pick a result, pick a starting chapter
nov-cli shadow slave -e 42    # search, then jump straight to chapter 42
nov-cli -c                    # resume the last novel/chapter you were reading
nov-cli --history             # list everything you've read
```

Reading progress saves after every chapter to `~/.local/state/nov-cli/history.json`, so `nov-cli -c` picks up exactly where you stopped.

## How it works

Each site lives in its own adapter, `src/nov_cli/sites/<site>.py`, implementing `search()`, `list_chapters_page()` (a single page of the table of contents, for lazy browsing), `list_chapters()` (the full thing, built on top of `list_chapters_page()`), and `get_chapter()` / `get_chapter_by_url()`. The CLI and the reader don't touch any site-specific HTML themselves — that's the adapter's job, and the only thing you'd need to write to support a new site. Nothing gets cached or redistributed; every chapter is fetched fresh.

To add a site: write a new adapter implementing `Site` from `sites/base.py`, then register it in the `SITES` dict in `sites/__init__.py`.

## A note on scraping etiquette

This is a personal reading tool, same spirit as ani-cli, not a bulk downloader. It retries with backoff if a site rate-limits you (HTTP 403/429), but that's a courtesy, not a license to hammer someone's server — space out your requests. It also only reads what's already freely visible on the page; it doesn't get around logins, paywalls, or anything else gating the content.

## Roadmap

- More site adapters
- Auto-detect which site a saved slug belongs to, for `--site`
- Optional export to plain text or EPUB for offline reading
- A config file for defaults (pager, width, default site)

## License

MIT — see [LICENSE](LICENSE).
