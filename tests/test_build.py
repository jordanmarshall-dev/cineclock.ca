from datetime import UTC, datetime, timedelta

import pytest

from cineclock import db
from cineclock.build import build, updated_label
from cineclock.models import Screening

NOW = datetime(2026, 10, 18, 8, 45, tzinfo=UTC)


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    yield connection
    connection.close()


def test_updated_label_is_vancouver_time():
    assert updated_label(NOW) == "Sun Oct 18, 1:45 am"


def test_build_writes_page_and_fonts(conn, tmp_path):
    db.sync_venue(
        conn, "The Rio", [Screening("The Rio", "Scream", NOW + timedelta(days=1), "https://x")], NOW
    )
    out = tmp_path / "site"
    build(conn, out, NOW)

    page = (out / "index.html").read_text()
    assert "Scream" in page
    assert "Updated Sun Oct 18, 1:45 am." in page
    assert (out / "static/fonts/big-shoulders-display.woff2").exists()


def test_built_page_uses_relative_paths(conn, tmp_path):
    # GitHub Pages serves the site from /cineclock/, so absolute /static/ links would break.
    build(conn, tmp_path / "site", NOW)
    page = (tmp_path / "site/index.html").read_text()
    assert 'src: url("static/fonts/' in page
    assert '"/static/' not in page


def test_build_replaces_old_output(conn, tmp_path):
    out = tmp_path / "site"
    out.mkdir()
    (out / "stale.html").write_text("old")
    build(conn, out, NOW)
    assert not (out / "stale.html").exists()
    assert (out / "index.html").exists()


def test_build_with_no_screenings_shows_empty_message(conn, tmp_path):
    build(conn, tmp_path / "site", NOW)
    assert "No showtimes saved yet" in (tmp_path / "site/index.html").read_text()
