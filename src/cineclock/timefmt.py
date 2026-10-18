"""How times and days read on the site, always in Vancouver time."""

from datetime import date, datetime, timedelta

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
    return f"{day:%a} {day.day}"
