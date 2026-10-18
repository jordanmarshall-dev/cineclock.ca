"""Shape saved screenings into what the page shows: days, then venues, then films."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from itertools import groupby

from cineclock.models import VANCOUVER, Screening


@dataclass
class Film:
    title: str
    year: int | None
    note: str | None
    poster_url: str | None
    info_url: str | None
    showtimes: list[Screening] = field(default_factory=list)


@dataclass
class Venue:
    name: str
    films: list[Film]


@dataclass
class Day:
    date: date
    label: str
    venues: list[Venue]


def day_label(day: date, today: date) -> str:
    if day == today:
        return f"Today {day:%b} {day.day}"
    if day == today + timedelta(days=1):
        return f"Tomorrow {day:%b} {day.day}"
    return f"{day:%A %b} {day.day}"


def clock(dt: datetime) -> str:
    """7:30 pm, in Vancouver time."""
    local = dt.astimezone(VANCOUVER)
    hour = local.hour % 12 or 12
    return f"{hour}:{local.minute:02d} {'am' if local.hour < 12 else 'pm'}"


def group_by_day(screenings: list[Screening], now: datetime) -> list[Day]:
    today = now.astimezone(VANCOUVER).date()
    ordered = sorted(screenings, key=lambda s: s.starts_at)
    days = []
    for day, day_shows in groupby(ordered, key=lambda s: s.local_start.date()):
        day_shows = list(day_shows)
        venues = []
        for name in sorted({s.venue for s in day_shows}):
            films: dict[tuple, Film] = {}
            # Two showings of the same film on the same day share one entry.
            for s in day_shows:
                if s.venue != name:
                    continue
                key = (s.title, s.year, s.note)
                if key not in films:
                    films[key] = Film(s.title, s.year, s.note, s.poster_url, s.info_url)
                films[key].showtimes.append(s)
            venues.append(Venue(name, list(films.values())))
        days.append(Day(day, day_label(day, today), venues))
    return days
