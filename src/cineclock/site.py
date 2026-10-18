"""Every page of the site, built from the database.

Three kinds of page: the home page (what's on, by day), one page per film
and one page per venue. pages() returns them all as {path: html}, which the
static build writes to disk and the dev server serves from memory.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from sqlite3 import Connection

from cineclock import db
from cineclock.films import Film, match_key, slugify
from cineclock.models import VANCOUVER, Screening
from cineclock.render import env
from cineclock.timefmt import clock, day_label, short_day
from cineclock.venues import BY_NAME, VENUES, Venue, order


@dataclass
class FilmPage:
    slug: str
    title: str
    year: int | None
    film: Film | None
    screenings: list[Screening] = field(default_factory=list)

    @property
    def poster_url(self) -> str | None:
        return choose_poster(self.screenings[0], self.film) if self.screenings else None


@dataclass
class Row:
    """One film at one venue on one day: what a line on the home page shows."""

    page: FilmPage
    title: str
    year: int | None
    note: str | None
    poster_url: str | None
    showtimes: list[Screening]


@dataclass
class VenueGroup:
    venue: Venue
    rows: list[Row]


@dataclass
class Day:
    date: date
    label: str
    short: str
    groups: list[VenueGroup]

    @property
    def anchor(self) -> str:
        return f"d{self.date:%Y%m%d}"


def choose_poster(screening: Screening, film: Film | None) -> str | None:
    """The Rio's and the Park's own posters first; elsewhere TMDB's poster beats a still."""
    venue = BY_NAME.get(screening.venue)
    if venue and venue.own_posters and screening.poster_url:
        return screening.poster_url
    if film and film.poster_url:
        return film.poster_url
    return screening.poster_url


def venue_for(name: str) -> Venue:
    # A venue missing from the registry still gets a page rather than crashing the build.
    return BY_NAME.get(name) or Venue(name, slugify(name), "", "", "")


def film_pages(screenings: list[Screening], films: dict[str, Film]) -> dict[int, FilmPage]:
    """Group screenings into one page per film. Returns {id(screening): page}."""
    pages: dict[tuple, FilmPage] = {}
    used_slugs: set[str] = set()
    by_screening = {}
    for s in sorted(screenings, key=lambda s: s.starts_at):
        film = films.get(match_key(s.title, s.year))
        # Matched films share a page across venues, even when venues word the
        # title differently ("Ken Russell's 'The Devils'" and "The Devils").
        if film and film.matched:
            identity = ("tmdb", film.tmdb_id)
            title, year = film.title or s.title, film.year or s.year
        else:
            identity = ("title", match_key(s.title, s.year))
            title, year = s.title, s.year
        if identity not in pages:
            base = slugify(title) + (f"-{year}" if year else "")
            slug, n = base, 2
            while slug in used_slugs:
                slug, n = f"{base}-{n}", n + 1
            used_slugs.add(slug)
            pages[identity] = FilmPage(slug, title, year, film if film and film.matched else None)
        pages[identity].screenings.append(s)
        by_screening[id(s)] = pages[identity]
    return by_screening


def group_days(
    screenings: list[Screening], page_of: dict[int, FilmPage], films: dict[str, Film], now: datetime
) -> list[Day]:
    today = now.astimezone(VANCOUVER).date()
    by_day: dict[date, list[Screening]] = defaultdict(list)
    for s in sorted(screenings, key=lambda s: s.starts_at):
        by_day[s.local_start.date()].append(s)

    days = []
    for day in sorted(by_day):
        by_venue: dict[str, list[Screening]] = defaultdict(list)
        for s in by_day[day]:
            by_venue[s.venue].append(s)
        groups = []
        for name in sorted(by_venue, key=lambda n: (order(n), n)):
            rows: dict[tuple, Row] = {}
            for s in by_venue[name]:
                # Two showings of a film on one day share a row, unless the venue
                # labels them differently (a 70mm show and a regular one).
                key = (id(page_of[id(s)]), s.note)
                if key not in rows:
                    film = films.get(match_key(s.title, s.year))
                    rows[key] = Row(
                        page_of[id(s)], s.title, s.year, s.note, choose_poster(s, film), []
                    )
                rows[key].showtimes.append(s)
            groups.append(VenueGroup(venue_for(name), list(rows.values())))
        days.append(Day(day, day_label(day, today), short_day(day, today), groups))
    return days


def updated_label(now: datetime) -> str:
    local = now.astimezone(VANCOUVER)
    return f"{local:%a %b} {local.day}, {clock(now)}"


def pages(conn: Connection, now: datetime) -> dict[str, str]:
    screenings = db.upcoming(conn, now)
    films = db.films_by_key(conn)
    page_of = film_pages(screenings, films)
    days = group_days(screenings, page_of, films, now)
    common = {"updated": updated_label(now), "venues": VENUES}

    def render(template: str, path: str, **context) -> str:
        root = "../" * path.count("/")
        return env.get_template(template).render(root=root, path=path, **common, **context)

    out = {"index.html": render("index.html", "index.html", days=days)}

    for page in {id(p): p for p in page_of.values()}.values():
        path = f"films/{page.slug}/index.html"
        page_days = group_days(page.screenings, page_of, films, now)
        out[path] = render("film.html", path, page=page, film=page.film, days=page_days)

    for venue in VENUES:
        path = f"venues/{venue.slug}/index.html"
        mine = [s for s in screenings if s.venue == venue.name]
        out[path] = render(
            "venue.html",
            path,
            venue=venue,
            current_venue=venue.slug,
            days=group_days(mine, page_of, films, now),
        )
    return out


def stats(conn: Connection, now: datetime) -> dict:
    """A summary for checking a deploy at a glance (published as stats.json)."""
    screenings = db.upcoming(conn, now)
    films = db.films_by_key(conn)
    keys = {match_key(s.title, s.year) for s in screenings}
    known = [films[k] for k in keys if k in films]
    per_venue: dict[str, int] = defaultdict(int)
    for s in screenings:
        per_venue[s.venue] += 1
    return {
        "updated": now.isoformat(),
        "screenings": len(screenings),
        "per_venue": dict(sorted(per_venue.items(), key=lambda item: order(item[0]))),
        "films": len(keys),
        "looked_up": len(known),
        "matched": sum(f.matched for f in known),
        "with_letterboxd_rating": sum(f.letterboxd_rating is not None for f in known),
        "with_imdb_rating": sum(f.imdb_rating is not None for f in known),
        "with_rt_score": sum(f.rt_score is not None for f in known),
        "unmatched": sorted(k for k in keys if k not in films or not films[k].matched),
    }
