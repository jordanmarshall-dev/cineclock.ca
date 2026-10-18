from datetime import UTC, datetime, timedelta

import httpx
import pytest

from cineclock import db, prices, scrape
from cineclock.venues import BY_NAME, Price

NOW = datetime(2026, 10, 18, 20, 0, tzinfo=UTC)


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    yield connection
    connection.close()


def amounts(found):
    return [(p.label, p.amount) for p in found.tickets + found.deals]


def test_viff_prices_from_its_table(fixture_text):
    found = prices.parse_viff(fixture_text("prices/viff.html"))
    assert amounts(found) == [
        ("Adult", "$17 / $15"),
        ("Senior or student", "$15 / $13"),
        ("VIFF+ member", "$14 / $12"),
        ("VIFF+ Premium or under 25", "$12 / $10"),
        ("Accessible", "$12 / $10"),
        ("VIFF+ membership", "From $49 a year"),
    ]
    assert found.columns == "VIFF Cinema / Lochmaddy Studio Theatre"


def test_rio_and_park_prices(fixture_text):
    page = fixture_text("prices/rio.html")
    assert amounts(prices.parse_rio(page)) == [
        ("Adult", "$16"),
        ("Member, senior or student", "$13"),
        ("Rio and Park membership", "$30 a year"),
    ]
    park = prices.parse_park(page)
    assert amounts(park) == [("Rio and Park membership", "$30 a year")]
    assert park.deals[0].detail.startswith("$3 off regular films at both theatres")


def test_cinematheque_prices_and_packs(fixture_text):
    found = prices.parse_cinematheque(
        fixture_text("prices/cinematheque_visit.html"),
        fixture_text("prices/cinematheque_packs.html"),
    )
    assert amounts(found) == [
        ("General", "$15"),
        ("Senior", "$13"),
        ("Student", "$11"),
        ("First Nations, Inuit and Métis", "Free"),
        ("5-film pack", "$55"),
        ("10-film pack", "$100"),
        ("50-film pack", "$450"),
    ]
    assert found.tickets[0].detail == "18 and over"
    assert found.deals[2].detail == "$9 a film"


def test_a_page_that_changed_shape_gives_nothing():
    page = "<html><body><p>Tickets are on sale now!</p></body></html>"
    assert prices.parse_viff(page) is None
    assert prices.parse_rio(page) is None
    assert prices.parse_park(page) is None
    assert prices.parse_cinematheque(page, page) is None


def test_prices_round_trip_through_the_database(conn, fixture_text):
    found = prices.parse_viff(fixture_text("prices/viff.html"))
    db.save_prices(conn, "VIFF Centre", prices.to_json(found), NOW)
    data, fetched = db.load_prices(conn)["VIFF Centre"]
    assert prices.from_json(data) == found and fetched == NOW


def pages_client(pages):
    def handler(request):
        page = pages.get(str(request.url))
        return httpx.Response(200, text=page) if page else httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_refresh_reads_once_a_month_and_keeps_the_last_good_prices(conn, fixture_text):
    viff = fixture_text("prices/viff.html")
    with pages_client({prices.VIFF_URL: viff}) as client:
        scrape.refresh_prices(conn, client, NOW)
    stored = db.load_prices(conn)
    assert set(stored) == {"VIFF Centre"}  # the other pages 404ed; nothing saved for them
    assert prices.from_json(stored["VIFF Centre"][0]).checked == "Oct 18, 2026"

    # A week later nothing is re-read, even though the page has broken.
    broken = "<p>Coming soon</p>"
    with pages_client({prices.VIFF_URL: broken}) as client:
        scrape.refresh_prices(conn, client, NOW + timedelta(days=7))
    # Two months later it tries again, can't read the page, and keeps the old prices.
    with pages_client({prices.VIFF_URL: broken}) as client:
        scrape.refresh_prices(conn, client, NOW + timedelta(days=60))
    data, fetched = db.load_prices(conn)["VIFF Centre"]
    assert fetched == NOW and prices.from_json(data).tickets[0] == Price("Adult", "$17 / $15")


def test_saved_prices_replace_the_copy_in_venues(conn):
    newer = prices.Prices(tickets=(Price("Adult", "$18"),), checked="Nov 18, 2026")
    current = prices.current({"The Rio": newer})
    assert current["The Rio"] == newer
    assert current["VIFF Centre"] == BY_NAME["VIFF Centre"].prices
    assert current["The Dunbar"].origin  # third-party prices say where they're from
