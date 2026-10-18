"""SQLite storage for screenings.

A screening is identified by venue, title and start time. Each scrape replaces
a venue's upcoming screenings: new ones are added, existing ones are updated in
place, and ones the venue no longer lists (cancelled or moved) are removed.
Past screenings are never touched, so they stay as history.
"""

import sqlite3
from dataclasses import asdict, dataclass, fields
from datetime import UTC, date, datetime

from cineclock.films import Film
from cineclock.models import Screening
from cineclock.profiles import Profile

SCHEMA = """
CREATE TABLE IF NOT EXISTS screenings (
    id INTEGER PRIMARY KEY,
    venue TEXT NOT NULL,
    title TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    url TEXT NOT NULL,
    room TEXT,
    info_url TEXT,
    year INTEGER,
    note TEXT,
    poster_url TEXT,
    film_format TEXT,
    first_seen TEXT,
    UNIQUE (venue, title, starts_at)
);
CREATE INDEX IF NOT EXISTS screenings_starts_at ON screenings (starts_at);

-- Details looked up for each venue title and year. Kept separately from
-- screenings so lookups happen once a week per film, not on every scrape.
CREATE TABLE IF NOT EXISTS films (
    match_key TEXT PRIMARY KEY,
    fetched_at TEXT NOT NULL,
    tmdb_id INTEGER,
    imdb_id TEXT,
    title TEXT,
    year INTEGER,
    director TEXT,
    runtime INTEGER,
    overview TEXT,
    genres TEXT,
    poster_url TEXT,
    backdrop_url TEXT,
    letterboxd_url TEXT,
    letterboxd_rating REAL,
    letterboxd_count INTEGER,
    imdb_rating REAL,
    rt_score INTEGER,
    metacritic INTEGER
);

-- A synced Letterboxd member's films, one row per film they've listed or watched.
CREATE TABLE IF NOT EXISTS profile_films (
    user TEXT NOT NULL,
    slug TEXT NOT NULL,
    watchlist INTEGER NOT NULL DEFAULT 0,
    watched INTEGER NOT NULL DEFAULT 0,
    rating INTEGER,
    last_watched TEXT,
    PRIMARY KEY (user, slug)
);

CREATE TABLE IF NOT EXISTS profiles (
    user TEXT PRIMARY KEY,
    fetched_at TEXT NOT NULL,
    diary_since TEXT
);
"""

FIELDS = (
    "venue", "title", "starts_at", "url", "room", "info_url", "year", "note", "poster_url",
    "film_format",
)  # fmt: skip


@dataclass(frozen=True)
class SyncResult:
    added: int
    kept: int
    removed: int


# Columns added after the first release. A database saved by an older version
# (like the one the deploy keeps between runs) gets them added on connect.
ADDED_COLUMNS = {
    "screenings": {"first_seen": "TEXT", "film_format": "TEXT", "room": "TEXT"},
    "films": {"letterboxd_count": "INTEGER", "genres": "TEXT", "metacritic": "INTEGER"},
}


def connect(path: str = "cineclock.db") -> sqlite3.Connection:
    # The web app may open the connection on one thread and use it on another.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    upgrade(conn)
    return conn


def upgrade(conn: sqlite3.Connection) -> None:
    for table, columns in ADDED_COLUMNS.items():
        have = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, kind in columns.items():
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")
    # VIFF's studio was once its own venue; it's now a room of VIFF Centre.
    conn.execute(
        "UPDATE OR IGNORE screenings SET venue = 'VIFF Centre', room = 'viff-lochmaddy' "
        "WHERE venue = 'VIFF Lochmaddy'"
    )
    conn.execute("DELETE FROM screenings WHERE venue = 'VIFF Lochmaddy'")
    conn.commit()


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
        s.room,
        s.info_url,
        s.year,
        s.note,
        s.poster_url,
        s.film_format,
    )


def _from_row(row: sqlite3.Row) -> Screening:
    data = {field: row[field] for field in FIELDS}
    data["starts_at"] = datetime.fromisoformat(data["starts_at"])
    if row["first_seen"]:
        data["first_seen"] = datetime.fromisoformat(row["first_seen"])
    return Screening(**data)


