"""The rows of posters: the home page's spotlight and rails, and the rows at the
top of each theatre page. Each picks and orders films for one idea (on today,
leaving soon, on film, just added...) from the FilmPages in listings.py.
"""

from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from markupsafe import Markup

from cineclock.listings import RARE, FilmPage, compact, last_day, when
from cineclock.models import VANCOUVER
from cineclock.tags import EVENTS, ON_FILM, is_event
from cineclock.timefmt import stamp
from cineclock.venues import Venue

RAIL_LENGTH = 15
# Below this many Letterboxd ratings, an average says little.
MIN_RATINGS_FOR_TOP = 1000


@dataclass
class Card:
    """A poster in one of the home page's rows. `why` says why it's in that row."""

    page: FilmPage
    next_label: str
    why: str | None = None
    ends: bool = False

    @property
    def stamped(self) -> Markup:
        if self.ends:
            return stamp(self.next_label, self.page.last_showing.starts_at, "ends")
        return stamp(self.next_label, self.page.next_showing.starts_at, "card")


@dataclass
class Rail:
    title: str
    cards: list[Card]
    more: str  # where "See all" goes, relative to the site root


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

    @property
    def stamped(self) -> Markup:
        return stamp(self.when, self.page.next_showing.starts_at, "card")


def highlights(film_list: list[FilmPage], now: datetime, count: int = 3) -> list[Slide]:
    """The home page hero: tonight's pick, then the standout things coming up in the
    next two weeks (events, film prints, one-offs), best rated first, spread across
    the theatres so one busy venue doesn't fill it. Only films with a backdrop
    image, so every slide has full art. The page shuffles them on each visit."""
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
    shown = Counter(v.slug for v in first.venues)
    while rest and len(slides) < count:
        # The best pick from whichever theatre has had the fewest slides so far.
        p = min(rest, key=lambda p: min((shown[v.slug] for v in p.venues), default=0))
        rest.remove(p)
        shown.update(v.slug for v in p.venues)
        slides.append(Slide(p, standout(p) or "Coming up", when(p.next_showing, now)))
    return slides


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
    # Leaving soon swaps the date line for when the run ends.
    def cards(pages, why=None, ends=False):
        return [
            Card(
                p,
                f"Ends {last_day(p.last_showing, now)}" if ends else when(p.next_showing, now),
                why(p) if why else None,
                ends,
            )
            for p in pages[:RAIL_LENGTH]
        ]

    found = [
        Rail("On today", cards(on_today), f"showtimes/#d{today:%Y%m%d}"),
        Rail(
            "Leaving soon",
            cards(
                leaving,
                lambda p: f"Ends {last_day(p.last_showing, now)}",
                ends=True,
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
