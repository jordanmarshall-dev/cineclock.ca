from datetime import UTC, datetime, timedelta, timezone

import pytest

from cineclock.models import Screening


def make(starts_at):
    return Screening(venue="Rio", title="Stalker", starts_at=starts_at, url="https://example.com")


def offset(hours):
    return timezone(timedelta(hours=hours))


def test_naive_time_is_rejected():
    with pytest.raises(ValueError):
        make(datetime(2026, 10, 18, 19, 0))


def test_start_time_is_stored_in_utc():
    s = make(datetime(2026, 10, 18, 19, 0, tzinfo=offset(-7)))
    assert s.starts_at == datetime(2026, 10, 19, 2, 0, tzinfo=UTC)
    assert s.starts_at.tzinfo == UTC


def test_same_moment_from_different_offsets_is_equal():
    a = make(datetime(2026, 10, 18, 19, 0, tzinfo=offset(-7)))
    b = make(datetime(2026, 10, 19, 2, 0, tzinfo=UTC))
    assert a == b


def test_old_winter_screening_shows_standard_time():
    # Before 2026, B.C. still fell back to UTC-8 in winter.
    s = make(datetime(2025, 12, 15, 3, 0, tzinfo=UTC))
    assert s.local_start.hour == 19
    assert s.local_start.utcoffset() == timedelta(hours=-8)


def test_last_clock_change_in_march_2026():
    before = make(datetime(2026, 3, 7, 3, 0, tzinfo=UTC))
    after = make(datetime(2026, 3, 9, 2, 0, tzinfo=UTC))
    assert before.local_start.utcoffset() == timedelta(hours=-8)
    assert after.local_start.utcoffset() == timedelta(hours=-7)
    assert before.local_start.hour == after.local_start.hour == 19


def test_clocks_do_not_fall_back_in_november_2026():
    # B.C. moved to permanent UTC-7, so a 7pm show stays at 7pm on both sides of Nov 1.
    before = make(datetime(2026, 11, 1, 2, 0, tzinfo=UTC))
    after = make(datetime(2026, 11, 3, 2, 0, tzinfo=UTC))
    assert before.local_start.hour == after.local_start.hour == 19
    assert after.local_start.utcoffset() == timedelta(hours=-7)


def test_winter_2027_stays_on_utc_minus_7():
    s = make(datetime(2027, 1, 16, 2, 0, tzinfo=UTC))
    assert s.local_start.hour == 19
    assert s.local_start.utcoffset() == timedelta(hours=-7)
