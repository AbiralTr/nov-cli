# nov-cli

A terminal webnovel reader. Search a site, pick a novel, pick a chapter, read — with `n`/`p` to move between chapters. Inspired by [ani-cli](https://github.com/pystardust/ani-cli), but for text instead of video.

nov-cli doesn't host or bundle any novel content — it scrapes pages on demand from sites you point it at and renders them in your terminal. Currently supported:

- [Novel Phoenix](https://novelphoenix.com)

## Install

```sh
git clone https://github.com/AbiralTr/nov-cli
cd nov-cli
pip install -e .
```

This installs a `nov` command (via `pyproject.toml`'s `[project.scripts]`). Requires Python 3.9+.

## Usage

```sh
nov shadow slave          # search, pick a result, pick a starting chapter, start reading
nov shadow slave -e 42    # search, then jump straight to chapter 42
nov -c                    # resume the last novel/chapter you were reading
nov --history             # list everything you've read so far
```

While reading:

- `n` — next chapter
- `p` — previous chapter
- `q` — quit

Progress is saved automatically after each chapter to `~/.local/state/nov-cli/history.json`, so `nov -c` always picks up where you left off.

## How it works

Each site is a small adapter (`src/nov_cli/sites/<site>.py`) implementing a common interface: `search()`, `list_chapters()`, and `get_chapter()`/`get_chapter_by_url()`. The CLI and reader don't know anything about site-specific HTML — that's the adapter's job. Chapters are fetched fresh over HTTP each time; nothing is cached or redistributed.

To add another site, drop a new adapter in `src/nov_cli/sites/`, implement `Site` from `sites/base.py`, and register it in `sites/__init__.py`'s `SITES` dict.

## Notes

- This is a personal-use scraping tool, same spirit as ani-cli. Be a reasonable citizen of the sites you point it at — it already retries with backoff on rate limiting (HTTP 403/429), but don't hammer a site with rapid repeated requests.
- Only reads novels that are already freely and publicly readable on the target site; it doesn't bypass paywalls, logins, or access controls.

## Roadmap

- [ ] More site adapters
- [ ] `--site` fuzzy fallback / auto-detect which site a slug belongs to
- [ ] Optional local export (e.g. to a text/EPUB file) for offline reading
- [ ] Config file for defaults (pager, width, site)

## License

MIT — see [LICENSE](LICENSE).
