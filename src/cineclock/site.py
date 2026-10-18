"""Every page of the site, built from the database.

Four kinds of page: the home page (rows of posters: on today, just added,
highly rated...), the showtimes page (everything, by day, with filters), one
page per film and one page per venue. pages() returns them all as
{path: html}, which the static build writes to disk and the dev server serves
from memory.
"""

import calendar
import json
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from sqlite3 import Connection

from cineclock import db, personal, profiles
from cineclock.films import Film, match_key, slugify
from cineclock.models import VANCOUVER, Screening
from cineclock.render import env
from cineclock.tags import EVENTS, ON_FILM, is_event, kind, screening_tags, sort_tags
from cineclock.timefmt import clock, day_label, short_day
from cineclock.venues import BY_NAME, VENUES, Room, Venue, order, shown_specs

RAIL_LENGTH = 15
RARE = ("One screening",)
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
    # The series name counts too, so a festival programme gets the Festival tag.
    note = " ".join(filter(None, [s.note, s.series])) or None
    return screening_tags(s.title, note, s.film_format)


def compact(n: int) -> str:
    """1476132 -> 1.5M, 12345 -> 12K"""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{round(n / 1_000)}K"
    return str(n)


def rarity(screenings: list[Screening]) -> list[str]:
    """Flags a film you could easily miss: a single showing. (Jordan dropped "One day
    only" for several showings on one day; one clear flag reads better.)"""
    return ["One screening"] if len(screenings) == 1 else []


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
        found = [t for s in self.screenings for t in tags_for(s)]
        # No year, no score and nothing the listing says: that's almost always a
        # one-off event rather than a film, so it gets the general event tag.
        if not found and not self.year and not self.has_score:
            found = ["Event"]
        return sort_tags(found + rarity(self.screenings))

    @property
    def has_score(self) -> bool:
        f = self.film
        return bool(
            f
            and (
                f.letterboxd_rating
                or f.imdb_rating
                or f.rt_score is not None
                or f.metacritic is not None
            )
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
    def shared_note(self) -> str | None:
        """The venue's note when every showing has the same one, to show once up top."""
        notes = {s.note for s in self.screenings}
        return notes.pop() if len(notes) == 1 else None

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
class CalendarDay:
    date: date
    anchor: str | None  # set when there are showings that day
    today: bool


@dataclass
class CalendarMonth:
    title: str
    weeks: list[list[CalendarDay | None]]


def calendar_months(days: list[Day], now: datetime) -> list[CalendarMonth]:
    """Month grids covering every listed day, weeks starting on Sunday."""
    if not days:
        return []
    listed = {d.date: d.anchor for d in days}
    today = now.astimezone(VANCOUVER).date()
    first, last = min(listed), max(listed)
    months = []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        weeks = [
            [CalendarDay(d, listed.get(d), d == today) if d.month == month else None for d in week]
            for week in calendar.Calendar(firstweekday=6).monthdatescalendar(year, month)
        ]
        months.append(CalendarMonth(f"{date(year, month, 1):%B %Y}", weeks))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


@dataclass
class TheatreRun:
    """Back-to-back days at one theatre, shown as one block on a film page."""

    venue: Venue
    days: list[tuple[Day, list[Row]]]


def theatre_runs(days: list[Day]) -> list[TheatreRun]:
    runs: list[TheatreRun] = []
    for day in days:
        for group in day.groups:
            if runs and runs[-1].venue == group.venue:
                runs[-1].days.append((day, group.rows))
            else:
                runs.append(TheatreRun(group.venue, [(day, group.rows)]))
    return runs


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


def spotlight(film_list: list[FilmPage], now: datetime) -> FilmPage | None:
    """The film to feature at the top of the home page: the best-rated one still
    to come today with a backdrop image, or failing that the soonest one."""
    today = now.astimezone(VANCOUVER).date()
    tonight = [
        p
        for p in film_list
        if p.film and p.film.backdrop_url and p.next_showing.local_start.date() == today
    ]
    if tonight:
        return max(tonight, key=lambda p: p.film.letterboxd_rating or 0)
    with_art = [p for p in film_list if p.film and p.film.backdrop_url]
    return min(with_art, key=lambda p: p.next_showing.starts_at) if with_art else None


@dataclass
class Slide:
    page: FilmPage
    label: str
    when: str


def highlights(film_list: list[FilmPage], now: datetime, count: int = 3) -> list[Slide]:
    """The home page hero: tonight's pick, then the standout things coming up in the
    next two weeks (events, film prints, one-offs), best rated first. Only films
    with a backdrop image, so every slide has full art."""
    first = spotlight(film_list, now)
    if not first:
        return []
    today = now.astimezone(VANCOUVER).date()
    soon = today + timedelta(days=14)

    def standout(p: FilmPage) -> str | None:
        tags = p.tags
        return next(
            (t for t in tags if t in EVENTS),
            next((t for t in tags if t in ON_FILM), next((t for t in tags if t in RARE), None)),
        )

    rest = sorted(
        (
            p
            for p in film_list
            if p is not first
            and p.film
            and p.film.backdrop_url
            and p.next_showing.local_start.date() <= soon
        ),
        key=lambda p: (
            standout(p) is None,
            -(p.film.letterboxd_rating or 0),
            p.next_showing.starts_at,
        ),
    )
    on_today = first.next_showing.local_start.date() == today
    slides = [Slide(first, "Tonight" if on_today else "Up next", when(first.next_showing, now))]
    for p in rest[: count - 1]:
        slides.append(Slide(p, standout(p) or "Coming up", when(p.next_showing, now)))
    return slides


def last_day(s: Screening, now: datetime) -> str:
    """today, tomorrow, or a short date: "Ends Tue 20" """
    today = now.astimezone(VANCOUVER).date()
    day = s.local_start.date()
    if day == today:
        return "today"
    if day == today + timedelta(days=1):
        return "tomorrow"
    return f"{day:%a} {day.day}"


# A scrape takes a few minutes, so anything first seen this close to a theatre's debut is baseline.
DEBUT_GRACE = timedelta(hours=1)


def rails(
    film_list: list[FilmPage], now: datetime, debuts: dict[str, datetime] | None = None
) -> list[Rail]:
    today = now.astimezone(VANCOUVER).date()
    soonest = lambda p: p.next_showing.starts_at  # noqa: E731

    on_today = sorted(
        (p for p in film_list if any(s.local_start.date() == today for s in p.screenings)),
        key=soonest,
    )
    this_week = sorted(
        (
            p
            for p in film_list
            if p not in on_today and p.next_showing.local_start.date() <= today + timedelta(days=7)
        ),
        key=soonest,
    )

    # Films that appeared in the last two weeks, newest first. A theatre's first
    # scrape is its baseline, not news, so a newly added theatre doesn't fill the rail.
    if debuts is None:
        debuts = {}
        for p in film_list:
            for s in p.screenings:
                if s.first_seen and (s.venue not in debuts or s.first_seen < debuts[s.venue]):
                    debuts[s.venue] = s.first_seen

    def is_new(p: FilmPage) -> bool:
        seen = [s for s in p.screenings if s.first_seen]
        if not seen:
            return False
        first = min(seen, key=lambda s: s.first_seen)
        debut = debuts.get(first.venue, first.first_seen)
        return first.first_seen > max(debut + DEBUT_GRACE, now - timedelta(days=14))

    just_added = sorted(
        (p for p in film_list if is_new(p)),
        key=lambda p: (-p.added.timestamp(), soonest(p)),
    )

    # A run that ends this week. One-off screenings already carry their own pill.
    last = lambda p: p.last_showing.starts_at  # noqa: E731
    leaving = sorted(
        (
            p
            for p in film_list
            if p.last_showing.local_start.date() <= today + timedelta(days=6)
            and len({s.local_start.date() for s in p.screenings}) > 1
        ),
        key=last,
    )
    on_film = sorted((p for p in film_list if ON_FILM & set(p.tags)), key=soonest)
    events = sorted((p for p in film_list if is_event(p.tags)), key=soonest)
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
    # Long runs: films with plenty of chances to catch them.
    busiest = sorted(
        (p for p in film_list if len(p.screenings) >= 4),
        key=lambda p: (-len(p.screenings), soonest(p)),
    )

    # `why` is kept on each card for reference but not drawn; the rail's title says it.
    # A rail can swap the date line for its own (Leaving soon shows when it ends).
    def cards(pages, why=None, label=None):
        return [
            Card(p, label(p) if label else when(p.next_showing, now), why(p) if why else None)
            for p in pages[:RAIL_LENGTH]
        ]

    found = [
        Rail("On today", cards(on_today), f"showtimes/#d{today:%Y%m%d}"),
        Rail(
            "Leaving soon",
            cards(
                leaving,
                lambda p: f"Ends {last_day(p.last_showing, now)}",
                label=lambda p: f"Ends {last_day(p.last_showing, now)}",
            ),
            "films/?sort=leaving",
        ),
        Rail("This week", cards(this_week), "films/"),
        Rail("Just added", cards(just_added), "films/?sort=added"),
        Rail(
            "On film",
            cards(on_film, lambda p: " and ".join(t for t in p.tags if t in ON_FILM)),
            "films/?tag=on-film",
        ),
        Rail(
            "Events and guests",
            cards(events, lambda p: next(t for t in p.tags if t in EVENTS)),
            "films/?tag=event",
        ),
        Rail(
            "Highly rated",
            # The card already shows the Letterboxd score.
            cards(top),
            "films/?sort=rated",
        ),
        Rail(
            "Popular",
            # Highly rated already shows the acclaimed ones; leave them out here.
            cards(
                [p for p in popular if p not in top[:RAIL_LENGTH]],
                lambda p: f"{compact(p.film.letterboxd_count)} Letterboxd ratings",
            ),
            "films/?sort=popular",
        ),
        Rail(
            "Most screenings",
            cards(busiest, lambda p: f"{len(p.screenings)} screenings"),
            "films/?sort=screenings",
        ),
    ]
    return [r for r in found if r.cards]


# A topic rail on a theatre page needs at least this many films to be worth a row.
MIN_THEATRE_RAIL = 3


def theatre_rails(
    venue: Venue, film_list: list[FilmPage], now: datetime, debuts: dict[str, datetime]
) -> list[Rail]:
    """Poster rows for a theatre page. "Now playing" always has every film here, so
    even a two-film theatre gets a full row. Topic rows (Leaving soon, Events and
    so on) only show when they have enough films and say something new."""
    here = [
        replace(p, screenings=[s for s in p.screenings if s.venue == venue.name])
        for p in film_list
        if any(s.venue == venue.name for s in p.screenings)
    ]
    if not here:
        return []
    by_title = {r.title: r for r in rails(here, now, debuts)}
    everything = sorted(here, key=lambda p: p.next_showing.starts_at)
    playing = Rail(
        "Now playing",
        [Card(p, when(p.next_showing, now)) for p in everything],
        f"films/?venue={venue.slug}",
    )
    found = [playing]
    for title, sort in [
        ("Leaving soon", "leaving"),
        ("Events and guests", "next&tag=event"),
        ("On film", "next&tag=on-film"),
        ("Just added", "added"),
    ]:
        r = by_title.get(title)
        if r and MIN_THEATRE_RAIL <= len(r.cards) < len(here) and len(found) < 3:
            found.append(replace(r, more=f"films/?venue={venue.slug}&sort={sort}"))
    return found


# films.json is read from pages at different depths, so cards are drawn with this
# stand-in for the path to the site root and the browser fills in the real one.
ROOT_MARK = "@root@"


def shelf_index(film_list: list[FilmPage], now: datetime) -> list[dict]:
    """films.json: each film's details plus its finished poster card, so the
    watchlist shelf drawn in the browser looks exactly like every other card."""
    parts = env.get_template("_parts.html").module
    index = personal.films_index(film_list)
    for entry, page in zip(index, film_list, strict=True):
        entry["card"] = str(parts.film_card(page, ROOT_MARK, when(page.next_showing, now))).strip()
    return index


def updated_label(now: datetime) -> str:
    local = now.astimezone(VANCOUVER)
    return f"{local:%a %b} {local.day}, {clock(now)}"


def pages(conn: Connection, now: datetime) -> dict[str, str]:
    screenings = db.upcoming(conn, now)
    films = db.films_by_key(conn)
    page_of = film_pages(screenings, films)
    film_list = list({id(p): p for p in page_of.values()}.values())
    days = group_days(screenings, page_of, films, now)
    debuts = db.venue_debuts(conn)
    common = {"updated": updated_label(now), "venues": VENUES}

    def render(template: str, path: str, root: str | None = None, **context) -> str:
        root = "../" * path.count("/") if root is None else root
        return env.get_template(template).render(root=root, path=path, **common, **context)

    # The Events chip already covers the plain Event tag, so it isn't listed twice.
    filter_tags = sort_tags({t for p in film_list for t in p.tags} - {"Event"})
    out = {
        "index.html": render(
            "index.html",
            "index.html",
            rails=rails(film_list, now, debuts),
            slides=highlights(film_list, now),
        ),
        "showtimes/index.html": render(
            "showtimes.html",
            "showtimes/index.html",
            days=days,
            months=calendar_months(days, now),
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
        out[path] = render(
            "film.html", path, page=page, film=page.film, runs=theatre_runs(page_days)
        )

    out["theatres/index.html"] = render("theatres.html", "theatres/index.html", current="theatres")
    out["films.json"] = json.dumps(shelf_index(film_list, now), separators=(",", ":"))
    synced = []
    for user in profiles.SYNCED:
        stored = db.load_profile(conn, user)
        if not stored:
            continue
        synced.append(user)
        data = personal.profile_json(stored[0], film_list, now)
        out[f"me/{user}.json"] = json.dumps(data, separators=(",", ":"))
        out[f"me/{user}/watchlist.ics"] = personal.watchlist_calendar(
            stored[0], film_list, venue_for, now
        )
    out["me/index.html"] = render("me.html", "me/index.html", synced=synced)
    out["about/index.html"] = render("about.html", "about/index.html")
    for venue in VENUES:
        path = f"theatres/{venue.slug}/index.html"
        mine = [s for s in screenings if s.venue == venue.name]
        venue_days = group_days(mine, page_of, films, now)
        out[path] = render(
            "venue.html",
            path,
            venue=venue,
            spec_fields=shown_specs(),
            # What's on the schedule here right now: events and formats from the listings.
            listed=[
                t for t in sort_tags({t for s in mine for t in tags_for(s)}) if kind(t) != "rare"
            ],
            current="theatres",
            days=venue_days,
            months=calendar_months(venue_days, now),
            rails=theatre_rails(venue, film_list, now, debuts),
        )

    # GitHub Pages shows 404.html for any missing address, at any depth, so its
    # links use the full site address instead of relative paths.
    site_url = env.globals["site_url"]
    out["404.html"] = render("404.html", "404.html", root=site_url, films=by_next[:6])
    out["sitemap.xml"] = sitemap(site_url, [p for p in out if p.endswith("index.html")])
    return out


def sitemap(site_url: str, paths: list[str]) -> str:
    """Every page, so search engines find films and theatres, not just the home page."""
    urls = "".join(
        f"  <url><loc>{site_url}{p.removesuffix('index.html')}</loc></url>\n" for p in sorted(paths)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}</urlset>\n"
    )


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
