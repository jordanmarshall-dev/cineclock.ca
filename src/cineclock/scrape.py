"""Scrape every venue, save the results, then look up film details: python -m cineclock.scrape"""

import os
from datetime import UTC, datetime

from cineclock import db
from cineclock.enrich import enrich
from cineclock.scrapers import cinematheque, dunbar, make_client, park, rio, viff

# Each scraper and the venues it covers.
SCRAPERS = [
    (rio.scrape, rio.VENUES),
    (park.scrape, park.VENUES),
    (cinematheque.scrape, cinematheque.VENUES),
    (viff.scrape, viff.VENUES),
    (dunbar.scrape, dunbar.VENUES),
]


def run_scrapers(conn, client, now) -> None:
    for scrape, venues in SCRAPERS:
        # One venue failing shouldn't stop the others from updating.
        try:
            screenings = scrape(client, now=now)
        except Exception as error:
            print(f"{', '.join(venues)}: failed ({error})")
            continue
        for venue in venues:
            mine = [s for s in screenings if s.venue == venue]
            result = db.sync_venue(conn, venue, mine, now, allow_empty=bool(screenings))
            print(f"{venue}: {result.added} new, {result.kept} kept, {result.removed} removed")


def main():
    conn = db.connect(os.environ.get("CINECLOCK_DB", "cineclock.db"))
    now = datetime.now(UTC)
    with make_client() as client:
        run_scrapers(conn, client, now)
        tmdb_key = os.environ.get("TMDB_API_KEY")
        if tmdb_key:
            result = enrich(conn, client, now, tmdb_key, os.environ.get("OMDB_API_KEY"))
            print(
                f"Film details: {result.looked_up} looked up, {result.matched} matched, "
                f"{result.failed} failed"
            )
        else:
            print("Film details: skipped (no TMDB_API_KEY)")
    conn.close()


if __name__ == "__main__":
    main()
