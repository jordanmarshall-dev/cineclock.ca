import json
from datetime import UTC, datetime

import httpx

from cineclock.scrapers import FilmDetails, rio


def test_parse_listings_skips_live_events(fixture_json):
    screenings = rio.parse_listings(fixture_json("rio/listings.json"))
    assert [s.title for s in screenings] == ["John Woo's 'A Better Tomorrow'", "Beat Street"]


def test_parse_listings_fields(fixture_json):
    first = rio.parse_listings(fixture_json("rio/listings.json"))[0]
    assert first.venue == "The Rio"
    assert first.note == "40th Anniversary Restoration"
    # "2026-05-31T19:00:00-07:00" is 2am UTC the next day
    assert first.starts_at == datetime(2026, 6, 1, 2, 0, tzinfo=UTC)
    assert first.local_start.hour == 19
    assert first.url.startswith("https://riotheatretickets.ca/events/41803")
    assert first.info_url == "https://riotheatre.ca/movie/a-better-tomorrow-2025-restoration/"


def test_parse_listings_falls_back_to_film_page_without_ticket_link():
    item = {
        "event": {"title": "Stalker", "link": "https://riotheatre.ca/movie/stalker/"},
        "start_time": "2026-11-05T19:00:00-07:00",
        "tickets_link": "",
    }
    assert rio.parse_listings([item])[0].url == "https://riotheatre.ca/movie/stalker/"


def test_parse_listings_empty():
    assert rio.parse_listings([]) == []


def test_parse_live_listings(fixture_json):
    # Real response from Oct 2026, including a Q&A note and a live event
    screenings = rio.parse_listings(fixture_json("rio/listings_2026-10.json"))
    assert [(s.title, s.note) for s in screenings] == [
        ("Musk", None),
        ("Traces of Home", "With Filmmakers Dr. Gabor Maté & Colette Ghunim Q&A"),
        ("Scream", "30th Anniversary Screening"),
    ]
    assert screenings[0].local_start.strftime("%a %b %d %H:%M") == "Sun Oct 18 12:30"


def test_parse_film_page(fixture_text):
    details = rio.parse_film_page(fixture_text("rio/movie_musk.html"))
    assert details.year == 2026
    assert details.poster_url == (
        "https://riotheatre.ca/wp-content/uploads/2026/10/"
        "EP_Musk_Cineplex_Traditional_Screen_768x1280-scaled.jpg"
    )


def test_parse_film_page_with_comma_free_credits(fixture_text):
    details = rio.parse_film_page(fixture_text("rio/movie_scream.html"))
    assert details.year == 1996
    assert details.poster_url.endswith(".jpg")


def test_parse_film_page_without_details():
    details = rio.parse_film_page("<html><body>Coming soon</body></html>")
    assert details == FilmDetails()


def fake_rio(listings, pages, calls=None):
    """A stand-in for the Rio's website, so scrape() runs without the network."""

    def handler(request):
        if calls is not None:
            calls.append(str(request.url))
        if request.url.path == "/wp-json/barker/v1/listings":
            return httpx.Response(200, json=listings)
        url = str(request.url)
        if url in pages:
            return httpx.Response(200, text=pages[url])
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_scrape_adds_year_and_poster(fixture_json, fixture_text):
    page = fixture_text("rio/movie_musk.html")
    pages = {"https://riotheatre.ca/movie/beat-street/": page}
    with fake_rio(fixture_json("rio/listings.json"), pages) as client:
        screenings = rio.scrape(client)

    beat_street = next(s for s in screenings if s.title == "Beat Street")
    assert beat_street.year == 2026
    assert beat_street.poster_url.endswith("768x1280-scaled.jpg")


def test_scrape_survives_a_missing_film_page(fixture_json):
    with fake_rio(fixture_json("rio/listings.json"), pages={}) as client:
        screenings = rio.scrape(client)
    assert len(screenings) == 2
    assert all(s.year is None and s.poster_url is None for s in screenings)


def test_scrape_fetches_each_film_page_once(fixture_json):
    listings = fixture_json("rio/listings.json")
    repeat = json.loads(json.dumps(listings[1]))
    repeat["start_time"] = "2026-06-01T21:30:00-07:00"
    calls = []
    with fake_rio(listings + [repeat], pages={}, calls=calls) as client:
        screenings = rio.scrape(client)
    assert len(screenings) == 3
    assert sum("/movie/beat-street/" in c for c in calls) == 1


def test_scrape_asks_for_the_next_60_days(fixture_json):
    calls = []
    now = datetime(2026, 10, 18, 8, 0, tzinfo=UTC)
    with fake_rio([], pages={}, calls=calls) as client:
        rio.scrape(client, now=now)
    assert "start_date=2026-10-18T08%3A00%3A00%2B00%3A00" in calls[0]
    assert "end_date=2026-12-17T08%3A00%3A00%2B00%3A00" in calls[0]
