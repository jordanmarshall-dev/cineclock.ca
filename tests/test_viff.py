from datetime import UTC, datetime

import httpx
import pytest

from cineclock.scrapers import viff

ROOM = "viff-centre-viff-cinema"


def test_parse_nonce_from_real_calendar_page(fixture_text):
    assert viff.parse_nonce(fixture_text("viff/calendar.html")) == "5282647b44"


def test_parse_nonce_missing():
    assert viff.parse_nonce("<html>no settings here</html>") is None


def test_parse_instances_skips_live_shows(fixture_json):
    screenings = viff.parse_instances(fixture_json("viff/instances_2026-10.json"))
    assert [(s.title, s.year, s.note) for s in screenings] == [
        ("Day of Wrath", None, None),
        ("The Thing", 1982, None),
        ("Shrek", None, "Halloween Family Show"),
        ("Day of Wrath", None, None),
    ]


def test_screens_become_separate_venues(fixture_json):
    screenings = viff.parse_instances(fixture_json("viff/instances_2026-10.json"))
    venues = {s.title: s.venue for s in screenings}
    assert venues["Day of Wrath"] == "VIFF Centre"
    assert venues["The Thing"] == "VIFF Lochmaddy"


def test_events_at_other_locations_are_skipped():
    item = {"start": "2026-12-05T19:00:00", "eventType": "Film", "title": card()}
    item["resourceId"] = "roundhouse-community-arts-recreation-centre"
    assert viff.parse_instances([item]) == []


def test_parse_instances_fields(fixture_json):
    first = viff.parse_instances(fixture_json("viff/instances_2026-10.json"))[0]
    assert first.venue == "VIFF Centre"
    assert first.starts_at == datetime(2026, 10, 18, 18, 0, tzinfo=UTC)
    assert first.local_start.hour == 11
    assert first.url == "https://viff.org/whats-on/day-of-wrath/book/pCGMwCW36F"
    assert first.info_url == "https://viff.org/whats-on/day-of-wrath/"


def card(time_tag=""):
    return (
        '<h3 class="c-calendar-instance__title">Cure</h3>'
        f"{time_tag}"
        '<a class="c-btn c-btn--primary" href="https://viff.org/whats-on/cure/book/x">Book Now</a>'
        '<a class="c-btn c-btn--ghost" href="https://viff.org/whats-on/cure/">More Info</a>'
    )


def test_bare_start_time_is_read_as_vancouver_time():
    item = {
        "start": "2026-12-05T19:00:00",
        "eventType": "Film",
        "title": card(),
        "resourceId": ROOM,
    }
    [s] = viff.parse_instances([item])
    # Permanent UTC-7, so 7pm in December is 2am UTC.
    assert s.starts_at == datetime(2026, 12, 6, 2, 0, tzinfo=UTC)


def test_time_tag_wins_over_bare_start():
    tag = '<time datetime="2026-12-05T21:00:00-07:00">9 pm</time>'
    item = {
        "start": "2026-12-05T19:00:00",
        "eventType": "Film",
        "title": card(tag),
        "resourceId": ROOM,
    }
    [s] = viff.parse_instances([item])
    assert s.local_start.hour == 21


def test_card_without_title_is_skipped():
    item = {
        "start": "2026-12-05T19:00:00",
        "eventType": "Film",
        "title": "<div>nothing</div>",
        "resourceId": ROOM,
    }
    assert viff.parse_instances([item]) == []


def test_parse_film_page(fixture_text):
    details = viff.parse_film_page(fixture_text("viff/film_day-of-wrath.html"))
    assert details.year == 1943
    assert details.poster_url.startswith("https://images.viff.org/uploads/2025/12/DayOfWrath.jpg")


def test_parse_film_page_without_details():
    assert viff.parse_film_page("<html></html>") == viff.FilmDetails()


def fake_viff(fixture_text, fixture_json, calls):
    def handler(request):
        calls.append(request)
        url = str(request.url)
        if url == viff.CALENDAR_URL:
            return httpx.Response(200, text=fixture_text("viff/calendar.html"))
        if url == viff.INSTANCES_URL:
            if request.headers.get("X-WP-Nonce") != "5282647b44":
                return httpx.Response(403, json={"code": "forbidden"})
            return httpx.Response(200, json=fixture_json("viff/instances_2026-10.json"))
        if url == "https://viff.org/whats-on/day-of-wrath/":
            return httpx.Response(200, text=fixture_text("viff/film_day-of-wrath.html"))
        if url == "https://viff.org/whats-on/the-thing/":
            return httpx.Response(200, text=fixture_text("viff/film_the-thing.html"))
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_scrape_sends_token_and_adds_details(fixture_text, fixture_json):
    calls = []
    with fake_viff(fixture_text, fixture_json, calls) as client:
        screenings = viff.scrape(client)

    by_title = {s.title: s for s in screenings}
    assert by_title["Day of Wrath"].year == 1943
    assert by_title["The Thing"].year == 1982
    assert by_title["The Thing"].poster_url.startswith("https://images.viff.org/")
    # Day of Wrath plays twice but its page is fetched once
    pages = [str(c.url) for c in calls if "/whats-on/day-of-wrath/" == c.url.path]
    assert len(pages) == 1


def test_scrape_drops_past_screenings(fixture_text, fixture_json):
    now = datetime(2026, 10, 19, tzinfo=UTC)
    with fake_viff(fixture_text, fixture_json, []) as client:
        screenings = viff.scrape(client, now=now)
    assert all(s.starts_at >= now for s in screenings)
    assert len(screenings) == 3


def test_scrape_fails_clearly_without_token():
    def handler(request):
        return httpx.Response(200, text="<html>redesigned</html>")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError, match="no API token"):
            viff.scrape(client)
