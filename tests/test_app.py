from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from cineclock import db
from cineclock.app import app, get_conn, get_now
from cineclock.models import Screening

NOW = datetime(2026, 10, 18, 8, 0, tzinfo=UTC)


@pytest.fixture
def client():
    connection = db.connect(":memory:")
    db.sync_venue(
        connection,
        "The Rio",
        [Screening("The Rio", "Scream", NOW + timedelta(days=1), "https://tix/scream")],
        NOW,
    )
    app.dependency_overrides[get_conn] = lambda: connection
    app.dependency_overrides[get_now] = lambda: NOW
    yield TestClient(app)
    app.dependency_overrides.clear()
    connection.close()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_serves_the_same_pages_as_the_build(client):
    assert "Scream" in client.get("/").text
    assert "Scream" in client.get("/films/scream/").text
    assert "1660 East Broadway" in client.get("/venues/rio/").text


def test_missing_slash_redirects_like_github_pages(client):
    response = client.get("/films/scream", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/films/scream/"


def test_unknown_page_is_404(client):
    assert client.get("/films/nope/").status_code == 404


def test_static_files(client):
    assert client.get("/static/site.css").status_code == 200
    assert client.get("/static/fonts/instrument-sans.woff2").status_code == 200
