"""SQLite storage for screenings.

A screening is identified by venue, title and start time. Each scrape replaces
a venue's upcoming screenings: new ones are added, existing ones are updated in
place, and ones the venue no longer lists (cancelled or moved) are removed.
Past screenings are never touched, so they stay as history.
"""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from cineclock.models import Screening

SCHEMA = """
CREATE TABLE IF NOT EXISTS screenings (
    id INTEGER PRIMARY KEY,
    venue TEXT NOT NULL,
    title TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    url TEXT NOT NULL,
    info_url TEXT,
    year INTEGER,
    note TEXT,
    poster_url TEXT,
    UNIQUE (venue, title, starts_at)
);
CREATE INDEX IF NOT EXISTS screenings_starts_at ON screenings (starts_at);
"""

FIELDS = ("venue", "title", "starts_at", "url", "info_url", "year", "note", "poster_url")


@dataclass(frozen=True)
class SyncResult:
    added: int
    kept: int
    removed: int


def connect(path: str = "cineclock.db") -> sqlite3.Connection:
    # The web app may open the connection on one thread and use it on another.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _utc_text(dt: datetime) -> str:
    # Times are saved as UTC text in one fixed format, so comparing and sorting
    # the text gives the same answer as comparing the times.
    return dt.astimezone(UTC).replace(microsecond=0).isoformat()


def _to_row(s: Screening) -> tuple:
    return (
        s.venue,
        s.title,
        _utc_text(s.starts_at),
        s.url,
        s.info_url,
        s.year,
        s.note,
        s.poster_url,
    )


def _from_row(row: sqlite3.Row) -> Screening:
    data = {field: row[field] for field in FIELDS}
    data["starts_at"] = datetime.fromisoformat(data["starts_at"])
    return Screening(**data)


def sync_venue(
    conn: sqlite3.Connection, venue: str, screenings: list[Screening], now: datetime
) -> SyncResult:
    if any(s.venue != venue for s in screenings):
        raise ValueError(f"all screenings must belong to {venue}")

    # An empty scrape is far more likely a broken page than a venue with nothing
    # on, so leave the existing listings alone rather than wiping them.
    if not screenings:
        return SyncResult(added=0, kept=0, removed=0)

    cutoff = _utc_text(now)
    scraped = {(s.title, _utc_text(s.starts_at)) for s in screenings}

    # "with conn" makes this one transaction: if anything fails, nothing changes.
    with conn:
        existing = {
            (row["title"], row["starts_at"])
            for row in conn.execute(
                "SELECT title, starts_at FROM screenings WHERE venue = ?", (venue,)
            )
        }
        conn.executemany(
            f"""
            INSERT INTO screenings ({", ".join(FIELDS)}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (venue, title, starts_at) DO UPDATE SET
                url = excluded.url,
                info_url = excluded.info_url,
                year = excluded.year,
                note = excluded.note,
                poster_url = excluded.poster_url
            """,
            [_to_row(s) for s in screenings],
        )
        gone = {key for key in existing - scraped if key[1] >= cutoff}
        conn.executemany(
            "DELETE FROM screenings WHERE venue = ? AND title = ? AND starts_at = ?",
            [(venue, title, starts_at) for title, starts_at in gone],
        )

    return SyncResult(
        added=len(scraped - existing), kept=len(scraped & existing), removed=len(gone)
    )


def upcoming(conn: sqlite3.Connection, now: datetime) -> list[Screening]:
    rows = conn.execute(
        "SELECT * FROM screenings WHERE starts_at >= ? ORDER BY starts_at, venue, title",
        (_utc_text(now),),
    )
    return [_from_row(row) for row in rows]