def sync_venue(
    conn: sqlite3.Connection,
    venue: str,
    screenings: list[Screening],
    now: datetime,
    allow_empty: bool = False,
) -> SyncResult:
    if any(s.venue != venue for s in screenings):
        raise ValueError(f"all screenings must belong to {venue}")

    # An empty scrape is far more likely a broken page than a venue with nothing
    # on, so leave the existing listings alone rather than wiping them. The one
    # exception: a scraper covering two screens that found shows for one of them
    # is working, so the other really has nothing on.
    if not screenings and not allow_empty:
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
            INSERT INTO screenings ({", ".join(FIELDS)}, first_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (venue, title, starts_at) DO UPDATE SET
                url = excluded.url,
                room = excluded.room,
                info_url = excluded.info_url,
                year = excluded.year,
                note = excluded.note,
                poster_url = excluded.poster_url,
                film_format = excluded.film_format,
                -- Keep the date we first saw it; only fill it in for older rows.
                first_seen = COALESCE(screenings.first_seen, excluded.first_seen)
            """,
            [(*_to_row(s), cutoff) for s in screenings],
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


FILM_FIELDS = [f.name for f in fields(Film)]


def get_film(conn: sqlite3.Connection, key: str) -> Film | None:
    row = conn.execute("SELECT * FROM films WHERE match_key = ?", (key,)).fetchone()
    if not row:
        return None
    data = {name: row[name] for name in FILM_FIELDS}
    data["fetched_at"] = datetime.fromisoformat(data["fetched_at"])
    return Film(**data)


def save_film(conn: sqlite3.Connection, film: Film) -> None:
    data = asdict(film)
    data["fetched_at"] = _utc_text(film.fetched_at)
    columns = ", ".join(FILM_FIELDS)
    placeholders = ", ".join(f":{name}" for name in FILM_FIELDS)
    with conn:
        conn.execute(f"INSERT OR REPLACE INTO films ({columns}) VALUES ({placeholders})", data)


def films_by_key(conn: sqlite3.Connection) -> dict[str, Film]:
    rows = conn.execute("SELECT match_key FROM films").fetchall()
    return {row["match_key"]: get_film(conn, row["match_key"]) for row in rows}


def save_profile(conn: sqlite3.Connection, profile: Profile, now: datetime) -> None:
    """Replace everything stored for this member with a fresh read."""
    slugs = profile.watchlist | set(profile.watched)
    rows = [
        (
            profile.user,
            slug,
            int(slug in profile.watchlist),
            int(slug in profile.watched),
            profile.watched.get(slug),
            profile.diary[slug].isoformat() if slug in profile.diary else None,
        )
        for slug in sorted(slugs)
    ]
    since = profile.diary_since.isoformat() if profile.diary_since else None
    with conn:
        conn.execute("DELETE FROM profile_films WHERE user = ?", (profile.user,))
        conn.executemany("INSERT INTO profile_films VALUES (?, ?, ?, ?, ?, ?)", rows)
        conn.execute(
            "INSERT OR REPLACE INTO profiles VALUES (?, ?, ?)",
            (profile.user, _utc_text(now), since),
        )


def load_profile(conn: sqlite3.Connection, user: str) -> tuple[Profile, datetime] | None:
    """The stored profile and when it was read, or None if never synced."""
    head = conn.execute("SELECT * FROM profiles WHERE user = ?", (user,)).fetchone()
    if not head:
        return None
    profile = Profile(user)
    if head["diary_since"]:
        profile.diary_since = date.fromisoformat(head["diary_since"])
    for row in conn.execute("SELECT * FROM profile_films WHERE user = ?", (user,)):
        if row["watchlist"]:
            profile.watchlist.add(row["slug"])
        if row["watched"]:
            profile.watched[row["slug"]] = row["rating"]
        if row["last_watched"]:
            profile.diary[row["slug"]] = date.fromisoformat(row["last_watched"])
    return profile, datetime.fromisoformat(head["fetched_at"])
