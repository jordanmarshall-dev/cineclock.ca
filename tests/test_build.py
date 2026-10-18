import json
from datetime import UTC, datetime, timedelta

import pytest

from cineclock import db
from cineclock.build import build
from cineclock.models import Screening

NOW = datetime(2026, 10, 18, 8, 45, tzinfo=UTC)


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    yield connection
    connection.close()


def test_build_writes_every_page_and_asset(conn, tmp_path):
    db.sync_venue(
        conn, "The Rio", [Screening("The Rio", "Scream", NOW + timedelta(days=1), "https://x")], NOW
    )
    out = tmp_path / "site"
    count = build(conn, out, NOW)

    assert count == 1 + 1 + 5  # home, one film, five venues
    assert "Scream" in (out / "index.html").read_text()
    assert (out / "films/scream/index.html").exists()
    assert (out / "venues/rio/index.html").exists()
    assert (out / "static/site.css").exists()
    assert (out / "static/fonts/source-serif-4.woff2").exists()
    assert "Updated Sun Oct 18, 1:45 am." in (out / "index.html").read_text()


def test_build_publishes_stats(conn, tmp_path):
    build(conn, tmp_path / "site", NOW)
    summary = json.loads((tmp_path / "site/stats.json").read_text())
    assert summary["screenings"] == 0
    assert summary["updated"].startswith("2026-10-18T08:45")


def test_build_replaces_old_output(conn, tmp_path):
    out = tmp_path / "site"
    (out / "films/gone").mkdir(parents=True)
    (out / "films/gone/index.html").write_text("old")
    build(conn, out, NOW)
    assert not (out / "films/gone").exists()


def test_no_page_links_outside_the_site_root(conn, tmp_path):
    # GitHub Pages serves from /cineclock/, so links starting with "/" would break.
    db.sync_venue(
        conn, "The Rio", [Screening("The Rio", "Scream", NOW + timedelta(days=1), "https://x")], NOW
    )
    out = tmp_path / "site"
    build(conn, out, NOW)
    for page in out.rglob("*.html"):
        html = page.read_text()
        assert 'href="/' not in html and 'src="/' not in html, page
