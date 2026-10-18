from datetime import UTC, datetime

import httpx
import pytest

from cineclock.models import VANCOUVER
from cineclock.scrapers import park

# Saved pages are from 1:50am Oct 18, 2026
NOW = datetime(2026, 10, 18, 8, 50, tzinfo=UTC)


def local(*args):
    return datetime(*args, tzinfo=VANCOUVER)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Sun, Oct 18, 1:15 pm", local(2026, 10, 18, 13, 15)),
        ("Sat, Oct 24, 10:00 am", local(2026, 10, 24, 10, 0)),
        ("Sat, Oct 24, 11:00 pm", local(2026, 10, 24, 23, 0)),
        ("Sun, Nov 1, 12:45 pm", local(2026, 11, 1, 12, 45)),
        ("Mon, Dec 21, 12:30 am", local(2026, 12, 21, 0, 30)),
        # Listings in January are next year: Jan 15 is a Friday in 2027
        ("Fri, Jan 15, 7:00 pm", local(2027, 1, 15, 19, 0)),
        # The weekday decides even when another year would be closer
        ("Thu, Oct 16, 7:00 pm", local(2025, 10, 16, 19, 0)),
        # Backup tile format: no weekday, so the closest date wins
        ("Nov 08, 12:00 PM", local(2026, 11, 8, 12, 0)),
        ("Old format: 6:20pm - Thursday", None),
        ("De Gaulle - Résistance & Liberté", None),
        ("Foo 12, 7:00 pm", None),
    ],
)
def test_parse_date(text, expected):
    assert park.parse_date(text, NOW) == expected


def test_parse_real_first_page(fixture_text):
    screenings, next_url = park.parse_page(fixture_text("park/page1.html"), NOW)
    assert next_url == "https://tickets.theparktheatre.ca/?page=2"
    # 60 listings, minus the De Gaulle bundle that has no date
    assert len(screenings) == 59

    tony = screenings[0]
    assert (tony.title, tony.year, tony.note) == ("Tony", 2026, None)
    assert tony.local_start == local(2026, 10, 18, 13, 15)
    assert tony.url == "https://tickets.theparktheatre.ca/events/45549-tony"
    assert tony.poster_url.endswith("/45549/original/tony-movie-poster.jpg")


def test_notes_and_years_from_real_page(fixture_text):
    screenings, _ = park.parse_page(fixture_text("park/page1.html"), NOW)
    found = {(s.title, s.year, s.note) for s in screenings}
    assert ("Dune: Part Three", 2026, "Presented in 70mm") in found
    assert ("The Fly", 1986, "40th Anniversary Screening") in found
    assert ("Ken Russell's 'The Devils'", 1971, None) in found


def test_listing_without_ticket_button_uses_its_event_page(fixture_text):
    screenings, _ = park.parse_page(fixture_text("park/page1.html"), NOW)
    cereal = next(s for s in screenings if s.title.startswith("The Saturday Morning"))
    assert cereal.url.startswith("https://tickets.theparktheatre.ca/events/45473-")


def test_last_page_has_no_next(fixture_text):
    screenings, next_url = park.parse_page(fixture_text("park/page2.html"), NOW)
    assert next_url is None
    assert len(screenings) == 3


def test_backup_date_tile_is_used():
    html = """
    <div class="single-event">
      <div class="date-preview"><p>Nov</p><p>08</p><p>12:00 PM</p></div>
      <p class="event-date">De Gaulle - Liberté</p>
      <p class="event-headline">De Gaulle - Liberté</p>
      <a class="image-link" href="/events/1-de-gaulle"></a>
    </div>
    """
    [s] = park.parse_page(html, NOW)[0]
    assert s.local_start == local(2026, 11, 8, 12, 0)


def fake_park(pages, calls):
    def handler(request):
        calls.append(request)
        if "text/html" not in request.headers.get("Accept", ""):
            return httpx.Response(406)
        page = request.url.params.get("page", "1")
        return httpx.Response(200, text=pages[page])

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_scrape_follows_pages_and_drops_past_shows(fixture_text):
    pages = {"1": fixture_text("park/page1.html"), "2": fixture_text("park/page2.html")}
    calls = []
    later = datetime(2026, 10, 19, 7, 0, tzinfo=UTC)  # midnight Oct 19 in Vancouver
    with fake_park(pages, calls) as client:
        screenings = park.scrape(client, now=later)
    assert len(calls) == 2
    assert all(s.starts_at >= later for s in screenings)
    # Oct 18's four showings are gone; 59 + 3 - 4
    assert len(screenings) == 58


def test_scrape_stops_if_pages_never_end():
    page = '<a class="next_page" href="/?page=2">NEXT</a>'
    with fake_park({"1": page, "2": page}, calls := []) as client:
        assert park.scrape(client, now=NOW) == []
    assert len(calls) == park.MAX_PAGES
