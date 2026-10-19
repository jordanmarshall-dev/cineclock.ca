"""How times and days read on the site, always in Vancouver time."""

from datetime import date, datetime, timedelta

from markupsafe import Markup

from cineclock.models import VANCOUVER


def clock(dt: datetime) -> str:
    """7:30 pm, in Vancouver time."""
    local = dt.astimezone(VANCOUVER)
    hour = local.hour % 12 or 12
    return f"{hour}:{local.minute:02d} {'am' if local.hour < 12 else 'pm'}"


def day_label(day: date, today: date) -> str:
    if day == today:
        return f"Today, {day:%b} {day.day}"
    if day == today + timedelta(days=1):
        return f"Tomorrow, {day:%b} {day.day}"
    return f"{day:%A}, {day:%b} {day.day}"


def short_day(day: date, today: date) -> str:
    if day == today:
        return "Today"
    if day == today + timedelta(days=1):
        return "Tomorrow"
    # Past this month the strip needs the month too, or "Sun 1" could be any month.
    if (day.year, day.month) != (today.year, today.month):
        return f"{day:%a} {day:%b} {day.day}"
    return f"{day:%a} {day.day}"


def stamp(text: str, at: date, fmt: str) -> Markup:
    """A date label as it read at build time, wrapped with the real date. Pages are
    rebuilt every few hours, so static/when.js redoes Today and Tomorrow from the
    visitor's own day."""
    if isinstance(at, datetime):
        value = at.astimezone(VANCOUVER).strftime("%Y-%m-%dT%H:%M")
    else:
        value = at.isoformat()
    return Markup('<time datetime="{}" data-fmt="{}">{}</time>').format(value, fmt, text)
