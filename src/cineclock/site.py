"""Every page of the site, built from the database.

Four kinds of page: the home page (rows of posters: on today, just added,
highly rated...), the showtimes page (everything, by day, with filters), one
page per film and one page per venue. pages() returns them all as
{path: html}, which the static build writes to disk and the dev server serves
from memory.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from sqlite3 import Connection

from cineclock import db
from cineclock.films import Film, match_key, slugify
from cineclock.models import VANCOUVER, Screening
from cineclock.render import env
from cineclock.tags import screening_tags, sort_tags
from cineclock.timefmt import clock, day_label, short_day
from cineclock.venues import BY_NAME, VENUES, Room, Venue, order, shown_specs

RAIL_LENGTH = 15
# Below this many Letterboxd ratings, an average says little.
MIN_RATINGS_FOR_TOP = 1000


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
    if name in BY_NAME:
        return BY_NAME[name]
    slug = slugify(name)
    return Venue(name, name, slug, "", "", "", "", rooms=(Room(f"{slug}-main", "Main"),))


def tags_for(s: Screening) -> list[str]:
    return screening_tags(s.title, s.note, s.film_format)


def compact(n: int) -> str:
    """1476132 -> 1.5M, 12345 -> 12K"""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{round(n / 1_000)}K"
    return str(n)


def rarity(screenings: list[Screening]) -> list[str]:
    """Flags for films you could easily miss: one showing, or several on a single day."""
    if len(screenings) == 1:
        return ["One screening"]
    if len({s.local_start.date() for s in screenings}) == 1:
        return ["One day only"]
    return []


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

    @property
    def next_showing(self) -> Screening:
        return min(self.screenings, key=lambda s: s.starts_at)

    @property
    def added(self) -> datetime | None:
        seen = [s.first_seen for s in self.screenings if s.first_seen]
        return min(seen) if seen else None

    @property
    def tags(self) -> list[str]:
        return sort_tags(
            [t for s in self.screenings for t in tags_for(s)] + rarity(self.screenings)
        )

    @property
    def venues(self) -> list[Venue]:
        names = sorted({s.venue for s in self.screenings}, key=lambda n: (order(n), n))
        return [venue_for(n) for n in names]

    @property
    def genres(self) -> list[str]:
        return self.film.genre_list if self.film else []

    @property
    def last_showing(self) -> Screening:
        return max(self.screenings, key=lambda s: s.starts_at)

    @property
    def date_range(self) -> str:
        """Oct 18 only, or Oct 18 to Nov 2"""
        first = self.next_showing.local_start.date()
        last = self.last_showing.local_start.date()
        if first == last:
            return f"{first:%b} {first.day} only"
        return f"{first:%b} {first.day} to {last:%b} {last.day}"


@dataclass
class Row:
    """One film at one venue on one day: a line on the showtimes page."""

    page: FilmPage
    title: str
    year: int | None
    note: str | None
    poster_url: str | None
    showtimes: list[Screening]

    @property
    def tags(self) -> list[str]:
        return sort_tags(
            [t for s in self.showtimes for t in tags_for(s)] + rarity(self.page.screenings)
        )


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


@dataclass
class Card:
    """A poster in one of the home page's rows. `why` says why it's in that row."""

    page: FilmPage
    next_label: str
    why: str | None = None


@dataclass
class Rail:
    title: str
    cards: list[Card]
    more: str  # where "See all" goes, relative to the site root


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


def when(s: Screening, now: datetime) -> str:
    """Today, 7:00 pm / Tomorrow, 7:00 pm / Oct 24, 7:00 pm (short enough for a card)"""
    today = now.astimezone(VANCOUVER).date()
    day = s.local_start.date()
    if day == today:
        return f"Today, {clock(s.starts_at)}"
    if day == today + timedelta(days=1):
        return f"Tomorrow, {clock(s.starts_at)}"
    return f"{day:%b} {day.day}, {clock(s.starts_at)}"


def rails(film_list: list[FilmPage], now: datetime) -> list[Rail]:
    today = now.astimezone(VANCOUVER).date()
    soonest = lambda p: p.next_showing.starts_at  # noqa: E731

    on_today = sorted(
        (p for p in film_list if any(s.local_start.date() == today for s in p.screenings)),
        key=soonest,
    )
    coming_up = sorted((p for p in film_list if p not in on_today), key=soonest)

    # Films that appeared in the last two weeks, newest first. Everything seen on
    # the very first run is the baseline, not news, so it doesn't count.
    added = [p.added for p in film_list if p.added]
    since = max(min(added), now - timedelta(days=14)) if added else now
    just_added = sorted(
        (p for p in film_list if p.added and p.added > since),
        key=lambda p: (-p.added.timestamp(), soonest(p)),
    )

    on_film = sorted((p for p in film_list if {"70mm", "35mm", "16mm"} & set(p.tags)), key=soonest)
    events = sorted((p for p in film_list if "Event" in p.tags), key=soonest)
    top = sorted(
        (
            p
            for p in film_list
            if p.film
            and p.film.letterboxd_rating
            and (p.film.letterboxd_count or 0) >= MIN_RATINGS_FOR_TOP
        ),
        key=lambda p: -p.film.letterboxd_rating,
    )
    popular = sorted(
        (p for p in film_list if p.film and p.film.letterboxd_count),
        key=lambda p: -p.film.letterboxd_count,
    )
    busiest = sorted(
        (p for p in film_list if len(p.screenings) > 1),
        key=lambda p: (-len(p.screenings), soonest(p)),
    )

    def cards(pages, why=None):
        return [
            Card(p, when(p.next_showing, now), why(p) if why else None) for p in pages[:RAIL_LENGTH]
        ]

    found = [
        Rail("On today", cards(on_today), f"showtimes/#d{today:%Y%m%d}"),
        Rail("Coming up", cards(coming_up), "films/"),
        Rail("Just added", cards(just_added), "films/?sort=added"),
        Rail(
            "On film",
            cards(on_film, lambda p: " and ".join(t for t in p.tags if t.endswith("mm"))),
            "films/?tag=on-film",
        ),
        Rail(
            "Highly rated",
            cards(top, lambda p: f"{p.film.letterboxd_rating:.1f} on Letterboxd"),
            "films/?sort=rated",
        ),
        Rail(
            "Popular",
            cards(popular, lambda p: f"{compact(p.film.letterboxd_count)} Letterboxd ratings"),
            "films/?sort=popular",
        ),
        Rail(
            "Events and guests",
            cards(
                events, lambda p: next((s.note for s in p.screenings if s.note), "Special event")
            ),
            "films/?tag=event",
        ),
        Rail(
            "Most screenings",
            cards(busiest, lambda p: f"{len(p.screenings)} screenings"),
            "films/?sort=screenings",
        ),
    ]
    return [r for r in found if r.cards]


def updated_label(now: datetime) -> str:
    local = now.astimezone(VANCOUVER)
    return f"{local:%a %b} {local.day}, {clock(now)}"


def pages(conn: Connection, now: datetime) -> dict[str, str]:
    screenings = db.upcoming(conn, now)
    films = db.films_by_key(conn)
    page_of = film_pages(screenings, films)
    film_list = list({id(p): p for p in page_of.values()}.values())
    days = group_days(screenings, page_of, films, now)
    common = {"updated": updated_label(now), "venues": VENUES}

    def render(template: str, path: str, **context) -> str:
        root = "../" * path.count("/")
        return env.get_template(template).render(root=root, path=path, **common, **context)

    filter_tags = sort_tags({t for p in film_list for t in p.tags})
    out = {
        "index.html": render("index.html", "index.html", rails=rails(film_list, now)),
        "showtimes/index.html": render(
            "showtimes.html",
            "showtimes/index.html",
            days=days,
            filter_tags=filter_tags,
            genres=sorted({g for p in film_list for g in p.genres}),
            current="showtimes",
        ),
    }

    by_next = sorted(film_list, key=lambda p: p.next_showing.starts_at)
    out["films/index.html"] = render(
        "films.html",
        "films/index.html",
        films=by_next,
        filter_tags=filter_tags,
        genres=sorted({g for p in film_list for g in p.genres}),
        current="films",
    )

    for page in film_list:
        path = f"films/{page.slug}/index.html"
        page_days = group_days(page.screenings, page_of, films, now)
        out[path] = render("film.html", path, page=page, film=page.film, days=page_days)

    out["theatres/index.html"] = render("theatres.html", "theatres/index.html", current="theatres")
    for venue in VENUES:
        path = f"theatres/{venue.slug}/index.html"
        mine = [s for s in screenings if s.venue == venue.name]
        out[path] = render(
            "venue.html",
            path,
            venue=venue,
            spec_fields=shown_specs(),
            current="theatres",
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
    tag_counts: dict[str, int] = defaultdict(int)
    for s in screenings:
        per_venue[s.venue] += 1
        for t in tags_for(s):
            tag_counts[t] += 1
    return {
        "updated": now.isoformat(),
        "screenings": len(screenings),
        "per_venue": dict(sorted(per_venue.items(), key=lambda item: order(item[0]))),
        "tagged_screenings": dict(sorted(tag_counts.items())),
        "films": len(keys),
        "looked_up": len(known),
        "matched": sum(f.matched for f in known),
        "with_letterboxd_rating": sum(f.letterboxd_rating is not None for f in known),
        "with_letterboxd_count": sum(f.letterboxd_count is not None for f in known),
        "with_imdb_rating": sum(f.imdb_rating is not None for f in known),
        "with_rt_score": sum(f.rt_score is not None for f in known),
        "unmatched": sorted(k for k in keys if k not in films or not films[k].matched),
    }
