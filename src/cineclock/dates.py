"""Dates that venues list without a year, like "Sun, Oct 18" or "Friday 23, October"."""

from datetime import datetime

from cineclock.models import VANCOUVER

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def month_number(name: str) -> int | None:
    key = name.strip(" .").lower()[:3]
    return MONTHS.index(key) + 1 if key in MONTHS else None


def hour_24(hour: int, ampm: str) -> int:
    return hour % 12 + (12 if ampm.lower() == "pm" else 0)


def resolve(
    month: int, day: int, hour: int, minute: int, weekday: str | None, now: datetime
) -> datetime | None:
    """Pick the year for a date listed without one, as Vancouver time.

    The year is the one where the date lands on the listed weekday. A date
    only falls on the same weekday once in any three years, so checking last
    year, this year and next year finds exactly one match. Without a weekday,
    the date closest to now wins.
    """
    today = now.astimezone(VANCOUVER)
    candidates = []
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidates.append(datetime(year, month, day, hour, minute, tzinfo=VANCOUVER))
        except ValueError:
            continue  # Feb 29 in a non-leap year
    if not candidates:
        return None
    key = (weekday or "").lower()[:3]
    on_weekday = [c for c in candidates if WEEKDAYS[c.weekday()] == key]
    return min(on_weekday or candidates, key=lambda c: abs(c - today))
