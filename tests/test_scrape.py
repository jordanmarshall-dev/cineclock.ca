from datetime import UTC, datetime, timedelta

from cineclock import db, scrape
from cineclock.models import Screening

NOW = datetime(2026, 10, 18, 8, 0, tzinfo=UTC)


def show(venue, title, days=1):
    return Screening(venue, title, NOW + timedelta(days=days), f"https://x/{title}")


def run(conn, monkeypatch, scrapers):
    monkeypatch.setattr(scrape, "SCRAPERS", scrapers)
    scrape.run_scrapers(conn, client=None, now=NOW)


def test_one_broken_venue_does_not_stop_the_others(monkeypatch, capsys):
    conn = db.connect(":memory:")

    def broken(client, now):
        raise RuntimeError("site is down")

    def working(client, now):
        return [show("The Rio", "Stalker")]

    run(conn, monkeypatch, [(broken, ("The Park",)), (working, ("The Rio",))])
    output = capsys.readouterr().out
    assert "The Park: failed (site is down)" in output
    assert "The Rio: 1 new, 0 kept, 0 removed" in output
    assert [s.title for s in db.upcoming(conn, NOW)] == ["Stalker"]


def test_two_screen_scraper_syncs_each_screen(monkeypatch):
    conn = db.connect(":memory:")
    venues = ("VIFF Centre", "VIFF Lochmaddy")

    def both(client, now):
        return [show("VIFF Centre", "Cure"), show("VIFF Lochmaddy", "Pulse")]

    def centre_only(client, now):
        return [show("VIFF Centre", "Cure")]

    run(conn, monkeypatch, [(both, venues)])
    run(conn, monkeypatch, [(centre_only, venues)])
    # The scraper worked, so Lochmaddy really has nothing on now.
    assert [(s.venue, s.title) for s in db.upcoming(conn, NOW)] == [("VIFF Centre", "Cure")]


def test_empty_scraper_keeps_everything(monkeypatch):
    conn = db.connect(":memory:")
    venues = ("VIFF Centre", "VIFF Lochmaddy")
    run(conn, monkeypatch, [(lambda client, now: [show("VIFF Lochmaddy", "Pulse")], venues)])
    run(conn, monkeypatch, [(lambda client, now: [], venues)])
    assert [s.title for s in db.upcoming(conn, NOW)] == ["Pulse"]


def test_old_combined_viff_rows_move_to_the_right_screen(monkeypatch):
    # Before the split, Lochmaddy shows were saved under "VIFF Centre".
    conn = db.connect(":memory:")
    db.sync_venue(conn, "VIFF Centre", [show("VIFF Centre", "Pulse")], NOW)
    run(
        conn,
        monkeypatch,
        [
            (
                lambda client, now: [show("VIFF Lochmaddy", "Pulse")],
                ("VIFF Centre", "VIFF Lochmaddy"),
            )
        ],
    )
    assert [s.venue for s in db.upcoming(conn, NOW)] == ["VIFF Lochmaddy"]


def test_profiles_sync_once_a_day_and_keep_the_last_copy_on_failure(monkeypatch):
    from cineclock import profiles
    from cineclock.profiles import Profile

    conn = db.connect(":memory:")
    calls = []

    def fetch(client, user, pause):
        calls.append(user)
        if len(calls) == 2:
            raise RuntimeError("letterboxd down")
        return Profile(user, watchlist={"jaws"})

    monkeypatch.setattr(profiles, "SYNCED", ["me"])
    monkeypatch.setattr(profiles, "fetch", fetch)
    scrape.sync_profiles(conn, None, NOW)
    scrape.sync_profiles(conn, None, NOW + timedelta(hours=2))  # too soon, skipped
    scrape.sync_profiles(conn, None, NOW + timedelta(days=1))  # fails
    assert calls == ["me", "me"]
    assert db.load_profile(conn, "me")[0].watchlist == {"jaws"}
