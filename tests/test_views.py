from datetime import UTC, date, datetime, timedelta

import pytest

from cineclock.models import Screening
from cineclock.views import clock, day_label, group_by_day

# 1am Oct 18 in Vancouver
NOW = datetime(2026, 10, 18, 8, 0, tzinfo=UTC)


def show(title, local_hour, day=18, venue="The Rio", **extra):
    # Vancouver is UTC-7 year round now, so local 7pm is 2am UTC the next day.
    starts = datetime(2026, 10, day, local_hour, 0, tzinfo=UTC) + timedelta(hours=7)
    return Screening(venue, title, starts, f"https://tix/{title}/{day}/{local_hour}", **extra)


@pytest.mark.parametrize(
    "hour, minute, expected",
    [
        (0, 0, "12:00 am"),
        (9, 5, "9:05 am"),
        (12, 0, "12:00 pm"),
        (19, 30, "7:30 pm"),
        (23, 45, "11:45 pm"),
    ],
)
def test_clock(hour, minute, expected):
    local = datetime(2026, 10, 18, hour, minute, tzinfo=UTC) + timedelta(hours=7)
    assert clock(local) == expected


def test_day_labels():
    today = date(2026, 10, 18)
    assert day_label(today, today) == "Today Oct 18"
    assert day_label(date(2026, 10, 19), today) == "Tomorrow Oct 19"
    assert day_label(date(2026, 10, 20), today) == "Tuesday Oct 20"
    assert day_label(date(2026, 11, 6), today) == "Friday Nov 6"


def test_late_show_belongs_to_its_local_day():
    # 11:45pm in Vancouver is already the next day in UTC.
    [day] = group_by_day([show("Rocky Horror", 23, day=23)], NOW)
    assert day.date == date(2026, 10, 23)


def test_days_are_in_order():
    days = group_by_day([show("B", 19, day=20), show("A", 19, day=18)], NOW)
    assert [d.label for d in days] == ["Today Oct 18", "Tuesday Oct 20"]


def test_same_film_twice_a_day_shares_one_entry():
    [day] = group_by_day([show("Rocky Horror", 20, day=24), show("Rocky Horror", 23, day=24)], NOW)
    [film] = day.venues[0].films
    assert [clock(s.starts_at) for s in film.showtimes] == ["8:00 pm", "11:00 pm"]


def test_different_notes_stay_separate():
    shows = [show("Stalker", 18, note="35mm"), show("Stalker", 21, note="4K Restoration")]
    [day] = group_by_day(shows, NOW)
    assert [f.note for f in day.venues[0].films] == ["35mm", "4K Restoration"]


def test_venues_follow_the_set_order():
    shows = [
        show("Mirror", 18, venue="VIFF Centre"),
        show("Pulse", 18, venue="The Cinematheque"),
        show("Stalker", 19, venue="The Rio"),
        show("Tony", 20, venue="The Park"),
    ]
    [day] = group_by_day(shows, NOW)
    assert [v.name for v in day.venues] == [
        "The Rio",
        "The Park",
        "The Cinematheque",
        "VIFF Centre",
    ]


def test_no_screenings_means_no_days():
    assert group_by_day([], NOW) == []
