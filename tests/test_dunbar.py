from datetime import UTC, datetime

import httpx

from cineclock.models import VANCOUVER
from cineclock.scrapers import dunbar

# Saved page is from Oct 18, 2026
NOW = datetime(2026, 10, 18, 8, 0, tzinfo=UTC)


def parsed(fixture_text):
    return dunbar.parse_sessions(fixture_text("dunbar/sessions.html"), NOW)


def test_every_session_on_the_page(fixture_text):
    screenings = parsed(fixture_text)
    assert len(screenings) == 38
    assert {s.title for s in screenings} == {"Primetime", "Wildwood"}
    # The page lists sessions by date and by film; we only read one half
    assert len({s.url for s in screenings}) == 38


def test_first_session_fields(fixture_text):
    first = parsed(fixture_text)[0]
    assert first.venue == "The Dunbar" and first.room == "dunbar-main"
    assert first.title == "Primetime"
    assert first.local_start == datetime(2026, 10, 18, 16, 0, tzinfo=VANCOUVER)
    assert first.url.startswith("https://ticketing.uswest.veezi.com/purchase/8433?")
    assert first.poster_url.startswith("https://ticketing.uswest.veezi.com/Media/Poster?")


def test_times_are_stored_in_utc(fixture_text):
    first = parsed(fixture_text)[0]
    assert first.starts_at == datetime(2026, 10, 18, 23, 0, tzinfo=UTC)


def test_missing_pieces_are_skipped():
    page = """
    <div id="sessionsByFilmConent">
      <div class="film">
        <div class="date-container"><div class="date">Friday 23, October</div></div></div>
      <div class="film"><h3 class="title">No Dates</h3></div>
      <div class="film"><h3 class="title">Bad Time</h3>
        <div class="date-container"><div class="date">Friday 23, October</div>
          <div class="session-times"><a href="/purchase/1">Sold out</a></div></div></div>
    </div>"""
    assert dunbar.parse_sessions(page, NOW) == []


def test_january_dates_roll_into_next_year():
    page = """
    <div id="sessionsByFilmConent"><div class="film"><h3 class="title">Jaws (1975)</h3>
      <div class="date-container"><div class="date">Friday 15, January</div>
        <div class="session-times"><a href="/purchase/9">7:00 PM</a></div></div></div></div>"""
    [s] = dunbar.parse_sessions(page, NOW)
    assert s.local_start == datetime(2027, 1, 15, 19, 0, tzinfo=VANCOUVER)
    assert (s.title, s.year) == ("Jaws", 1975)


def test_scrape_drops_past_sessions(fixture_text):
    later = datetime(2026, 10, 19, 7, 0, tzinfo=UTC)

    def handler(request):
        assert request.url.params["siteToken"]
        return httpx.Response(200, text=fixture_text("dunbar/sessions.html"))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        screenings = dunbar.scrape(client, now=later)
    assert screenings and all(s.starts_at >= later for s in screenings)
    assert len(screenings) < 38
