from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from cineclock import db
from cineclock.app import app, get_conn, get_now
from cineclock.models import Screening

NOW = datetime(2026, 10, 18, 8, 0, tzinfo=UTC)


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    app.dependency_overrides[get_conn] = lambda: connection
    app.dependency_overrides[get_now] = lambda: NOW
    yield connection
    app.dependency_overrides.clear()
    connection.close()


@pytest.fixture
def client(conn):
    return TestClient(app)


def add(conn, *screenings):
    db.sync_venue(conn, "The Rio", list(screenings), NOW)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_empty_page_says_how_to_fill_it(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "python -m cineclock.scrape" in response.text


def test_page_shows_screenings(client, conn):
    add(
        conn,
        Screening(
            "The Rio",
            "Scream",
            datetime(2026, 10, 27, 4, 30, tzinfo=UTC),
            "https://tix/scream",
            info_url="https://riotheatre.ca/movie/scream/",
            year=1996,
            note="30th Anniversary Screening",
            poster_url="https://riotheatre.ca/poster.jpg",
        ),
    )
    page = client.get("/").text
    assert 'aria-label="Monday Oct 26"' in page
    assert "Scream" in page
    assert "1996" in page
    assert "30th Anniversary Screening" in page
    assert 'href="https://tix/scream"' in page
    assert "9:30 pm" in page
    assert 'src="https://riotheatre.ca/poster.jpg"' in page


def test_past_screenings_are_hidden(client, conn):
    add(conn, Screening("The Rio", "Gone", NOW - timedelta(hours=1), "https://tix/gone"))
    assert "Gone" not in client.get("/").text


def test_titles_are_escaped(client, conn):
    add(
        conn,
        Screening("The Rio", "<script>alert(1)</script>", NOW + timedelta(hours=2), "https://x"),
    )
    page = client.get("/").text
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_fonts_are_served_locally(client):
    response = client.get("/static/fonts/big-shoulders-display.woff2")
    assert response.status_code == 200
    assert "fonts.googleapis.com" not in client.get("/").text
