"""Scrape every venue, save the results, then look up film details: python -m cineclock.scrape"""

import os
from datetime import UTC, datetime, timedelta

from cineclock import db, prices, profiles
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
            for venue in venues:
                db.record_run(conn, venue, ok=False, now=now)
            continue
        for venue in venues:
            mine = [s for s in screenings if s.venue == venue]
            result = db.sync_venue(conn, venue, mine, now, allow_empty=bool(screenings))
            print(f"{venue}: {result.added} new, {result.kept} kept, {result.removed} removed")
            if not screenings:
                print(f"{venue}: nothing found, keeping the saved listings")
            elif result.held:
                print(f"{venue}: most saved shows went missing, so none were deleted")
            db.record_run(conn, venue, ok=bool(screenings) and not result.held, now=now)


# Letterboxd lists change slowly, and reading them is ~50 page loads, so once a day is plenty.
PROFILE_REFRESH = timedelta(hours=20)


def sync_profiles(conn, client, now, pause: float = 1.0) -> None:
    for user in profiles.SYNCED:
        stored = db.load_profile(conn, user)
        if stored and now - stored[1] < PROFILE_REFRESH:
            print(f"Letterboxd {user}: up to date")
            continue
        try:
            profile = profiles.fetch(client, user, pause)
        except Exception as error:
            # Keep the last good copy; the site carries on with it.
            print(f"Letterboxd {user}: failed ({error})")
            continue
        db.save_profile(conn, profile, now)
        print(
            f"Letterboxd {user}: {len(profile.watchlist)} on watchlist, "
            f"{len(profile.watched)} watched"
        )


def refresh_prices(conn, client, now) -> None:
    """Re-read each theatre's price page once its saved prices are a month old."""
    stored = db.load_prices(conn)
    for venue in prices.SOURCES:
        if venue in stored and now - stored[venue][1] < prices.REFRESH:
            print(f"{venue} prices: up to date")
            continue
        try:
            found = prices.fetch(client, venue, now)
        except Exception as error:
            print(f"{venue} prices: failed ({error})")
            continue
        if not found:
            # The page changed shape; keep the last good prices and say so in the log.
            print(f"{venue} prices: couldn't read the page, keeping the last prices")
            continue
        db.save_prices(conn, venue, prices.to_json(found), now)
        print(f"{venue} prices: updated")


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
        sync_profiles(conn, client, now)
        refresh_prices(conn, client, now)
    conn.close()


if __name__ == "__main__":
    main()
