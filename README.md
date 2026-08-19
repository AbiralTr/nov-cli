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

That gives you a `nov` command, defined in `pyproject.toml`'s `[project.scripts]`. Needs Python 3.9+. If you'd rather it live outside any one project's venv, `pipx install -e .` puts it on your PATH globally.

## Usage

Run `nov` with no arguments and you're dropped into a prompt:

```sh
$ nov
nov-cli — type a novel title to search.
Commands: c = continue last read, history, q = quit

search> shadow slave
```

Type a title, pick a result, pick where to start reading, and go. `n`/`p` move you between chapters; `q` backs out of the chapter and drops you at `search>` again, so you can look something else up without relaunching the command. `c` resumes wherever you last left off, `history` lists everything you've read, and `q` at the prompt exits for real.

If you already know what you want, skip the prompt:

```sh
nov shadow slave          # search, pick a result, pick a starting chapter
nov shadow slave -e 42    # search, then jump straight to chapter 42
nov -c                    # resume the last novel/chapter you were reading
nov --history             # list everything you've read
```

Reading progress saves after every chapter to `~/.local/state/nov-cli/history.json`, so `nov -c` picks up exactly where you stopped.

## How it works

Each site lives in its own adapter, `src/nov_cli/sites/<site>.py`, implementing three methods: `search()`, `list_chapters()`, and `get_chapter()` (or `get_chapter_by_url()`). The CLI and the reader don't touch any site-specific HTML themselves — that's the adapter's job, and the only thing you'd need to write to support a new site. Nothing gets cached or redistributed; every chapter is fetched fresh.

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
