from datetime import UTC, datetime, timedelta

from cineclock import db, scrape
from cineclock.models import Screening


def test_one_broken_venue_does_not_stop_the_others(tmp_path, monkeypatch, capsys):
    path = str(tmp_path / "test.db")
    monkeypatch.setenv("CINECLOCK_DB", path)

    def working(client, now):
        return [Screening("The Rio", "Stalker", now + timedelta(days=1), "https://x")]

    def broken(client, now):
        raise RuntimeError("site is down")

    monkeypatch.setattr(scrape, "VENUES", {"The Park": broken, "The Rio": working})
    scrape.main()

    output = capsys.readouterr().out
    assert "The Park: failed (site is down)" in output
    assert "The Rio: 1 new, 0 kept, 0 removed" in output
    conn = db.connect(path)
    assert [s.title for s in db.upcoming(conn, datetime.now(UTC))] == ["Stalker"]
    conn.close()
