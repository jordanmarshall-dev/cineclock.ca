"""Scrape every venue and save the results: python -m cineclock.scrape"""

import os
from datetime import UTC, datetime

from cineclock import db
from cineclock.scrapers import make_client, park, rio, viff

VENUES = {rio.VENUE: rio.scrape, viff.VENUE: viff.scrape, park.VENUE: park.scrape}


def main():
    conn = db.connect(os.environ.get("CINECLOCK_DB", "cineclock.db"))
    now = datetime.now(UTC)
    with make_client() as client:
        for venue, scrape in VENUES.items():
            # One venue failing shouldn't stop the others from updating.
            try:
                result = db.sync_venue(conn, venue, scrape(client, now=now), now)
            except Exception as error:
                print(f"{venue}: failed ({error})")
                continue
            print(f"{venue}: {result.added} new, {result.kept} kept, {result.removed} removed")
    conn.close()


if __name__ == "__main__":
    main()
