# cineclock

[![CI](https://github.com/yogzoth/cineclock/actions/workflows/ci.yml/badge.svg)](https://github.com/yogzoth/cineclock/actions/workflows/ci.yml)

Vancouver showtimes for film lovers. Indie and rep cinemas in one place.

## Status

Early days. Version 1 covers The Cinematheque, VIFF Centre, the Park and the Rio:

- [x] Project skeleton, tests and CI
- [x] Rio scraper (showtimes, year and poster from each film page)
- [x] Save to SQLite (reruns update instead of duplicating)
- [ ] What's playing page, by day and venue
- [ ] Add to calendar (.ics)
- [ ] VIFF, Cinematheque and Park scrapers

## Running it

Needs Python 3.12 or newer.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check .
fastapi dev src/cineclock/app.py
```

To scrape every venue and save to `cineclock.db`:

```sh
python -m cineclock.scrape
```

## How it's built

- Python, SQLite, FastAPI with Jinja2 templates
- httpx and BeautifulSoup for scraping
- Each venue scraper has a pure parse function tested against saved sample responses, so tests never hit the network
- Times are stored in UTC and shown in Vancouver time using the pinned `tzdata` package, so clock rule changes (like B.C.'s 2026 move to permanent daylight time) can't shift a showtime

## Credits

Inspired by [MovieClock](https://movieclock.app) by Jordan Hudson ([source](https://github.com/jordanhudson/moviecal), MIT licensed). Some scraper approaches are borrowed from it.

## License

MIT. See [LICENSE](LICENSE).
